// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Per-agent persistent key-value memory. This is what makes suspension
/// cheap: an agent's identity lives here (and in its snapshot), not in a
/// resident process. Persisted to disk on suspend and shutdown.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct Memory {
    entries: serde_json::Map<String, Value>,
}

impl Memory {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn get(&self, key: &str) -> Option<&Value> {
        self.entries.get(key)
    }

    pub fn set(&mut self, key: &str, value: Value) {
        self.entries.insert(key.to_string(), value);
    }

    pub fn remove(&mut self, key: &str) -> Option<Value> {
        self.entries.remove(key)
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Borrow the whole store — used to hand memory to a Python agent.
    pub fn as_map(&self) -> &serde_json::Map<String, Value> {
        &self.entries
    }

    /// Replace the whole store. A Python agent mutates memory as a plain
    /// dict and returns it wholesale when its handler finishes.
    pub fn replace(&mut self, entries: serde_json::Map<String, Value>) {
        self.entries = entries;
    }

    /// Convenience for counters: read an integer, defaulting to 0.
    pub fn get_u64(&self, key: &str) -> u64 {
        self.get(key).and_then(Value::as_u64).unwrap_or(0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn round_trips_through_json() {
        let mut m = Memory::new();
        m.set("count", json!(3));
        m.set("peer", json!("agent-7"));
        let text = serde_json::to_string(&m).unwrap();
        let back: Memory = serde_json::from_str(&text).unwrap();
        assert_eq!(back.get_u64("count"), 3);
        assert_eq!(back.get("peer"), Some(&json!("agent-7")));
    }
}
