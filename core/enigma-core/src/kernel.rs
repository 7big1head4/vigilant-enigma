// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

//! The kernel: a deterministic, single-threaded event loop that schedules
//! agents the way an OS schedules processes.
//!
//! Design invariants (see CLAUDE.md):
//! - **Budgets are conserved.** Token grants to sub-agents are charged to
//!   the parent at spawn time; a tree of agents can never spend more than
//!   its root was given.
//! - **Suspension is the default.** A suspended agent holds no instance in
//!   memory; any message addressed to it wakes it (resume-on-message).
//! - **Agent failure never kills the kernel.** An error from `on_message`
//!   kills that agent and records the reason.
//! - **Live observability.** While the loop runs, `status.json` is
//!   re-written at most every `status_interval` so external observers (the
//!   dashboard) can watch agents spawn, suspend, and die in real time.

use std::collections::{BTreeMap, HashMap, VecDeque};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::agent::{Agent, AgentFactory, AgentId, AgentState};
use crate::budget::Budget;
use crate::bus::{Address, Envelope, Sender};
use crate::error::{Error, Result};
use crate::memory::Memory;
use crate::model::{ModelBackend, ModelRequest, ModelResponse};
use crate::permissions::CapabilitySet;
use crate::tools::ToolRegistry;

#[derive(Clone, Debug)]
pub struct KernelConfig {
    /// Where suspended agents, the manifest, and status.json live.
    pub state_dir: PathBuf,
    /// Minimum interval between live status.json writes during a run.
    /// `None` disables live streaming (status is still written on
    /// `shutdown` and explicit `write_status` calls).
    pub status_interval: Option<Duration>,
}

impl KernelConfig {
    pub fn new(state_dir: PathBuf) -> Self {
        KernelConfig {
            state_dir,
            status_interval: Some(Duration::from_millis(250)),
        }
    }

    /// `ENIGMA_STATE_DIR` or `~/.enigma`.
    pub fn from_env() -> Self {
        let dir = std::env::var("ENIGMA_STATE_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(|_| {
                let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
                Path::new(&home).join(".enigma")
            });
        Self::new(dir)
    }
}

/// Everything needed to create an agent.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SpawnSpec {
    /// Registered kind (factory) name.
    pub kind: String,
    /// Human-readable name, shown in status.
    pub name: String,
    pub budget: Budget,
    pub caps: CapabilitySet,
    /// Topics to subscribe to from birth.
    pub topics: Vec<String>,
    /// Initial state passed to the factory.
    pub init: Value,
}

impl SpawnSpec {
    pub fn new(kind: &str, name: &str) -> Self {
        SpawnSpec {
            kind: kind.to_string(),
            name: name.to_string(),
            budget: Budget::unlimited(),
            caps: CapabilitySet::new(),
            topics: Vec::new(),
            init: Value::Null,
        }
    }

    pub fn budget(mut self, budget: Budget) -> Self {
        self.budget = budget;
        self
    }

    pub fn caps(mut self, caps: CapabilitySet) -> Self {
        self.caps = caps;
        self
    }

    pub fn topic(mut self, topic: &str) -> Self {
        self.topics.push(topic.to_string());
        self
    }

    pub fn init(mut self, init: Value) -> Self {
        self.init = init;
        self
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AgentMeta {
    pub id: AgentId,
    pub name: String,
    pub kind: String,
    pub state: AgentState,
    pub parent: Option<AgentId>,
    pub caps: CapabilitySet,
    pub budget: Budget,
    pub topics: Vec<String>,
}

struct Slot {
    meta: AgentMeta,
    memory: Memory,
    /// Latest snapshot, kept for resume; refreshed at suspend.
    saved: Value,
    /// `None` while suspended or dead.
    instance: Option<Box<dyn Agent>>,
}

/// On-disk form of a suspended agent.
#[derive(Serialize, Deserialize)]
struct SerializedAgent {
    meta: AgentMeta,
    memory: Memory,
    snapshot: Value,
}

#[derive(Serialize, Deserialize, Default)]
struct Manifest {
    next_id: u64,
    next_seq: u64,
}

#[derive(Clone, Debug, Default, Serialize)]
pub struct KernelStats {
    pub dispatched: u64,
    /// Messages addressed to missing or dead agents.
    pub dropped: u64,
}

#[derive(Serialize)]
pub struct AgentStatus {
    pub id: u64,
    pub name: String,
    pub kind: String,
    pub state: AgentState,
    pub parent: Option<u64>,
    pub tokens_used: u64,
    pub token_budget: Option<u64>,
}

#[derive(Serialize)]
pub struct StatusReport {
    pub updated: u64,
    pub stats: KernelStats,
    pub agents: Vec<AgentStatus>,
}

enum CtrlRequest {
    Spawn {
        id: AgentId,
        parent: AgentId,
        spec: SpawnSpec,
    },
    SuspendSelf,
}

struct Outgoing {
    to: Address,
    kind: String,
    payload: Value,
}

/// The capability surface handed to an agent while it handles a message.
pub struct Ctx<'a> {
    pub agent_id: AgentId,
    pub memory: &'a mut Memory,
    meta: &'a mut AgentMeta,
    model: &'a mut dyn ModelBackend,
    tools: &'a ToolRegistry,
    outbox: &'a mut Vec<Outgoing>,
    requests: &'a mut Vec<CtrlRequest>,
    next_id: &'a mut u64,
}

impl Ctx<'_> {
    /// Queue a message; it is delivered after this handler returns.
    pub fn send(&mut self, to: Address, kind: &str, payload: Value) {
        self.outbox.push(Outgoing {
            to,
            kind: kind.to_string(),
            payload,
        });
    }

    /// Run the model and charge this agent's budget for the tokens used.
    pub fn generate(&mut self, prompt: &str) -> Result<ModelResponse> {
        let response = self.model.generate(&ModelRequest {
            agent: self.agent_id,
            prompt: prompt.to_string(),
        })?;
        self.meta
            .budget
            .try_charge(response.tokens_used)
            .map_err(|remaining| Error::BudgetExhausted {
                agent: self.agent_id,
                needed: response.tokens_used,
                remaining,
            })?;
        Ok(response)
    }

    /// Invoke a tool through the permission gate.
    pub fn call_tool(&mut self, name: &str, args: &Value) -> Result<Value> {
        self.tools.invoke(&self.meta.caps, name, args)
    }

    /// Spawn a sub-agent. There is no limit on how many sub-agents an
    /// agent may create — but a bounded token grant is *transferred* from
    /// this agent's budget, and a bounded agent cannot grant an unlimited
    /// budget, so spawning never mints new tokens.
    pub fn spawn(&mut self, spec: SpawnSpec) -> Result<AgentId> {
        match (self.meta.budget.max_tokens, spec.budget.max_tokens) {
            (Some(_), None) => {
                return Err(Error::InvalidSpawn(format!(
                    "{} has a bounded budget and cannot grant an unlimited one",
                    self.agent_id
                )))
            }
            (_, Some(grant)) => {
                self.meta
                    .budget
                    .try_charge(grant)
                    .map_err(|remaining| Error::BudgetExhausted {
                        agent: self.agent_id,
                        needed: grant,
                        remaining,
                    })?;
            }
            (None, None) => {}
        }
        *self.next_id += 1;
        let id = AgentId(*self.next_id);
        self.requests.push(CtrlRequest::Spawn {
            id,
            parent: self.agent_id,
            spec,
        });
        Ok(id)
    }

    /// Ask the kernel to suspend this agent after the current message.
    pub fn suspend_self(&mut self) {
        self.requests.push(CtrlRequest::SuspendSelf);
    }

    pub fn subscribe(&mut self, topic: &str) {
        if !self.meta.topics.iter().any(|t| t == topic) {
            self.meta.topics.push(topic.to_string());
        }
    }
}

pub struct Kernel {
    cfg: KernelConfig,
    factories: HashMap<String, AgentFactory>,
    slots: BTreeMap<AgentId, Slot>,
    queue: VecDeque<Envelope>,
    next_id: u64,
    next_seq: u64,
    model: Box<dyn ModelBackend>,
    tools: ToolRegistry,
    stats: KernelStats,
    last_status: Instant,
}

impl Kernel {
    /// Create a kernel over `state_dir`, restoring any suspended agents a
    /// previous kernel left there. Factories must be re-registered before
    /// those agents can wake.
    pub fn new(cfg: KernelConfig, model: Box<dyn ModelBackend>) -> Result<Self> {
        fs::create_dir_all(cfg.state_dir.join("agents"))?;
        let mut kernel = Kernel {
            cfg,
            factories: HashMap::new(),
            slots: BTreeMap::new(),
            queue: VecDeque::new(),
            next_id: 0,
            next_seq: 0,
            model,
            tools: ToolRegistry::new(),
            stats: KernelStats::default(),
            last_status: Instant::now(),
        };
        kernel.load_state()?;
        Ok(kernel)
    }

    pub fn register_kind<F>(&mut self, kind: &str, factory: F)
    where
        F: Fn(&Value) -> Box<dyn Agent> + Send + 'static,
    {
        self.factories.insert(kind.to_string(), Box::new(factory));
    }

    pub fn tools_mut(&mut self) -> &mut ToolRegistry {
        &mut self.tools
    }

    /// Spawn a root agent (no parent; nothing is charged — this is the
    /// system handing out an allowance).
    pub fn spawn(&mut self, spec: SpawnSpec) -> Result<AgentId> {
        self.next_id += 1;
        let id = AgentId(self.next_id);
        self.materialize(id, None, spec);
        Ok(id)
    }

    fn materialize(&mut self, id: AgentId, parent: Option<AgentId>, spec: SpawnSpec) {
        let (state, instance) = match self.factories.get(&spec.kind) {
            Some(factory) => (AgentState::Running, Some(factory(&spec.init))),
            None => (
                AgentState::Dead {
                    reason: format!("unknown agent kind '{}'", spec.kind),
                },
                None,
            ),
        };
        let slot = Slot {
            meta: AgentMeta {
                id,
                name: spec.name,
                kind: spec.kind,
                state,
                parent,
                caps: spec.caps,
                budget: spec.budget,
                topics: spec.topics,
            },
            memory: Memory::new(),
            saved: spec.init,
            instance,
        };
        self.slots.insert(id, slot);
    }

    /// Inject a message from outside the agent world.
    pub fn post(&mut self, to: Address, kind: &str, payload: Value) {
        self.enqueue(Sender::System, to, kind.to_string(), payload);
    }

    fn enqueue(&mut self, from: Sender, to: Address, kind: String, payload: Value) {
        self.next_seq += 1;
        self.queue.push_back(Envelope {
            seq: self.next_seq,
            from,
            to,
            kind,
            payload,
        });
    }

    /// Drain the queue, dispatching every message (and the messages those
    /// dispatches produce) until nothing is left. Returns how many
    /// deliveries were made. Deterministic: same inputs, same order.
    /// Streams status.json (throttled) so observers see progress live.
    pub fn run_until_idle(&mut self) -> Result<u64> {
        let mut delivered = 0;
        while let Some(env) = self.queue.pop_front() {
            let targets: Vec<AgentId> = match &env.to {
                Address::Agent(id) => vec![*id],
                Address::Topic(topic) => self
                    .slots
                    .values()
                    .filter(|s| {
                        s.meta.topics.iter().any(|t| t == topic)
                            && !matches!(s.meta.state, AgentState::Dead { .. })
                    })
                    .map(|s| s.meta.id)
                    .collect(),
            };
            for id in targets {
                delivered += self.deliver(id, &env)?;
            }
            self.stream_status();
        }
        if delivered > 0 {
            // Final write so observers see the settled state immediately.
            let _ = self.write_status();
            self.last_status = Instant::now();
        }
        Ok(delivered)
    }

    /// Best-effort throttled status write during a run — telemetry must
    /// never fail the loop.
    fn stream_status(&mut self) {
        if let Some(interval) = self.cfg.status_interval {
            if self.last_status.elapsed() >= interval {
                let _ = self.write_status();
                self.last_status = Instant::now();
            }
        }
    }

    /// Deliver one envelope to one agent; returns 1 if a handler ran.
    fn deliver(&mut self, id: AgentId, env: &Envelope) -> Result<u64> {
        match self.slots.get(&id) {
            None => {
                self.stats.dropped += 1;
                return Ok(0);
            }
            Some(slot) => match slot.meta.state {
                AgentState::Dead { .. } => {
                    self.stats.dropped += 1;
                    return Ok(0);
                }
                AgentState::Suspended => self.resume(id)?,
                AgentState::Running => {}
            },
        }

        let mut instance = match self.slots.get_mut(&id).and_then(|s| s.instance.take()) {
            Some(instance) => instance,
            None => {
                self.stats.dropped += 1;
                return Ok(0);
            }
        };

        let mut outbox: Vec<Outgoing> = Vec::new();
        let mut requests: Vec<CtrlRequest> = Vec::new();
        let result = {
            let Kernel {
                slots,
                model,
                tools,
                next_id,
                ..
            } = self;
            let slot = slots.get_mut(&id).expect("slot exists during dispatch");
            let mut ctx = Ctx {
                agent_id: id,
                memory: &mut slot.memory,
                meta: &mut slot.meta,
                model: model.as_mut(),
                tools,
                outbox: &mut outbox,
                requests: &mut requests,
                next_id,
            };
            instance.on_message(&mut ctx, env)
        };
        self.stats.dispatched += 1;

        match result {
            Err(err) => {
                // Agent failure is contained: record it, keep the kernel up.
                self.kill(id, &err.to_string());
            }
            Ok(()) => {
                let mut suspend_after = false;
                for request in requests {
                    match request {
                        CtrlRequest::Spawn { id, parent, spec } => {
                            self.materialize(id, Some(parent), spec);
                        }
                        CtrlRequest::SuspendSelf => suspend_after = true,
                    }
                }
                if suspend_after {
                    self.suspend_instance(id, instance)?;
                } else if let Some(slot) = self.slots.get_mut(&id) {
                    if matches!(slot.meta.state, AgentState::Running) {
                        slot.instance = Some(instance);
                    }
                }
                for out in outbox {
                    self.enqueue(Sender::Agent(id), out.to, out.kind, out.payload);
                }
            }
        }
        Ok(1)
    }

    /// Suspend a running agent: snapshot + memory go to disk, the instance
    /// is dropped. Costs nothing while suspended; any message wakes it.
    pub fn suspend(&mut self, id: AgentId) -> Result<()> {
        let slot = self.slots.get_mut(&id).ok_or(Error::UnknownAgent(id))?;
        if !matches!(slot.meta.state, AgentState::Running) {
            return Ok(());
        }
        match slot.instance.take() {
            Some(instance) => self.suspend_instance(id, instance),
            None => Ok(()),
        }
    }

    fn suspend_instance(&mut self, id: AgentId, instance: Box<dyn Agent>) -> Result<()> {
        let slot = self.slots.get_mut(&id).ok_or(Error::UnknownAgent(id))?;
        slot.saved = instance.snapshot();
        slot.meta.state = AgentState::Suspended;
        drop(instance);
        let record = SerializedAgent {
            meta: slot.meta.clone(),
            memory: slot.memory.clone(),
            snapshot: slot.saved.clone(),
        };
        let path = self.agent_path(id);
        fs::write(path, serde_json::to_vec_pretty(&record)?)?;
        Ok(())
    }

    fn resume(&mut self, id: AgentId) -> Result<()> {
        let kind = self
            .slots
            .get(&id)
            .ok_or(Error::UnknownAgent(id))?
            .meta
            .kind
            .clone();
        if !self.factories.contains_key(&kind) {
            self.kill(id, &format!("cannot wake: unknown agent kind '{kind}'"));
            return Ok(());
        }
        let path = self.agent_path(id);
        let Kernel {
            slots, factories, ..
        } = self;
        let slot = slots.get_mut(&id).expect("checked above");
        let factory = factories.get(&kind).expect("checked above");
        slot.instance = Some(factory(&slot.saved));
        slot.meta.state = AgentState::Running;
        let _ = fs::remove_file(path);
        Ok(())
    }

    pub fn kill(&mut self, id: AgentId, reason: &str) {
        if let Some(slot) = self.slots.get_mut(&id) {
            slot.meta.state = AgentState::Dead {
                reason: reason.to_string(),
            };
            slot.instance = None;
            let _ = fs::remove_file(self.agent_path(id));
        }
    }

    pub fn suspend_all(&mut self) -> Result<()> {
        let running: Vec<AgentId> = self
            .slots
            .values()
            .filter(|s| matches!(s.meta.state, AgentState::Running))
            .map(|s| s.meta.id)
            .collect();
        for id in running {
            self.suspend(id)?;
        }
        Ok(())
    }

    /// Suspend everything, persist the manifest, write status.json.
    /// The next kernel over the same state_dir picks up where this left off.
    pub fn shutdown(&mut self) -> Result<()> {
        self.suspend_all()?;
        let manifest = Manifest {
            next_id: self.next_id,
            next_seq: self.next_seq,
        };
        fs::write(
            self.cfg.state_dir.join("manifest.json"),
            serde_json::to_vec_pretty(&manifest)?,
        )?;
        self.write_status()?;
        Ok(())
    }

    fn load_state(&mut self) -> Result<()> {
        let manifest_path = self.cfg.state_dir.join("manifest.json");
        if let Ok(raw) = fs::read(&manifest_path) {
            let manifest: Manifest = serde_json::from_slice(&raw)?;
            self.next_id = manifest.next_id;
            self.next_seq = manifest.next_seq;
        }
        let agents_dir = self.cfg.state_dir.join("agents");
        let entries = match fs::read_dir(&agents_dir) {
            Ok(entries) => entries,
            Err(_) => return Ok(()),
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) != Some("json") {
                continue;
            }
            let record: SerializedAgent = serde_json::from_slice(&fs::read(&path)?)?;
            let id = record.meta.id;
            let mut meta = record.meta;
            meta.state = AgentState::Suspended;
            self.next_id = self.next_id.max(id.0);
            self.slots.insert(
                id,
                Slot {
                    meta,
                    memory: record.memory,
                    saved: record.snapshot,
                    instance: None,
                },
            );
        }
        Ok(())
    }

    fn agent_path(&self, id: AgentId) -> PathBuf {
        self.cfg
            .state_dir
            .join("agents")
            .join(format!("agent-{}.json", id.0))
    }

    pub fn state(&self, id: AgentId) -> Option<&AgentState> {
        self.slots.get(&id).map(|s| &s.meta.state)
    }

    pub fn memory_of(&self, id: AgentId) -> Option<&Memory> {
        self.slots.get(&id).map(|s| &s.memory)
    }

    pub fn budget_of(&self, id: AgentId) -> Option<&Budget> {
        self.slots.get(&id).map(|s| &s.meta.budget)
    }

    pub fn stats(&self) -> &KernelStats {
        &self.stats
    }

    pub fn status(&self) -> StatusReport {
        StatusReport {
            updated: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
            stats: self.stats.clone(),
            agents: self
                .slots
                .values()
                .map(|s| AgentStatus {
                    id: s.meta.id.0,
                    name: s.meta.name.clone(),
                    kind: s.meta.kind.clone(),
                    state: s.meta.state.clone(),
                    parent: s.meta.parent.map(|p| p.0),
                    tokens_used: s.meta.budget.used_tokens,
                    token_budget: s.meta.budget.max_tokens,
                })
                .collect(),
        }
    }

    /// Write status.json for external observers (e.g. the dashboard).
    pub fn write_status(&self) -> Result<()> {
        let path = self.cfg.state_dir.join("status.json");
        fs::write(path, serde_json::to_vec_pretty(&self.status())?)?;
        Ok(())
    }
}
