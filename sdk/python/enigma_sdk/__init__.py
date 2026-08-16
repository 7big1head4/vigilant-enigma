# Copyright (C) 2026 the Enigma authors
# SPDX-License-Identifier: GPL-2.0-or-later

"""Enigma Python SDK — write agents for the Enigma agentic operating system.

Agents are plain Python classes. The Rust kernel schedules them, charges
their token budgets, persists their memory, and suspends them when idle;
this SDK is how you write one.

    from enigma_sdk import Agent, agent

    @agent("greeter")
    class Greeter(Agent):
        def on_message(self, ctx, msg):
            answer = ctx.generate("Say hello to %s" % msg.payload["name"])
            ctx.memory["greeted"] = ctx.memory.get("greeted", 0) + 1
            if msg.from_agent is not None:
                ctx.send_to(msg.from_agent, "result", {"text": answer.text})
            ctx.suspend_self()

Run the module that defines your agents as a worker:

    python3 -m enigma_sdk my_agents

The kernel spawns that command itself (see ``core/enigma-core/src/bridge.rs``);
running it by hand is only useful to check that a module imports and
registers the kinds you expect.

Standard library only — no dependencies, nothing to build on a Pi.
"""

from .context import Context
from .core import REGISTRY, Agent, EnigmaError, Generation, Message, agent
from .worker import PROTOCOL_VERSION, serve

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "Context",
    "EnigmaError",
    "Generation",
    "Message",
    "PROTOCOL_VERSION",
    "REGISTRY",
    "agent",
    "serve",
    "__version__",
]
