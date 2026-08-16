// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

use serde::{Deserialize, Serialize};

/// "ulimit for agents": token spend is a schedulable, conserved resource.
///
/// `max_tokens: None` means unlimited. Grants to sub-agents are charged
/// against the parent's budget at spawn time, so the sum of tokens a tree
/// of agents can spend never exceeds what the root was given.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Budget {
    pub max_tokens: Option<u64>,
    pub used_tokens: u64,
}

impl Budget {
    pub fn unlimited() -> Self {
        Budget {
            max_tokens: None,
            used_tokens: 0,
        }
    }

    pub fn with_max_tokens(max: u64) -> Self {
        Budget {
            max_tokens: Some(max),
            used_tokens: 0,
        }
    }

    /// Tokens still spendable, or `None` for unlimited.
    pub fn remaining(&self) -> Option<u64> {
        self.max_tokens
            .map(|max| max.saturating_sub(self.used_tokens))
    }

    /// Charge `n` tokens. On failure returns the number remaining and
    /// leaves the budget untouched.
    pub fn try_charge(&mut self, n: u64) -> std::result::Result<(), u64> {
        match self.remaining() {
            Some(remaining) if remaining < n => Err(remaining),
            _ => {
                self.used_tokens += n;
                Ok(())
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn charge_within_budget() {
        let mut b = Budget::with_max_tokens(10);
        assert!(b.try_charge(4).is_ok());
        assert!(b.try_charge(6).is_ok());
        assert_eq!(b.remaining(), Some(0));
    }

    #[test]
    fn charge_over_budget_fails_and_preserves_state() {
        let mut b = Budget::with_max_tokens(5);
        assert!(b.try_charge(3).is_ok());
        assert_eq!(b.try_charge(3), Err(2));
        assert_eq!(b.used_tokens, 3);
    }

    #[test]
    fn unlimited_never_fails() {
        let mut b = Budget::unlimited();
        assert!(b.try_charge(u64::MAX).is_ok());
        assert_eq!(b.remaining(), None);
    }
}
