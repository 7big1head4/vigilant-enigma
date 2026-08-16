// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

use std::fmt;

use crate::agent::AgentId;

/// Every failure the kernel can surface. Agents receive these from `Ctx`
/// calls; an error returned from `Agent::on_message` kills the agent (the
/// kernel itself never crashes on agent failure).
#[derive(Debug)]
pub enum Error {
    BudgetExhausted {
        agent: AgentId,
        needed: u64,
        remaining: u64,
    },
    PermissionDenied {
        tool: String,
        capability: String,
    },
    InvalidSpawn(String),
    UnknownAgent(AgentId),
    UnknownKind(String),
    UnknownTool(String),
    Model(String),
    Tool(String),
    Io(std::io::Error),
    Serde(serde_json::Error),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::BudgetExhausted {
                agent,
                needed,
                remaining,
            } => write!(
                f,
                "budget exhausted for {agent}: needed {needed} tokens, {remaining} remaining"
            ),
            Error::PermissionDenied { tool, capability } => {
                write!(
                    f,
                    "permission denied: tool '{tool}' requires capability '{capability}'"
                )
            }
            Error::InvalidSpawn(reason) => write!(f, "invalid spawn: {reason}"),
            Error::UnknownAgent(id) => write!(f, "unknown agent {id}"),
            Error::UnknownKind(kind) => write!(f, "unknown agent kind '{kind}'"),
            Error::UnknownTool(name) => write!(f, "unknown tool '{name}'"),
            Error::Model(msg) => write!(f, "model backend error: {msg}"),
            Error::Tool(msg) => write!(f, "tool error: {msg}"),
            Error::Io(err) => write!(f, "io error: {err}"),
            Error::Serde(err) => write!(f, "serialization error: {err}"),
        }
    }
}

impl std::error::Error for Error {}

impl From<std::io::Error> for Error {
    fn from(err: std::io::Error) -> Self {
        Error::Io(err)
    }
}

impl From<serde_json::Error> for Error {
    fn from(err: serde_json::Error) -> Self {
        Error::Serde(err)
    }
}

pub type Result<T> = std::result::Result<T, Error>;
