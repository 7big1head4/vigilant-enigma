// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

use std::fmt;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::bus::Envelope;
use crate::error::Result;
use crate::kernel::Ctx;

/// Kernel-assigned agent identity (the "pid").
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct AgentId(pub u64);

impl fmt::Display for AgentId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "agent-{}", self.0)
    }
}

/// The process model. `Suspended` agents hold no instance in memory —
/// their snapshot and memory live on disk until a message wakes them.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "state", rename_all = "snake_case")]
pub enum AgentState {
    Running,
    Suspended,
    Dead { reason: String },
}

/// What an agent implementation provides. Agents are event-driven: they
/// only run while handling a message, and everything they need — sending,
/// generating, tools, memory, spawning — comes through the [`Ctx`].
///
/// Returning an error kills the agent (the kernel records the reason and
/// keeps running). State that must survive suspension goes in `snapshot`;
/// the agent's factory rebuilds the instance from that value on resume.
pub trait Agent: Send {
    fn on_message(&mut self, ctx: &mut Ctx<'_>, msg: &Envelope) -> Result<()>;

    /// Serialize instance state for suspension. `Value::Null` if the agent
    /// keeps everything in `ctx.memory` (the recommended pattern).
    fn snapshot(&self) -> Value {
        Value::Null
    }
}

/// Builds an agent instance from a state value — the same function serves
/// initial spawn (from `SpawnSpec::init`) and resume (from the snapshot).
pub type AgentFactory = Box<dyn Fn(&Value) -> Box<dyn Agent> + Send>;
