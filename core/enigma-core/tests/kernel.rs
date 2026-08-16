// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

//! Integration tests for the kernel's OS-like guarantees: pub/sub IPC,
//! the permission gate, suspend/resume with wake-on-message, persistence
//! across kernel restarts, budget enforcement, and budget-conserving
//! sub-agent spawning. No mocks in the product path — the model trait is
//! implemented here by a deterministic test backend, and the real Ollama
//! HTTP client is tested against a real TCP server in `ollama_http.rs`.

use serde_json::{json, Value};

use enigma_core::{
    Address, Agent, AgentState, Budget, CapabilitySet, Ctx, Envelope, Error, Kernel, KernelConfig,
    Memory, ModelBackend, ModelRequest, ModelResponse, Result, SpawnSpec,
};

/// Deterministic backend: always answers with a fixed cost. Lets tests
/// assert exact budget arithmetic.
struct FixedModel {
    cost: u64,
}

impl ModelBackend for FixedModel {
    fn name(&self) -> &str {
        "fixed"
    }

    fn generate(&mut self, req: &ModelRequest) -> Result<ModelResponse> {
        Ok(ModelResponse {
            text: format!("answer to: {}", req.prompt),
            tokens_used: self.cost,
        })
    }
}

fn kernel_in(dir: &std::path::Path, cost: u64) -> Kernel {
    Kernel::new(
        KernelConfig::new(dir.to_path_buf()),
        Box::new(FixedModel { cost }),
    )
    .expect("kernel construction")
}

fn tmp_dir(name: &str) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("enigma-test-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

/// Counts every message it sees into memory.
struct Counter;

impl Agent for Counter {
    fn on_message(&mut self, ctx: &mut Ctx<'_>, _msg: &Envelope) -> Result<()> {
        let n = ctx.memory.get_u64("count") + 1;
        ctx.memory.set("count", json!(n));
        Ok(())
    }
}

#[test]
fn topic_pubsub_delivers_to_all_subscribers() {
    let dir = tmp_dir("pubsub");
    let mut kernel = kernel_in(&dir, 1);
    kernel.register_kind("counter", |_| Box::new(Counter));

    let a = kernel
        .spawn(SpawnSpec::new("counter", "a").topic("news"))
        .unwrap();
    let b = kernel
        .spawn(SpawnSpec::new("counter", "b").topic("news"))
        .unwrap();
    let c = kernel.spawn(SpawnSpec::new("counter", "c")).unwrap(); // not subscribed

    kernel.post(Address::Topic("news".into()), "event", json!({}));
    kernel.post(Address::Topic("news".into()), "event", json!({}));
    kernel.run_until_idle().unwrap();

    assert_eq!(kernel.memory_of(a).unwrap().get_u64("count"), 2);
    assert_eq!(kernel.memory_of(b).unwrap().get_u64("count"), 2);
    assert_eq!(kernel.memory_of(c).unwrap().get_u64("count"), 0);
}

/// Calls the echo tool once, storing the result.
struct ToolUser;

impl Agent for ToolUser {
    fn on_message(&mut self, ctx: &mut Ctx<'_>, msg: &Envelope) -> Result<()> {
        let result = ctx.call_tool("echo", &msg.payload)?;
        ctx.memory.set("result", result);
        Ok(())
    }
}

#[test]
fn permission_gate_blocks_and_allows() {
    let dir = tmp_dir("perms");
    let mut kernel = kernel_in(&dir, 1);
    kernel
        .tools_mut()
        .register(Box::new(enigma_core::tools::EchoTool));
    kernel.register_kind("tooluser", |_| Box::new(ToolUser));

    let denied = kernel.spawn(SpawnSpec::new("tooluser", "denied")).unwrap();
    let allowed = kernel
        .spawn(SpawnSpec::new("tooluser", "allowed").caps(CapabilitySet::new().grant("tool.echo")))
        .unwrap();

    kernel.post(Address::Agent(denied), "go", json!("hi"));
    kernel.post(Address::Agent(allowed), "go", json!("hi"));
    kernel.run_until_idle().unwrap();

    // The denied agent's tool error killed it — and only it.
    match kernel.state(denied).unwrap() {
        AgentState::Dead { reason } => assert!(reason.contains("permission denied")),
        other => panic!("expected dead, got {other:?}"),
    }
    assert_eq!(kernel.state(allowed).unwrap(), &AgentState::Running);
    assert_eq!(
        kernel.memory_of(allowed).unwrap().get("result"),
        Some(&json!("hi"))
    );
}

#[test]
fn suspended_agent_wakes_on_message_with_memory_intact() {
    let dir = tmp_dir("wake");
    let mut kernel = kernel_in(&dir, 1);
    kernel.register_kind("counter", |_| Box::new(Counter));

    let id = kernel.spawn(SpawnSpec::new("counter", "sleeper")).unwrap();
    kernel.post(Address::Agent(id), "tick", json!({}));
    kernel.post(Address::Agent(id), "tick", json!({}));
    kernel.run_until_idle().unwrap();

    kernel.suspend(id).unwrap();
    assert_eq!(kernel.state(id).unwrap(), &AgentState::Suspended);

    // Message to a suspended agent wakes it; count continues from 2.
    kernel.post(Address::Agent(id), "tick", json!({}));
    kernel.run_until_idle().unwrap();
    assert_eq!(kernel.state(id).unwrap(), &AgentState::Running);
    assert_eq!(kernel.memory_of(id).unwrap().get_u64("count"), 3);
}

#[test]
fn suspended_agents_survive_kernel_restart() {
    let dir = tmp_dir("restart");

    let id = {
        let mut kernel = kernel_in(&dir, 1);
        kernel.register_kind("counter", |_| Box::new(Counter));
        let id = kernel.spawn(SpawnSpec::new("counter", "phoenix")).unwrap();
        kernel.post(Address::Agent(id), "tick", json!({}));
        kernel.post(Address::Agent(id), "tick", json!({}));
        kernel.run_until_idle().unwrap();
        kernel.shutdown().unwrap();
        id
    };

    // A brand-new kernel over the same state_dir sees the agent, and a
    // message wakes it with its memory intact.
    let mut kernel = kernel_in(&dir, 1);
    kernel.register_kind("counter", |_| Box::new(Counter));
    assert_eq!(kernel.state(id).unwrap(), &AgentState::Suspended);

    kernel.post(Address::Agent(id), "tick", json!({}));
    kernel.run_until_idle().unwrap();
    assert_eq!(kernel.memory_of(id).unwrap().get_u64("count"), 3);
}

/// Generates on every message; used to exhaust budgets.
struct Generator;

impl Agent for Generator {
    fn on_message(&mut self, ctx: &mut Ctx<'_>, _msg: &Envelope) -> Result<()> {
        let response = ctx.generate("work")?;
        let n = ctx.memory.get_u64("generations") + 1;
        ctx.memory.set("generations", json!(n));
        ctx.memory.set("last", json!(response.text));
        Ok(())
    }
}

#[test]
fn budget_exhaustion_kills_the_agent_not_the_kernel() {
    let dir = tmp_dir("budget");
    let mut kernel = kernel_in(&dir, 10); // 10 tokens per generate
    kernel.register_kind("generator", |_| Box::new(Generator));

    let id = kernel
        .spawn(SpawnSpec::new("generator", "spender").budget(Budget::with_max_tokens(25)))
        .unwrap();
    for _ in 0..5 {
        kernel.post(Address::Agent(id), "work", json!({}));
    }
    kernel.run_until_idle().unwrap();

    // 25-token budget, 10 per call: two generations succeed, the third kills.
    assert_eq!(kernel.memory_of(id).unwrap().get_u64("generations"), 2);
    match kernel.state(id).unwrap() {
        AgentState::Dead { reason } => assert!(reason.contains("budget exhausted")),
        other => panic!("expected dead, got {other:?}"),
    }
    // Kernel is still healthy: remaining messages were dropped, not fatal.
    assert!(kernel.stats().dropped >= 2);
}

/// Spawns one child per "grow" message, granting it a fixed budget; the
/// child then answers a "task" with one generation.
struct Spawner;

impl Agent for Spawner {
    fn on_message(&mut self, ctx: &mut Ctx<'_>, msg: &Envelope) -> Result<()> {
        match msg.kind.as_str() {
            "grow" => {
                let grant = msg.payload["grant"].as_u64().unwrap_or(20);
                let child = ctx.spawn(
                    SpawnSpec::new("spawner", &format!("child-of-{}", ctx.agent_id))
                        .budget(Budget::with_max_tokens(grant)),
                )?;
                ctx.memory.set("child", json!(child.0));
                ctx.send(Address::Agent(child), "task", json!({}));
            }
            "task" => {
                let response = ctx.generate("do the thing")?;
                ctx.memory.set("answer", json!(response.text));
            }
            _ => {}
        }
        Ok(())
    }
}

#[test]
fn spawning_transfers_budget_from_parent() {
    let dir = tmp_dir("spawn");
    let mut kernel = kernel_in(&dir, 10);
    kernel.register_kind("spawner", |_| Box::new(Spawner));

    let parent = kernel
        .spawn(SpawnSpec::new("spawner", "parent").budget(Budget::with_max_tokens(100)))
        .unwrap();
    kernel.post(Address::Agent(parent), "grow", json!({ "grant": 60 }));
    kernel.run_until_idle().unwrap();

    // The 60-token grant moved from parent to child at spawn time.
    let parent_budget = kernel.budget_of(parent).unwrap();
    assert_eq!(parent_budget.used_tokens, 60);
    assert_eq!(parent_budget.remaining(), Some(40));

    let child = enigma_core::AgentId(kernel.memory_of(parent).unwrap().get_u64("child"));
    let child_budget = kernel.budget_of(child).unwrap();
    assert_eq!(child_budget.max_tokens, Some(60));
    assert_eq!(child_budget.used_tokens, 10); // one generation
    assert_eq!(
        kernel.memory_of(child).unwrap().get("answer"),
        Some(&json!("answer to: do the thing"))
    );
}

#[test]
fn sub_agents_can_nest_without_limit_but_tokens_conserve() {
    let dir = tmp_dir("nest");
    let mut kernel = kernel_in(&dir, 1);
    kernel.register_kind("spawner", |_| Box::new(Spawner));

    // parent(100) -> child(50) -> grandchild(20): three generations happen,
    // and no agent's spend escapes the root's original 100.
    let root = kernel
        .spawn(SpawnSpec::new("spawner", "root").budget(Budget::with_max_tokens(100)))
        .unwrap();
    kernel.post(Address::Agent(root), "grow", json!({ "grant": 50 }));
    kernel.run_until_idle().unwrap();
    let child = enigma_core::AgentId(kernel.memory_of(root).unwrap().get_u64("child"));

    kernel.post(Address::Agent(child), "grow", json!({ "grant": 20 }));
    kernel.run_until_idle().unwrap();
    let grandchild = enigma_core::AgentId(kernel.memory_of(child).unwrap().get_u64("child"));

    assert!(matches!(
        kernel.state(grandchild).unwrap(),
        AgentState::Running
    ));
    let root_spend = kernel.budget_of(root).unwrap().used_tokens; // 50 granted
    assert_eq!(root_spend, 50);
    assert_eq!(kernel.budget_of(child).unwrap().used_tokens, 20 + 1); // grant + own generate
    assert_eq!(kernel.budget_of(grandchild).unwrap().used_tokens, 1);
}

#[test]
fn bounded_agent_cannot_grant_unlimited_budget() {
    let dir = tmp_dir("nogrant");
    let mut kernel = kernel_in(&dir, 1);

    struct BadSpawner;
    impl Agent for BadSpawner {
        fn on_message(&mut self, ctx: &mut Ctx<'_>, _msg: &Envelope) -> Result<()> {
            // Unlimited child from a bounded parent must be refused.
            match ctx.spawn(SpawnSpec::new("bad", "escape")) {
                Err(Error::InvalidSpawn(_)) => Ok(()),
                Err(other) => panic!("wrong error: {other}"),
                Ok(_) => panic!("unlimited grant from bounded parent must fail"),
            }
        }
    }

    kernel.register_kind("bad", |_| Box::new(BadSpawner));
    let id = kernel
        .spawn(SpawnSpec::new("bad", "bounded").budget(Budget::with_max_tokens(10)))
        .unwrap();
    kernel.post(Address::Agent(id), "go", json!({}));
    kernel.run_until_idle().unwrap();
    assert_eq!(kernel.state(id).unwrap(), &AgentState::Running);
}

#[test]
fn over_granting_fails_and_charges_nothing() {
    let dir = tmp_dir("overgrant");
    let mut kernel = kernel_in(&dir, 1);

    struct Greedy;
    impl Agent for Greedy {
        fn on_message(&mut self, ctx: &mut Ctx<'_>, _msg: &Envelope) -> Result<()> {
            let result = ctx
                .spawn(SpawnSpec::new("greedy", "too-big").budget(Budget::with_max_tokens(1000)));
            assert!(matches!(result, Err(Error::BudgetExhausted { .. })));
            Ok(())
        }
    }

    kernel.register_kind("greedy", |_| Box::new(Greedy));
    let id = kernel
        .spawn(SpawnSpec::new("greedy", "parent").budget(Budget::with_max_tokens(100)))
        .unwrap();
    kernel.post(Address::Agent(id), "go", json!({}));
    kernel.run_until_idle().unwrap();

    // Failed grant left the budget untouched.
    assert_eq!(kernel.budget_of(id).unwrap().used_tokens, 0);
}

#[test]
fn status_report_counts_states_and_streams_to_disk() {
    let dir = tmp_dir("status");
    let mut kernel = kernel_in(&dir, 1);
    kernel.register_kind("counter", |_| Box::new(Counter));

    let a = kernel.spawn(SpawnSpec::new("counter", "a")).unwrap();
    let _b = kernel.spawn(SpawnSpec::new("counter", "b")).unwrap();
    kernel.suspend(a).unwrap();
    kernel.kill(enigma_core::AgentId(999), "no such agent"); // no-op, no panic

    let status = kernel.status();
    assert_eq!(status.agents.len(), 2);
    let states: Vec<_> = status.agents.iter().map(|a| &a.state).collect();
    assert!(states.contains(&&AgentState::Suspended));
    assert!(states.contains(&&AgentState::Running));

    kernel.write_status().unwrap();
    let raw = std::fs::read(dir.join("status.json")).unwrap();
    let parsed: Value = serde_json::from_slice(&raw).unwrap();
    assert_eq!(parsed["agents"].as_array().unwrap().len(), 2);
}

#[test]
fn run_until_idle_leaves_fresh_status_on_disk() {
    // The live-streaming contract: after any run that delivered messages,
    // status.json on disk reflects the settled state without an explicit
    // write_status/shutdown call.
    let dir = tmp_dir("livestatus");
    let mut kernel = kernel_in(&dir, 1);
    kernel.register_kind("counter", |_| Box::new(Counter));
    let id = kernel.spawn(SpawnSpec::new("counter", "obs")).unwrap();
    kernel.post(Address::Agent(id), "tick", json!({}));
    kernel.run_until_idle().unwrap();

    let raw = std::fs::read(dir.join("status.json")).unwrap();
    let parsed: Value = serde_json::from_slice(&raw).unwrap();
    assert_eq!(parsed["agents"][0]["name"], json!("obs"));
    assert_eq!(parsed["stats"]["dispatched"], json!(1));
}

#[test]
fn memory_is_the_identity_not_the_instance() {
    // The recommended agent pattern keeps all state in ctx.memory; this
    // asserts Memory itself round-trips faithfully through serialization.
    let mut memory = Memory::new();
    memory.set("plan", json!({ "steps": ["a", "b"], "done": 1 }));
    let text = serde_json::to_string(&memory).unwrap();
    let back: Memory = serde_json::from_str(&text).unwrap();
    assert_eq!(back.get("plan"), memory.get("plan"));
}
