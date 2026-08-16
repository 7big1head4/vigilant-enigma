// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::agent::AgentId;

/// Who a message came from.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Sender {
    /// The kernel or an external caller (CLI, host program).
    System,
    Agent(AgentId),
}

/// Where a message is going: a single agent, or every subscriber of a topic.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum Address {
    Agent(AgentId),
    Topic(String),
}

/// The IPC unit. Delivery to a suspended agent wakes it (resume-on-message);
/// delivery to a dead agent is silently dropped.
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Envelope {
    /// Kernel-assigned, strictly increasing. Gives every delivery a total
    /// order for logging and deterministic tests.
    pub seq: u64,
    pub from: Sender,
    pub to: Address,
    /// Application-level message type, e.g. "task", "result".
    pub kind: String,
    pub payload: Value,
}
