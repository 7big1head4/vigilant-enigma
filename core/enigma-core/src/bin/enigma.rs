// Enigma CLI — run and observe the agent kernel.
//
// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later
//
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation; either version 2 of the License, or
// (at your option) any later version.

use std::process::{Command, ExitCode};

use serde_json::{json, Value};

use enigma_core::{
    register_python_kinds, Address, Agent, Budget, Ctx, Envelope, Kernel, KernelConfig,
    OllamaBackend, PythonBridge, Result, SpawnSpec,
};

/// Demo orchestrator: spawns `workers` sub-agents (each with a token grant
/// transferred from its own budget), hands each a prompt, and collects the
/// answers in memory.
struct Orchestrator;

impl Agent for Orchestrator {
    fn on_message(&mut self, ctx: &mut Ctx<'_>, msg: &Envelope) -> Result<()> {
        match msg.kind.as_str() {
            "start" => {
                let workers = msg.payload["workers"].as_u64().unwrap_or(2);
                let grant = msg.payload["grant"].as_u64().unwrap_or(300);
                let prompts = [
                    "In one short sentence: what does an operating system scheduler do?",
                    "In one short sentence: why do computers use virtual memory?",
                    "In one short sentence: what is inter-process communication?",
                    "In one short sentence: what is a system call?",
                ];
                ctx.memory.set("expected", json!(workers));
                for i in 0..workers {
                    let child = ctx.spawn(
                        SpawnSpec::new("worker", &format!("worker-{i}"))
                            .budget(Budget::with_max_tokens(grant)),
                    )?;
                    println!("[orchestrator] spawned {child} (grant: {grant} tokens)");
                    ctx.send(
                        Address::Agent(child),
                        "task",
                        json!({ "prompt": prompts[i as usize % prompts.len()] }),
                    );
                }
            }
            "result" => {
                let done = ctx.memory.get_u64("done") + 1;
                ctx.memory.set("done", json!(done));
                println!(
                    "[orchestrator] result {done}: {}",
                    msg.payload["text"].as_str().unwrap_or("<none>").trim()
                );
                if done >= ctx.memory.get_u64("expected") {
                    println!("[orchestrator] all results in — suspending myself");
                    ctx.suspend_self();
                }
            }
            _ => {}
        }
        Ok(())
    }
}

/// Demo worker: answers one prompt with the local model, reports back, and
/// asks to be suspended (it costs nothing until someone wakes it again).
struct Worker;

impl Agent for Worker {
    fn on_message(&mut self, ctx: &mut Ctx<'_>, msg: &Envelope) -> Result<()> {
        if msg.kind == "task" {
            let prompt = msg.payload["prompt"].as_str().unwrap_or("Say hello.");
            let response = ctx.generate(prompt)?;
            println!(
                "[{}] {} tokens: {}",
                ctx.agent_id,
                response.tokens_used,
                response.text.trim()
            );
            if let enigma_core::Sender::Agent(parent) = msg.from {
                ctx.send(
                    Address::Agent(parent),
                    "result",
                    json!({ "text": response.text }),
                );
            }
            ctx.suspend_self();
        }
        Ok(())
    }
}

fn demo(args: &[String]) -> Result<()> {
    let workers = flag_value(args, "--workers").unwrap_or(2);
    let grant = flag_value(args, "--grant").unwrap_or(300);

    let backend = OllamaBackend::from_env();
    println!(
        "Enigma demo — model '{}' via ollama, {workers} workers, {grant} tokens each",
        backend.model()
    );

    let mut kernel = Kernel::new(KernelConfig::from_env(), Box::new(backend))?;
    kernel.register_kind("orchestrator", |_| Box::new(Orchestrator));
    kernel.register_kind("worker", |_| Box::new(Worker));

    let orchestrator = kernel.spawn(
        SpawnSpec::new("orchestrator", "orchestrator")
            .budget(Budget::with_max_tokens(grant * workers + 100)),
    )?;
    kernel.post(
        Address::Agent(orchestrator),
        "start",
        json!({ "workers": workers, "grant": grant }),
    );
    kernel.run_until_idle()?;
    kernel.shutdown()?;

    println!("\n--- final status ---");
    print_status(&serde_json::to_value(kernel.status()).map_err(enigma_core::Error::Serde)?);
    Ok(())
}

/// Same demo, but the agents are written in Python (see `examples/agents.py`).
/// The kernel spawns a worker process and schedules its agents exactly like
/// native ones — budgets, capabilities, and suspension all still apply.
fn py_demo(args: &[String]) -> Result<()> {
    let topics = flag_value(args, "--topics").unwrap_or(3);
    let grant = flag_value(args, "--grant").unwrap_or(300);

    let python = env_or("ENIGMA_PYTHON", "python3");
    let sdk_path = env_or("ENIGMA_SDK_PATH", "sdk/python");
    let module_dir = env_or("ENIGMA_PYTHON_DIR", "examples");
    let module = env_or("ENIGMA_PYTHON_MODULE", "agents");

    // Pass the module as a path and leave the working directory alone, so a
    // relative ENIGMA_SDK_PATH still resolves from where the user ran us.
    let mut command = Command::new(&python);
    command
        .arg("-m")
        .arg("enigma_sdk")
        .arg(format!("{module_dir}/{module}.py"))
        .env("PYTHONPATH", &sdk_path);

    let backend = OllamaBackend::from_env();
    println!(
        "Enigma python demo — model '{}' via ollama, agents from {module_dir}/{module}.py",
        backend.model()
    );

    let bridge = PythonBridge::spawn(command)?;
    let mut kernel = Kernel::new(KernelConfig::from_env(), Box::new(backend))?;
    register_python_kinds(&mut kernel, &bridge)?;
    {
        let guard = bridge
            .lock()
            .map_err(|_| enigma_core::Error::Bridge("bridge mutex poisoned".into()))?;
        println!("python worker ready — kinds: {}", guard.kinds().join(", "));
    }

    let researcher = kernel.spawn(
        SpawnSpec::new("researcher", "researcher")
            .budget(Budget::with_max_tokens(grant * topics + 200)),
    )?;
    kernel.post(
        Address::Agent(researcher),
        "start",
        json!({ "topics": topics, "grant": grant }),
    );
    kernel.run_until_idle()?;
    kernel.shutdown()?;

    println!("\n--- final status ---");
    print_status(&serde_json::to_value(kernel.status()).map_err(enigma_core::Error::Serde)?);
    Ok(())
}

fn env_or(key: &str, fallback: &str) -> String {
    std::env::var(key).unwrap_or_else(|_| fallback.to_string())
}

fn status() -> Result<()> {
    let path = KernelConfig::from_env().state_dir.join("status.json");
    let raw = std::fs::read(&path).map_err(|e| {
        enigma_core::Error::Model(format!(
            "cannot read {} ({e}) — has a kernel run on this machine?",
            path.display()
        ))
    })?;
    let value: Value = serde_json::from_slice(&raw)?;
    print_status(&value);
    Ok(())
}

fn print_status(status: &Value) {
    let agents = status["agents"].as_array().cloned().unwrap_or_default();
    let count = |s: &str| {
        agents
            .iter()
            .filter(|a| a["state"]["state"] == json!(s))
            .count()
    };
    println!(
        "{} agents — {} running, {} suspended, {} dead · {} messages dispatched",
        agents.len(),
        count("running"),
        count("suspended"),
        count("dead"),
        status["stats"]["dispatched"].as_u64().unwrap_or(0),
    );
    for a in &agents {
        let state = a["state"]["state"].as_str().unwrap_or("?");
        let reason = a["state"]["reason"].as_str().unwrap_or("");
        let budget = match a["token_budget"].as_u64() {
            Some(max) => format!("{}/{max} tokens", a["tokens_used"].as_u64().unwrap_or(0)),
            None => format!(
                "{} tokens (unlimited)",
                a["tokens_used"].as_u64().unwrap_or(0)
            ),
        };
        println!(
            "  agent-{} {:<14} [{}] {} {}{}",
            a["id"],
            a["name"].as_str().unwrap_or("?"),
            a["kind"].as_str().unwrap_or("?"),
            state,
            budget,
            if reason.is_empty() {
                String::new()
            } else {
                format!(" — {reason}")
            }
        );
    }
}

fn flag_value(args: &[String], flag: &str) -> Option<u64> {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1))
        .and_then(|v| v.parse().ok())
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let result = match args.first().map(String::as_str) {
        Some("demo") => demo(&args),
        Some("py-demo") => py_demo(&args),
        Some("status") => status(),
        _ => {
            eprintln!(
                "usage: enigma <command>\n\n\
                 commands:\n  \
                 demo [--workers N] [--grant TOKENS]    Rust sub-agent demo (needs ollama)\n  \
                 py-demo [--topics N] [--grant TOKENS]  same, with Python agents\n  \
                 status                                 show the last kernel status\n\n\
                 env: ENIGMA_STATE_DIR, ENIGMA_OLLAMA_ADDR, ENIGMA_OLLAMA_MODEL,\n     \
                 ENIGMA_PYTHON, ENIGMA_SDK_PATH, ENIGMA_PYTHON_DIR, ENIGMA_PYTHON_MODULE\n\n\
                 py-demo expects to run from the repository root."
            );
            return ExitCode::from(2);
        }
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("error: {err}");
            ExitCode::FAILURE
        }
    }
}
