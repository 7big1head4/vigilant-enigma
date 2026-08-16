# Copyright (C) 2026 the Enigma authors
# SPDX-License-Identifier: GPL-2.0-or-later

"""The syscall surface handed to a Python agent while it handles a message.

Every method here is a round trip into the Rust kernel: the call is written
to the protocol channel, the kernel services it (charging budgets, checking
capabilities), and the reply comes back before the method returns. A refused
syscall raises :class:`~enigma_sdk.core.EnigmaError`.
"""

from .core import EnigmaError, Generation


class Context:
    """Per-dispatch capability handle. Do not keep a reference past
    ``on_message`` — it is only valid during the delivery."""

    def __init__(self, agent_id, memory, channel):
        self.agent_id = agent_id
        #: Durable per-agent store (plain dict). The kernel persists whatever
        #: this holds when the handler returns, and it survives suspension.
        self.memory = memory
        self._channel = channel

    def _syscall(self, **payload):
        reply = self._channel.call(payload)
        err = reply.get("err")
        if err is not None:
            raise EnigmaError(err)
        return reply.get("ok")

    def generate(self, prompt):
        """Run the model. Tokens are charged to this agent's budget.

        Raises :class:`EnigmaError` if the budget cannot cover the call.
        """
        result = self._syscall(op="generate", prompt=prompt) or {}
        return Generation(result.get("text", ""), result.get("tokens_used", 0))

    def send_to(self, agent_id, kind, payload=None):
        """Send a message to one agent. Wakes it if it is suspended."""
        self._syscall(
            op="send",
            to={"type": "agent", "id": int(agent_id)},
            kind=kind,
            payload=payload,
        )

    def publish(self, topic, kind, payload=None):
        """Publish to a topic — every subscriber receives it."""
        self._syscall(
            op="send",
            to={"type": "topic", "name": topic},
            kind=kind,
            payload=payload,
        )

    def spawn(self, kind, name=None, max_tokens=None, caps=(), topics=(), init=None):
        """Spawn a sub-agent and return its id.

        There is no limit on how many sub-agents an agent may spawn, or how
        deeply they nest — but a ``max_tokens`` grant is *transferred* from
        this agent's own budget, and an agent with a bounded budget cannot
        grant an unlimited one. Spawning never mints tokens, so a tree of
        agents can never outspend what its root was given.

        Raises :class:`EnigmaError` if this agent cannot afford the grant.
        """
        result = self._syscall(
            op="spawn",
            spec={
                "kind": kind,
                "name": name or kind,
                "max_tokens": max_tokens,
                "caps": list(caps),
                "topics": list(topics),
                "init": init,
            },
        )
        return (result or {}).get("agent_id")

    def call_tool(self, name, args=None):
        """Invoke a kernel tool. Requires the tool's capability."""
        return self._syscall(op="call_tool", name=name, args=args)

    def subscribe(self, topic):
        """Subscribe this agent to a topic."""
        self._syscall(op="subscribe", topic=topic)

    def suspend_self(self):
        """Ask the kernel to suspend this agent once the handler returns.

        A suspended agent costs nothing until a message wakes it.
        """
        self._syscall(op="suspend_self")

    def __repr__(self):
        return "<Context agent-%s>" % self.agent_id
