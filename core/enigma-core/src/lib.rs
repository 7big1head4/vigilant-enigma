// Enigma core — the runtime kernel of an agentic operating system.
//
// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later
//
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation; either version 2 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

//! Enigma gives AI agents what an operating system gives processes:
//! scheduling, memory, capabilities, and communication.
//!
//! The kernel is a deterministic, single-threaded event loop — light enough
//! to idle near zero on a Raspberry Pi 5. Agents are woken by messages,
//! charged for the tokens they spend, suspended to disk when idle, and can
//! spawn unlimited sub-agents (token grants transfer from the parent's
//! budget, so spawning never escapes budget enforcement). While the loop
//! runs it streams `status.json` to the state directory so observers (the
//! dashboard) can watch agents live.

pub mod agent;
pub mod budget;
pub mod bus;
pub mod error;
pub mod kernel;
pub mod memory;
pub mod model;
pub mod permissions;
pub mod tools;

pub use agent::{Agent, AgentId, AgentState};
pub use budget::Budget;
pub use bus::{Address, Envelope, Sender};
pub use error::{Error, Result};
pub use kernel::{Ctx, Kernel, KernelConfig, SpawnSpec, StatusReport};
pub use memory::Memory;
pub use model::{ModelBackend, ModelRequest, ModelResponse, OllamaBackend};
pub use permissions::CapabilitySet;
pub use tools::{Tool, ToolRegistry};
