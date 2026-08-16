// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

//! End-to-end tests for Python agents: a real `python3` worker process
//! running the real SDK, driven by a real kernel. Nothing here is mocked —
//! the deterministic model backend is the only stand-in, so budget
//! arithmetic can be asserted exactly.

use std::path::{Path, PathBuf};
use std::process::Command;

use serde_json::json;

use enigma_core::{
    register_python_kinds, Address, AgentId, AgentState, Budget, CapabilitySet, Kernel,
    KernelConfig, ModelBackend, ModelRequest, ModelResponse, PythonBridge, Result, SpawnSpec,
};

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

fn repo_root() -> PathBuf {
    // CARGO_MANIFEST_DIR is core/enigma-core.
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}

fn tmp_dir(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("enigma-py-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    dir
}

/// A kernel with the test agent module loaded over the bridge.
fn kernel_with_python(dir: &Path, cost: u64) -> Kernel {
    let root = repo_root();
    let mut command = Command::new(std::env::var("ENIGMA_PYTHON").unwrap_or("python3".into()));
    command
        .arg("-m")
        .arg("enigma_sdk")
        .arg("bridge_agents")
        .env("PYTHONPATH", root.join("sdk/python"))
        .current_dir(root.join("core/enigma-core/tests/py"));

    let bridge = PythonBridge::spawn(command).expect("python worker starts");
    let mut kernel = Kernel::new(
        KernelConfig::new(dir.to_path_buf()),
        Box::new(FixedModel { cost }),
    )
    .expect("kernel");
    register_python_kinds(&mut kernel, &bridge).expect("kinds registered");
    // The bridge outlives the kernel through the Arc the agents hold.
    kernel
}

#[test]
fn python_agent_memory_survives_the_round_trip() {
    let dir = tmp_dir("memory");
    let mut kernel = kernel_with_python(&dir, 1);

    let id = kernel
        .spawn(SpawnSpec::new("counter", "py-counter"))
        .unwrap();
    kernel.post(Address::Agent(id), "tick", json!({}));
    kernel.post(Address::Agent(id), "tock", json!({}));
    kernel.run_until_idle().unwrap();

    let memory = kernel.memory_of(id).unwrap();
    assert_eq!(memory.get_u64("count"), 2);
    assert_eq!(memory.get("last_kind"), Some(&json!("tock")));
}

#[test]
fn python_generate_is_charged_to_the_agents_budget() {
    let dir = tmp_dir("generate");
    let mut kernel = kernel_with_python(&dir, 30);

    let id = kernel
        .spawn(SpawnSpec::new("thinker", "py-thinker").budget(Budget::with_max_tokens(100)))
        .unwrap();
    kernel.post(
        Address::Agent(id),
        "task",
        json!({ "prompt": "why is the sky blue" }),
    );
    kernel.run_until_idle().unwrap();

    assert_eq!(
        kernel.memory_of(id).unwrap().get("answer"),
        Some(&json!("answer to: why is the sky blue"))
    );
    assert_eq!(kernel.memory_of(id).unwrap().get_u64("tokens"), 30);
    assert_eq!(kernel.budget_of(id).unwrap().used_tokens, 30);
}

#[test]
fn python_agent_spawns_sub_agents_and_budgets_conserve() {
    let dir = tmp_dir("spawn");
    let mut kernel = kernel_with_python(&dir, 10);

    let boss = kernel
        .spawn(SpawnSpec::new("boss", "py-boss").budget(Budget::with_max_tokens(500)))
        .unwrap();
    kernel.post(
        Address::Agent(boss),
        "start",
        json!({ "children": 3, "grant": 100 }),
    );
    kernel.run_until_idle().unwrap();

    // Three 100-token grants moved out of the boss's own budget.
    assert_eq!(kernel.budget_of(boss).unwrap().used_tokens, 300);
    assert_eq!(kernel.budget_of(boss).unwrap().remaining(), Some(200));

    let children = kernel
        .memory_of(boss)
        .unwrap()
        .get("children")
        .unwrap()
        .clone();
    let children = children.as_array().unwrap();
    assert_eq!(children.len(), 3);
    for child in children {
        let id = AgentId(child.as_u64().unwrap());
        let budget = kernel.budget_of(id).unwrap();
        assert_eq!(budget.max_tokens, Some(100));
        assert_eq!(budget.used_tokens, 10); // one generation each
        assert!(kernel.memory_of(id).unwrap().get("answer").is_some());
    }
}

#[test]
fn python_agent_exceeding_its_budget_is_killed_not_the_kernel() {
    let dir = tmp_dir("overspend");
    let mut kernel = kernel_with_python(&dir, 40);

    let id = kernel
        .spawn(SpawnSpec::new("thinker", "py-broke").budget(Budget::with_max_tokens(10)))
        .unwrap();
    kernel.post(Address::Agent(id), "task", json!({ "prompt": "expensive" }));
    kernel.run_until_idle().unwrap();

    match kernel.state(id).unwrap() {
        AgentState::Dead { reason } => {
            assert!(reason.contains("budget exhausted"), "reason: {reason}")
        }
        other => panic!("expected dead, got {other:?}"),
    }

    // The kernel is fine: another Python agent still runs afterwards.
    let survivor = kernel.spawn(SpawnSpec::new("counter", "after")).unwrap();
    kernel.post(Address::Agent(survivor), "tick", json!({}));
    kernel.run_until_idle().unwrap();
    assert_eq!(kernel.memory_of(survivor).unwrap().get_u64("count"), 1);
}

#[test]
fn permission_gate_applies_to_python_agents() {
    let dir = tmp_dir("perms");
    let mut kernel = kernel_with_python(&dir, 1);
    kernel
        .tools_mut()
        .register(Box::new(enigma_core::tools::EchoTool));

    let denied = kernel.spawn(SpawnSpec::new("toolo", "denied")).unwrap();
    let allowed = kernel
        .spawn(SpawnSpec::new("toolo", "allowed").caps(CapabilitySet::new().grant("tool.echo")))
        .unwrap();
    kernel.post(Address::Agent(denied), "go", json!({ "hi": true }));
    kernel.post(Address::Agent(allowed), "go", json!({ "hi": true }));
    kernel.run_until_idle().unwrap();

    // Python caught EnigmaError and recorded it, so the agent survives.
    let refusal = kernel
        .memory_of(denied)
        .unwrap()
        .get("denied")
        .unwrap()
        .clone();
    assert!(
        refusal.as_str().unwrap().contains("permission denied"),
        "got: {refusal}"
    );
    assert_eq!(kernel.state(denied).unwrap(), &AgentState::Running);
    assert_eq!(
        kernel.memory_of(allowed).unwrap().get("echoed"),
        Some(&json!({ "hi": true }))
    );
}

#[test]
fn python_agent_suspends_and_wakes_with_memory_intact() {
    let dir = tmp_dir("suspend");
    let mut kernel = kernel_with_python(&dir, 1);

    let id = kernel.spawn(SpawnSpec::new("napper", "py-napper")).unwrap();
    kernel.post(Address::Agent(id), "nap", json!({}));
    kernel.run_until_idle().unwrap();
    assert_eq!(kernel.state(id).unwrap(), &AgentState::Suspended);

    // Waking is just another message; the Python side rebuilds from memory.
    kernel.post(Address::Agent(id), "nap", json!({}));
    kernel.run_until_idle().unwrap();
    assert_eq!(kernel.memory_of(id).unwrap().get_u64("naps"), 2);
    assert_eq!(kernel.state(id).unwrap(), &AgentState::Suspended);
}

#[test]
fn raising_python_agent_is_killed_with_its_exception_as_the_reason() {
    let dir = tmp_dir("explode");
    let mut kernel = kernel_with_python(&dir, 1);

    let bomb = kernel.spawn(SpawnSpec::new("exploder", "py-bomb")).unwrap();
    kernel.post(Address::Agent(bomb), "go", json!({}));
    kernel.run_until_idle().unwrap();

    match kernel.state(bomb).unwrap() {
        AgentState::Dead { reason } => {
            assert!(reason.contains("ValueError"), "reason: {reason}");
            assert!(reason.contains("boom from python"), "reason: {reason}");
        }
        other => panic!("expected dead, got {other:?}"),
    }

    // The worker process survived one agent's exception.
    let survivor = kernel.spawn(SpawnSpec::new("counter", "after")).unwrap();
    kernel.post(Address::Agent(survivor), "tick", json!({}));
    kernel.run_until_idle().unwrap();
    assert_eq!(kernel.memory_of(survivor).unwrap().get_u64("count"), 1);
}

#[test]
fn python_agents_use_the_topic_bus() {
    let dir = tmp_dir("topics");
    let mut kernel = kernel_with_python(&dir, 1);

    // One subscribes at spawn, the other subscribes at runtime.
    let eager = kernel
        .spawn(SpawnSpec::new("listener", "eager").topic("news"))
        .unwrap();
    let latecomer = kernel.spawn(SpawnSpec::new("listener", "late")).unwrap();

    kernel.post(Address::Topic("news".into()), "headline", json!({}));
    kernel.run_until_idle().unwrap();

    kernel.post(
        Address::Agent(latecomer),
        "join",
        json!({ "topic": "news" }),
    );
    kernel.run_until_idle().unwrap();
    kernel.post(Address::Topic("news".into()), "headline", json!({}));
    kernel.run_until_idle().unwrap();

    assert_eq!(kernel.memory_of(eager).unwrap().get_u64("heard"), 2);
    assert_eq!(kernel.memory_of(latecomer).unwrap().get_u64("heard"), 1);
}

#[test]
fn unknown_kind_from_python_is_reported_not_crashed() {
    let dir = tmp_dir("unknown");
    let mut kernel = kernel_with_python(&dir, 1);

    // 'ghost' is not registered in the Python module.
    let ghost = kernel.spawn(SpawnSpec::new("ghost", "missing")).unwrap();
    match kernel.state(ghost).unwrap() {
        AgentState::Dead { reason } => assert!(reason.contains("unknown agent kind")),
        other => panic!("expected dead, got {other:?}"),
    }
}
