// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

//! Provider-agnostic model layer. Local models are first-class: the only
//! backend shipped in v0 talks to an Ollama server over plain HTTP on the
//! local network. The HTTP client is hand-rolled on `std::net::TcpStream`
//! (no dependencies, no TLS — Ollama is a localhost/LAN service), which
//! keeps the core light per the RPi5 contract.
//!
//! Every response reports the tokens it consumed so the kernel can charge
//! the calling agent's budget — token accounting is load-bearing here, not
//! telemetry.

use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::Duration;

use serde_json::{json, Value};

use crate::agent::AgentId;
use crate::error::{Error, Result};

#[derive(Clone, Debug)]
pub struct ModelRequest {
    pub agent: AgentId,
    pub prompt: String,
}

#[derive(Clone, Debug)]
pub struct ModelResponse {
    pub text: String,
    /// Prompt + completion tokens as reported by the backend. Charged to
    /// the calling agent's budget by `Ctx::generate`.
    pub tokens_used: u64,
}

pub trait ModelBackend: Send {
    fn name(&self) -> &str;
    fn generate(&mut self, req: &ModelRequest) -> Result<ModelResponse>;
}

/// Ollama backend (`POST /api/generate`, non-streaming).
///
/// Configuration comes from the constructor or, via [`OllamaBackend::from_env`],
/// the environment: `ENIGMA_OLLAMA_ADDR` (default `127.0.0.1:11434`) and
/// `ENIGMA_OLLAMA_MODEL` (default `llama3.2:1b`, a model that fits an
/// 8 GB Pi alongside the rest of the system).
pub struct OllamaBackend {
    addr: String,
    model: String,
    connect_timeout: Duration,
    read_timeout: Duration,
}

impl OllamaBackend {
    pub fn new(addr: &str, model: &str) -> Self {
        OllamaBackend {
            addr: addr.to_string(),
            model: model.to_string(),
            connect_timeout: Duration::from_secs(3),
            read_timeout: Duration::from_secs(600),
        }
    }

    pub fn from_env() -> Self {
        let addr =
            std::env::var("ENIGMA_OLLAMA_ADDR").unwrap_or_else(|_| "127.0.0.1:11434".to_string());
        let model =
            std::env::var("ENIGMA_OLLAMA_MODEL").unwrap_or_else(|_| "llama3.2:1b".to_string());
        Self::new(&addr, &model)
    }

    pub fn model(&self) -> &str {
        &self.model
    }
}

impl ModelBackend for OllamaBackend {
    fn name(&self) -> &str {
        "ollama"
    }

    fn generate(&mut self, req: &ModelRequest) -> Result<ModelResponse> {
        let body = json!({
            "model": self.model,
            "prompt": req.prompt,
            "stream": false,
        });
        let response = http_post_json(
            &self.addr,
            "/api/generate",
            &body,
            self.connect_timeout,
            self.read_timeout,
        )?;

        let text = response
            .get("response")
            .and_then(Value::as_str)
            .ok_or_else(|| {
                Error::Model(format!(
                    "ollama returned no 'response' field: {}",
                    truncate(&response.to_string(), 200)
                ))
            })?
            .to_string();

        let prompt_tokens = response
            .get("prompt_eval_count")
            .and_then(Value::as_u64)
            .unwrap_or(0);
        let completion_tokens = response
            .get("eval_count")
            .and_then(Value::as_u64)
            .unwrap_or(0);
        let mut tokens_used = prompt_tokens + completion_tokens;
        if tokens_used == 0 {
            // Backend gave no counts (some proxies strip them): estimate
            // conservatively so budgets still bind rather than leak.
            tokens_used =
                (req.prompt.split_whitespace().count() + text.split_whitespace().count()) as u64;
        }

        Ok(ModelResponse { text, tokens_used })
    }
}

fn truncate(s: &str, max: usize) -> &str {
    match s.char_indices().nth(max) {
        Some((idx, _)) => &s[..idx],
        None => s,
    }
}

/// Minimal HTTP/1.1 POST for a JSON body. `Connection: close`, so the
/// response is everything until EOF; handles both Content-Length and
/// chunked transfer encoding.
fn http_post_json(
    addr: &str,
    path: &str,
    body: &Value,
    connect_timeout: Duration,
    read_timeout: Duration,
) -> Result<Value> {
    let sock_addr = addr
        .parse()
        .map_err(|e| Error::Model(format!("bad backend address '{addr}': {e}")))?;
    let mut stream = TcpStream::connect_timeout(&sock_addr, connect_timeout).map_err(|e| {
        Error::Model(format!(
            "cannot connect to model backend at {addr}: {e} \
             (is `ollama serve` running?)"
        ))
    })?;
    stream.set_read_timeout(Some(read_timeout))?;

    let payload = body.to_string();
    let request = format!(
        "POST {path} HTTP/1.1\r\nHost: {addr}\r\nContent-Type: application/json\r\n\
         Content-Length: {}\r\nConnection: close\r\n\r\n{payload}",
        payload.len()
    );
    stream.write_all(request.as_bytes())?;

    let mut raw = Vec::new();
    stream.read_to_end(&mut raw)?;

    let header_end = find_subslice(&raw, b"\r\n\r\n")
        .ok_or_else(|| Error::Model("malformed HTTP response (no header end)".into()))?;
    let headers = String::from_utf8_lossy(&raw[..header_end]);
    let mut body_bytes = &raw[header_end + 4..];

    let status = headers
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|code| code.parse::<u16>().ok())
        .ok_or_else(|| Error::Model("malformed HTTP status line".into()))?;

    let decoded;
    if headers
        .lines()
        .any(|l| l.to_ascii_lowercase().starts_with("transfer-encoding:") && l.contains("chunked"))
    {
        decoded = decode_chunked(body_bytes)?;
        body_bytes = &decoded;
    }

    if status != 200 {
        return Err(Error::Model(format!(
            "backend returned HTTP {status}: {}",
            truncate(&String::from_utf8_lossy(body_bytes), 200)
        )));
    }

    serde_json::from_slice(body_bytes)
        .map_err(|e| Error::Model(format!("backend returned invalid JSON: {e}")))
}

fn find_subslice(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack
        .windows(needle.len())
        .position(|window| window == needle)
}

fn decode_chunked(mut data: &[u8]) -> Result<Vec<u8>> {
    let mut out = Vec::new();
    loop {
        let line_end = find_subslice(data, b"\r\n")
            .ok_or_else(|| Error::Model("malformed chunked encoding".into()))?;
        let size_str = String::from_utf8_lossy(&data[..line_end]);
        let size = usize::from_str_radix(size_str.trim().split(';').next().unwrap_or(""), 16)
            .map_err(|_| Error::Model("malformed chunk size".into()))?;
        data = &data[line_end + 2..];
        if size == 0 {
            return Ok(out);
        }
        if data.len() < size + 2 {
            return Err(Error::Model("truncated chunked body".into()));
        }
        out.extend_from_slice(&data[..size]);
        data = &data[size + 2..];
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decode_chunked_body() {
        let body = b"5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n";
        assert_eq!(decode_chunked(body).unwrap(), b"hello world");
    }

    #[test]
    fn truncate_is_char_safe() {
        assert_eq!(truncate("héllo", 2), "hé");
        assert_eq!(truncate("ab", 10), "ab");
    }
}
