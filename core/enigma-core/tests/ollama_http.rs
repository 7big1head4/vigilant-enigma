// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

//! Hermetic tests for the REAL Ollama HTTP client: a `TcpListener` on a
//! random localhost port plays the server role, so the exact bytes-on-wire
//! path ships tested without needing a live LLM.

use std::io::{Read, Write};
use std::net::TcpListener;
use std::thread;

use enigma_core::{AgentId, ModelBackend, ModelRequest, OllamaBackend};

/// Serve exactly one connection with a canned HTTP response, returning the
/// bound address and a handle that yields the request the client sent.
fn one_shot_server(response: &'static str) -> (String, thread::JoinHandle<String>) {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
    let addr = listener.local_addr().unwrap().to_string();
    let handle = thread::spawn(move || {
        let (mut stream, _) = listener.accept().expect("accept");
        let mut request = Vec::new();
        let mut buf = [0u8; 4096];
        // Read until the JSON body is complete (Content-Length delimited).
        loop {
            let n = stream.read(&mut buf).expect("read");
            request.extend_from_slice(&buf[..n]);
            if let Some(header_end) = find(&request, b"\r\n\r\n") {
                let headers = String::from_utf8_lossy(&request[..header_end]).to_string();
                let length: usize = headers
                    .lines()
                    .find_map(|l| {
                        l.to_ascii_lowercase()
                            .strip_prefix("content-length:")
                            .map(|v| v.trim().parse().unwrap())
                    })
                    .unwrap_or(0);
                if request.len() >= header_end + 4 + length {
                    break;
                }
            }
            if n == 0 {
                break;
            }
        }
        stream.write_all(response.as_bytes()).expect("write");
        String::from_utf8_lossy(&request).to_string()
    });
    (addr, handle)
}

fn find(haystack: &[u8], needle: &[u8]) -> Option<usize> {
    haystack.windows(needle.len()).position(|w| w == needle)
}

fn generate_against(addr: &str) -> enigma_core::Result<enigma_core::ModelResponse> {
    let mut backend = OllamaBackend::new(addr, "test-model");
    backend.generate(&ModelRequest {
        agent: AgentId(1),
        prompt: "hello there".into(),
    })
}

#[test]
fn parses_content_length_response_and_token_counts() {
    let body = r#"{"response":"hi from the model","prompt_eval_count":7,"eval_count":5}"#;
    let response = format!(
        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\
         Connection: close\r\n\r\n{body}",
        body.len()
    );
    let (addr, server) = one_shot_server(Box::leak(response.into_boxed_str()));

    let result = generate_against(&addr).expect("generate succeeds");
    assert_eq!(result.text, "hi from the model");
    assert_eq!(result.tokens_used, 12); // 7 prompt + 5 completion

    // The client sent a well-formed Ollama request.
    let request = server.join().unwrap();
    assert!(request.starts_with("POST /api/generate HTTP/1.1\r\n"));
    assert!(request.contains(r#""model":"test-model""#));
    assert!(request.contains(r#""stream":false"#));
    assert!(request.contains(r#""prompt":"hello there""#));
}

#[test]
fn parses_chunked_response() {
    let body = r#"{"response":"chunky","prompt_eval_count":2,"eval_count":3}"#;
    // Split the JSON across two chunks to prove real dechunking.
    let (first, second) = body.split_at(10);
    let response = format!(
        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\
         Transfer-Encoding: chunked\r\nConnection: close\r\n\r\n\
         {:x}\r\n{first}\r\n{:x}\r\n{second}\r\n0\r\n\r\n",
        first.len(),
        second.len()
    );
    let (addr, server) = one_shot_server(Box::leak(response.into_boxed_str()));

    let result = generate_against(&addr).expect("generate succeeds");
    assert_eq!(result.text, "chunky");
    assert_eq!(result.tokens_used, 5);
    server.join().unwrap();
}

#[test]
fn missing_token_counts_fall_back_to_word_estimate() {
    let body = r#"{"response":"three word answer"}"#;
    let response = format!(
        "HTTP/1.1 200 OK\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let (addr, server) = one_shot_server(Box::leak(response.into_boxed_str()));

    let result = generate_against(&addr).expect("generate succeeds");
    // 2 prompt words ("hello there") + 3 response words — budgets never leak.
    assert_eq!(result.tokens_used, 5);
    server.join().unwrap();
}

#[test]
fn non_200_maps_to_model_error() {
    let body = r#"{"error":"model 'test-model' not found"}"#;
    let response = format!(
        "HTTP/1.1 404 Not Found\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    );
    let (addr, server) = one_shot_server(Box::leak(response.into_boxed_str()));

    let err = generate_against(&addr).expect_err("must fail");
    let message = err.to_string();
    assert!(message.contains("HTTP 404"), "got: {message}");
    assert!(message.contains("not found"), "got: {message}");
    server.join().unwrap();
}

#[test]
fn connection_refused_is_a_clear_error() {
    // Nothing listens on this port (bind then drop to reserve-and-release).
    let addr = {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        listener.local_addr().unwrap().to_string()
    };
    let err = generate_against(&addr).expect_err("must fail");
    assert!(err.to_string().contains("cannot connect"), "got: {err}");
}
