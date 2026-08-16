// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

use std::collections::BTreeSet;

use serde::{Deserialize, Serialize};

/// The syscall boundary: agents hold capabilities, tools require them.
/// An agent without the right capability cannot invoke a tool, full stop.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapabilitySet(BTreeSet<String>);

impl CapabilitySet {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn grant(mut self, capability: &str) -> Self {
        self.0.insert(capability.to_string());
        self
    }

    pub fn allows(&self, capability: &str) -> bool {
        self.0.contains(capability)
    }

    pub fn iter(&self) -> impl Iterator<Item = &str> {
        self.0.iter().map(String::as_str)
    }
}

impl FromIterator<String> for CapabilitySet {
    fn from_iter<T: IntoIterator<Item = String>>(iter: T) -> Self {
        CapabilitySet(iter.into_iter().collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn grant_and_check() {
        let caps = CapabilitySet::new().grant("tool.echo");
        assert!(caps.allows("tool.echo"));
        assert!(!caps.allows("tool.shell"));
    }
}
