// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

//! The Python bridge: agents written in Python, scheduled by the Rust
//! kernel exactly like native ones.
//!
//! The kernel spawns a worker process (`python3 -m enigma_sdk <module>`)
//! and speaks newline-delimited JSON over its stdin/stdout. A delivery is
//! a nested syscall loop — the kernel hands the worker a message, the
//! worker makes calls back into the kernel (`generate`, `spawn`,
//! `call_tool`, …), and each one is serviced through the same [`Ctx`] a
//! native agent uses. Budgets, capability checks, and suspension therefore
//! behave identically whichever language an agent is written in.
//!
//! IPC rather than PyO3 on purpose: embedding CPython would make the
//! interpreter resident in the kernel and put a compiler toolchain in the
//! way of running on a Pi. This keeps the core at two dependencies and the
//! SDK pure-stdlib.

use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::{Arc, Mutex};

use serde_json::{json, Value};

use crate::agent::{Agent, AgentId};
use crate::budget::Budget;
use crate::bus::{Address, Envelope, Sender};
use crate::error::{Error, Result};
use crate::kernel::{Ctx, Kernel, SpawnSpec};
use crate::permissions::CapabilitySet;

/// Protocol version this kernel speaks. The worker reports its own in the
/// handshake; a mismatch is refused rather than guessed at.
pub const PROTOCOL_VERSION: u64 = 1;

/// A running Python worker process.
///
/// Wrap in `Arc<Mutex<_>>` (as [`PythonBridge::spawn`] returns) and share
/// it across every Python agent — the kernel is single-threaded, so the
/// lock is uncontended and dispatches stay serialized and deterministic.
pub struct PythonBridge {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    kinds: Vec<String>,
}

impl PythonBridge {
    /// Spawn a worker and complete the handshake.
    ///
    /// The caller supplies the whole command, so the Python binary, the
    /// module of agents, and `PYTHONPATH` are all its choice:
    ///
    /// ```no_run
    /// # use std::process::Command;
    /// # use enigma_core::bridge::PythonBridge;
    /// let mut cmd = Command::new("python3");
    /// cmd.arg("-m").arg("enigma_sdk").arg("my_agents")
    ///    .env("PYTHONPATH", "sdk/python");
    /// let bridge = PythonBridge::spawn(cmd)?;
    /// # Ok::<(), enigma_core::Error>(())
    /// ```
    ///
    /// The worker's stderr is inherited, so Python tracebacks and any
    /// `print()` from agent code land in the kernel's terminal.
    pub fn spawn(mut command: Command) -> Result<Arc<Mutex<PythonBridge>>> {
        command.stdin(Stdio::piped()).stdout(Stdio::piped());
        let mut child = command.spawn().map_err(|e| {
            Error::Bridge(format!(
                "cannot start python worker ({e}) — is python3 on PATH?"
            ))
        })?;
        let stdin = child.stdin.take().expect("stdin was piped");
        let stdout = BufReader::new(child.stdout.take().expect("stdout was piped"));
        let mut bridge = PythonBridge {
            child,
            stdin,
            stdout,
            kinds: Vec::new(),
        };

        let hello = bridge.recv().map_err(|e| {
            Error::Bridge(format!(
                "python worker did not complete the handshake ({e}) — \
                 check its stderr for an import error"
            ))
        })?;
        if hello["op"] != json!("ready") {
            return Err(Error::Bridge(format!(
                "expected a 'ready' handshake, got {hello}"
            )));
        }
        let version = hello["protocol"].as_u64().unwrap_or(0);
        if version != PROTOCOL_VERSION {
            return Err(Error::Bridge(format!(
                "python worker speaks protocol {version}, kernel speaks {PROTOCOL_VERSION}"
            )));
        }
        bridge.kinds = hello["kinds"]
            .as_array()
            .map(|kinds| {
                kinds
                    .iter()
                    .filter_map(|k| k.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();
        Ok(Arc::new(Mutex::new(bridge)))
    }

    /// Agent kinds this worker advertised at startup.
    pub fn kinds(&self) -> &[String] {
        &self.kinds
    }

    fn send(&mut self, value: &Value) -> Result<()> {
        writeln!(self.stdin, "{value}")?;
        self.stdin.flush()?;
        Ok(())
    }

    fn recv(&mut self) -> Result<Value> {
        let mut line = String::new();
        if self.stdout.read_line(&mut line)? == 0 {
            return Err(Error::Bridge("python worker exited".into()));
        }
        serde_json::from_str(&line)
            .map_err(|e| Error::Bridge(format!("worker sent invalid JSON ({e}): {line:?}")))
    }
}

impl Drop for PythonBridge {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// Registers every kind a worker advertised, so the kernel can spawn them
/// by name just like native kinds.
pub fn register_python_kinds(kernel: &mut Kernel, bridge: &Arc<Mutex<PythonBridge>>) -> Result<()> {
    let kinds = {
        let guard = bridge
            .lock()
            .map_err(|_| Error::Bridge("bridge mutex poisoned".into()))?;
        guard.kinds().to_vec()
    };
    for kind in kinds {
        let shared = Arc::clone(bridge);
        kernel.register_kind(&kind.clone(), move |_| {
            Box::new(PythonAgent {
                kind: kind.clone(),
                bridge: Arc::clone(&shared),
            })
        });
    }
    Ok(())
}

/// A kernel-side agent whose behavior lives in the Python worker.
struct PythonAgent {
    kind: String,
    bridge: Arc<Mutex<PythonBridge>>,
}

impl Agent for PythonAgent {
    fn on_message(&mut self, ctx: &mut Ctx<'_>, msg: &Envelope) -> Result<()> {
        let mut bridge = self
            .bridge
            .lock()
            .map_err(|_| Error::Bridge("bridge mutex poisoned".into()))?;

        bridge.send(&json!({
            "op": "dispatch",
            "kind": self.kind,
            "agent_id": ctx.agent_id.0,
            "memory": ctx.memory.as_map(),
            "msg": envelope_json(msg),
        }))?;

        loop {
            let request = bridge.recv()?;
            match request["op"].as_str().unwrap_or_default() {
                "done" => {
                    // The worker returns the whole memory dict; it is the
                    // agent's durable identity, so the kernel adopts it.
                    if let Some(map) = request["memory"].as_object() {
                        ctx.memory.replace(map.clone());
                    }
                    return Ok(());
                }
                // An unhandled Python exception kills this agent, exactly
                // as an Err from a native agent would. The kernel lives on.
                "error" => {
                    return Err(Error::Bridge(
                        request["message"]
                            .as_str()
                            .unwrap_or("python agent failed")
                            .to_string(),
                    ))
                }
                op => {
                    // A refused syscall is reported to Python (where it
                    // raises EnigmaError) rather than failing the dispatch,
                    // so agents can catch and recover.
                    let reply = match service(ctx, op, &request) {
                        Ok(value) => json!({ "ok": value }),
                        Err(err) => json!({ "err": err.to_string() }),
                    };
                    bridge.send(&reply)?;
                }
            }
        }
    }
}

/// Perform one syscall on behalf of a Python agent.
fn service(ctx: &mut Ctx<'_>, op: &str, request: &Value) -> Result<Value> {
    match op {
        "generate" => {
            let prompt = request["prompt"].as_str().unwrap_or_default();
            let response = ctx.generate(prompt)?;
            Ok(json!({
                "text": response.text,
                "tokens_used": response.tokens_used,
            }))
        }
        "send" => {
            let to = address_from_json(&request["to"])?;
            let kind = request["kind"].as_str().unwrap_or("message");
            ctx.send(to, kind, request["payload"].clone());
            Ok(Value::Null)
        }
        "spawn" => {
            let id = ctx.spawn(spec_from_json(&request["spec"])?)?;
            Ok(json!({ "agent_id": id.0 }))
        }
        "call_tool" => {
            let name = request["name"]
                .as_str()
                .ok_or_else(|| Error::Bridge("call_tool needs a 'name'".into()))?;
            ctx.call_tool(name, &request["args"])
        }
        "subscribe" => {
            let topic = request["topic"]
                .as_str()
                .ok_or_else(|| Error::Bridge("subscribe needs a 'topic'".into()))?;
            ctx.subscribe(topic);
            Ok(Value::Null)
        }
        "suspend_self" => {
            ctx.suspend_self();
            Ok(Value::Null)
        }
        other => Err(Error::Bridge(format!("unknown syscall '{other}'"))),
    }
}

fn envelope_json(msg: &Envelope) -> Value {
    json!({
        "seq": msg.seq,
        "kind": msg.kind,
        "payload": msg.payload,
        "from": match msg.from {
            Sender::System => json!({ "type": "system" }),
            Sender::Agent(id) => json!({ "type": "agent", "id": id.0 }),
        },
    })
}

fn address_from_json(value: &Value) -> Result<Address> {
    match value["type"].as_str() {
        Some("agent") => value["id"]
            .as_u64()
            .map(|id| Address::Agent(AgentId(id)))
            .ok_or_else(|| Error::Bridge("agent address needs a numeric 'id'".into())),
        Some("topic") => value["name"]
            .as_str()
            .map(|name| Address::Topic(name.to_string()))
            .ok_or_else(|| Error::Bridge("topic address needs a 'name'".into())),
        _ => Err(Error::Bridge(format!("unroutable address: {value}"))),
    }
}

fn spec_from_json(value: &Value) -> Result<SpawnSpec> {
    let kind = value["kind"]
        .as_str()
        .ok_or_else(|| Error::InvalidSpawn("spec needs a 'kind'".into()))?;
    let name = value["name"].as_str().unwrap_or(kind);
    let mut spec = SpawnSpec::new(kind, name);

    // A missing/null max_tokens means "unlimited" — the kernel refuses that
    // grant from a bounded parent, which is where conservation is enforced.
    if let Some(max) = value["max_tokens"].as_u64() {
        spec = spec.budget(Budget::with_max_tokens(max));
    }
    if let Some(caps) = value["caps"].as_array() {
        let mut set = CapabilitySet::new();
        for cap in caps.iter().filter_map(Value::as_str) {
            set = set.grant(cap);
        }
        spec = spec.caps(set);
    }
    if let Some(topics) = value["topics"].as_array() {
        for topic in topics.iter().filter_map(Value::as_str) {
            spec = spec.topic(topic);
        }
    }
    if !value["init"].is_null() {
        spec = spec.init(value["init"].clone());
    }
    Ok(spec)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spec_defaults_to_unlimited_and_named_after_its_kind() {
        let spec = spec_from_json(&json!({ "kind": "worker" })).unwrap();
        assert_eq!(spec.kind, "worker");
        assert_eq!(spec.name, "worker");
        assert_eq!(spec.budget.max_tokens, None);
    }

    #[test]
    fn spec_reads_grant_caps_and_topics() {
        let spec = spec_from_json(&json!({
            "kind": "worker",
            "name": "w0",
            "max_tokens": 250,
            "caps": ["tool.echo"],
            "topics": ["news"],
        }))
        .unwrap();
        assert_eq!(spec.budget.max_tokens, Some(250));
        assert!(spec.caps.allows("tool.echo"));
        assert_eq!(spec.topics, vec!["news".to_string()]);
    }

    #[test]
    fn addresses_round_trip_both_forms() {
        assert_eq!(
            address_from_json(&json!({"type": "agent", "id": 4})).unwrap(),
            Address::Agent(AgentId(4))
        );
        assert_eq!(
            address_from_json(&json!({"type": "topic", "name": "news"})).unwrap(),
            Address::Topic("news".into())
        );
        assert!(address_from_json(&json!({"type": "nowhere"})).is_err());
    }
}
