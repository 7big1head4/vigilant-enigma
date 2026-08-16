# Copyright (C) 2026 the Enigma authors
# SPDX-License-Identifier: GPL-2.0-or-later

"""Agents used by the Rust bridge integration test (tests/python_bridge.rs).

Deliberately small and deterministic — each one exercises one syscall path
so a Rust assertion can pin down exactly what crossed the bridge.
"""

from enigma_sdk import Agent, EnigmaError, agent


@agent("counter")
class Counter(Agent):
    """Memory round trip: state survives in ctx.memory, not on self."""

    def on_message(self, ctx, msg):
        ctx.memory["count"] = ctx.memory.get("count", 0) + 1
        ctx.memory["last_kind"] = msg.kind


@agent("thinker")
class Thinker(Agent):
    """Model call, budget-charged by the kernel."""

    def on_message(self, ctx, msg):
        result = ctx.generate(msg.payload["prompt"])
        ctx.memory["answer"] = result.text
        ctx.memory["tokens"] = result.tokens_used


@agent("boss")
class Boss(Agent):
    """Unlimited sub-agents: spawns N children, each with a token grant
    transferred from its own budget, then fans work out to them."""

    def on_message(self, ctx, msg):
        if msg.kind == "start":
            children = []
            for i in range(msg.payload["children"]):
                child = ctx.spawn(
                    "thinker",
                    name="thinker-%d" % i,
                    max_tokens=msg.payload["grant"],
                )
                children.append(child)
                ctx.send_to(child, "task", {"prompt": "question %d" % i})
            ctx.memory["children"] = children
        elif msg.kind == "result":
            ctx.memory["results"] = ctx.memory.get("results", 0) + 1


@agent("toolo")
class ToolUser(Agent):
    """Capability gate: a denied tool raises EnigmaError in Python."""

    def on_message(self, ctx, msg):
        try:
            ctx.memory["echoed"] = ctx.call_tool("echo", msg.payload)
        except EnigmaError as exc:
            ctx.memory["denied"] = str(exc)


@agent("napper")
class Napper(Agent):
    """Suspends itself; the kernel should persist and later wake it."""

    def on_message(self, ctx, msg):
        ctx.memory["naps"] = ctx.memory.get("naps", 0) + 1
        ctx.suspend_self()


@agent("exploder")
class Exploder(Agent):
    """Raises — the kernel must kill this agent and keep running."""

    def on_message(self, ctx, msg):
        raise ValueError("boom from python")


@agent("listener")
class Listener(Agent):
    """Subscribes at runtime, then counts topic traffic."""

    def on_message(self, ctx, msg):
        if msg.kind == "join":
            ctx.subscribe(msg.payload["topic"])
            ctx.memory["joined"] = True
        else:
            ctx.memory["heard"] = ctx.memory.get("heard", 0) + 1
