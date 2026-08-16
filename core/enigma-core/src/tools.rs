// Copyright (C) 2026 the Enigma authors
// SPDX-License-Identifier: GPL-2.0-or-later

use std::collections::HashMap;

use serde_json::Value;

use crate::error::{Error, Result};
use crate::permissions::CapabilitySet;

/// A capability-gated system call. Tools are the only way agents touch the
/// world outside the kernel; every invocation crosses the permission check
/// in [`ToolRegistry::invoke`].
pub trait Tool: Send {
    fn name(&self) -> &str;
    /// Capability an agent must hold to call this tool.
    fn capability(&self) -> &str;
    fn call(&self, args: &Value) -> Result<Value>;
}

#[derive(Default)]
pub struct ToolRegistry {
    tools: HashMap<String, Box<dyn Tool>>,
}

impl ToolRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, tool: Box<dyn Tool>) {
        self.tools.insert(tool.name().to_string(), tool);
    }

    /// The permission gate. Unknown tool and missing capability are
    /// distinct errors so an agent (or its parent) can tell them apart.
    pub fn invoke(&self, caps: &CapabilitySet, name: &str, args: &Value) -> Result<Value> {
        let tool = self
            .tools
            .get(name)
            .ok_or_else(|| Error::UnknownTool(name.to_string()))?;
        if !caps.allows(tool.capability()) {
            return Err(Error::PermissionDenied {
                tool: name.to_string(),
                capability: tool.capability().to_string(),
            });
        }
        tool.call(args)
    }
}

/// Trivial built-in tool, mainly useful for exercising the permission
/// layer: returns its arguments unchanged. Requires `tool.echo`.
pub struct EchoTool;

impl Tool for EchoTool {
    fn name(&self) -> &str {
        "echo"
    }

    fn capability(&self) -> &str {
        "tool.echo"
    }

    fn call(&self, args: &Value) -> Result<Value> {
        Ok(args.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn invoke_checks_capability() {
        let mut reg = ToolRegistry::new();
        reg.register(Box::new(EchoTool));

        let no_caps = CapabilitySet::new();
        assert!(matches!(
            reg.invoke(&no_caps, "echo", &json!(1)),
            Err(Error::PermissionDenied { .. })
        ));

        let caps = CapabilitySet::new().grant("tool.echo");
        assert_eq!(reg.invoke(&caps, "echo", &json!(1)).unwrap(), json!(1));
    }

    #[test]
    fn unknown_tool_is_distinct_error() {
        let reg = ToolRegistry::new();
        assert!(matches!(
            reg.invoke(&CapabilitySet::new(), "nope", &json!(null)),
            Err(Error::UnknownTool(_))
        ));
    }
}
