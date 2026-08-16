# Copyright (C) 2026 the Enigma authors
# SPDX-License-Identifier: GPL-2.0-or-later

"""Core types for Enigma agents: the base class, the kind registry, and the
values an agent receives and returns.

Nothing here talks to the kernel — that is :mod:`enigma_sdk.context` (the
syscall surface) and :mod:`enigma_sdk.worker` (the protocol loop).
"""

REGISTRY = {}


class EnigmaError(Exception):
    """A syscall the kernel refused.

    Raised by ``ctx`` calls when the kernel replies with an error: budget
    exhausted, permission denied, unknown tool, invalid spawn. Catch it to
    handle the refusal; let it propagate to have the kernel kill this agent
    (the kernel stays up either way).
    """


class Message:
    """One delivery from the message bus."""

    __slots__ = ("seq", "kind", "payload", "sender")

    def __init__(self, raw):
        self.seq = raw.get("seq", 0)
        self.kind = raw.get("kind", "")
        self.payload = raw.get("payload")
        sender = raw.get("from") or {}
        # None when the kernel or an external caller sent it.
        self.sender = sender.get("id") if sender.get("type") == "agent" else None

    @property
    def from_agent(self):
        """Sender agent id, or ``None`` if it came from the system."""
        return self.sender

    def __repr__(self):
        origin = "system" if self.sender is None else "agent-%d" % self.sender
        return "<Message %s from %s>" % (self.kind, origin)


class Generation:
    """What a model call returned, and what it cost."""

    __slots__ = ("text", "tokens_used")

    def __init__(self, text, tokens_used):
        self.text = text
        self.tokens_used = tokens_used

    def __str__(self):
        return self.text

    def __repr__(self):
        return "<Generation %d tokens: %r>" % (self.tokens_used, self.text[:40])


class Agent:
    """Base class for Python agents.

    Agents are event-driven: ``on_message`` runs only while handling a
    delivery, and everything an agent can do — sending, generating, tools,
    spawning, suspending — goes through ``ctx``.

    A fresh instance is constructed for every delivery, so durable state
    belongs in ``ctx.memory`` (a plain dict the kernel persists), not in
    ``self``. That is what makes suspension cheap: the agent's identity
    lives in the kernel's store, not in a resident process.
    """

    def on_message(self, ctx, msg):
        raise NotImplementedError(
            "%s must implement on_message(self, ctx, msg)" % type(self).__name__
        )


def agent(kind):
    """Register an agent class under a kind name the kernel can spawn.

    >>> @agent("greeter")
    ... class Greeter(Agent):
    ...     def on_message(self, ctx, msg):
    ...         ctx.memory["seen"] = ctx.memory.get("seen", 0) + 1
    """

    def decorate(cls):
        if not isinstance(kind, str) or not kind:
            raise ValueError("agent kind must be a non-empty string")
        if kind in REGISTRY and REGISTRY[kind] is not cls:
            raise ValueError("agent kind %r is already registered" % kind)
        REGISTRY[kind] = cls
        cls.kind = kind
        return cls

    return decorate
