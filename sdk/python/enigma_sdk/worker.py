# Copyright (C) 2026 the Enigma authors
# SPDX-License-Identifier: GPL-2.0-or-later

"""The protocol loop: newline-delimited JSON over stdin/stdout.

The Rust kernel spawns this worker as a child process and drives it. One
delivery looks like:

    kernel -> worker   {"op":"dispatch","kind":"greeter","agent_id":3,
                        "memory":{...},"msg":{...}}
    worker -> kernel   {"op":"generate","prompt":"..."}      (a syscall)
    kernel -> worker   {"ok":{"text":"...","tokens_used":30}}
    worker -> kernel   {"op":"done","memory":{...}}

An agent that raises sends ``{"op":"error",...}`` instead of ``done``, and
the kernel kills that agent with the traceback as the reason — the kernel
itself keeps running.

stdout is the protocol channel, so ``sys.stdout`` is redirected to stderr
before any agent code runs: an agent's ``print()`` cannot corrupt the
stream.
"""

import json
import sys
import traceback

from .context import Context
from .core import REGISTRY, Message

PROTOCOL_VERSION = 1


class _Channel:
    """Framing over the two protocol streams."""

    def __init__(self, reader, writer):
        self._reader = reader
        self._writer = writer

    def write(self, obj):
        self._writer.write(json.dumps(obj) + "\n")
        self._writer.flush()

    def read(self):
        line = self._reader.readline()
        if not line:
            return None  # kernel closed the channel: time to exit
        return json.loads(line)

    def call(self, payload):
        """Send a syscall and block for its reply."""
        self.write(payload)
        reply = self.read()
        if reply is None:
            raise SystemExit(0)
        return reply


def _dispatch(channel, request):
    kind = request.get("kind")
    cls = REGISTRY.get(kind)
    if cls is None:
        channel.write(
            {
                "op": "error",
                "message": "no agent registered for kind %r (registered: %s)"
                % (kind, ", ".join(sorted(REGISTRY)) or "none"),
            }
        )
        return

    memory = dict(request.get("memory") or {})
    ctx = Context(request.get("agent_id"), memory, channel)
    msg = Message(request.get("msg") or {})
    try:
        # A fresh instance per delivery: durable state lives in ctx.memory.
        cls().on_message(ctx, msg)
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - report anything to the kernel
        channel.write(
            {
                "op": "error",
                "message": "python agent raised %s: %s"
                % (type(exc).__name__, exc),
                "traceback": traceback.format_exc(),
            }
        )
        return
    channel.write({"op": "done", "memory": ctx.memory})


def serve(reader=None, writer=None):
    """Run the protocol loop until the kernel closes the channel.

    Called with no arguments it takes over the real stdin/stdout and
    redirects ``sys.stdout`` to stderr. Pass explicit streams to drive it
    in tests.
    """
    owns_streams = reader is None and writer is None
    channel = _Channel(reader or sys.stdin, writer or sys.stdout)
    if owns_streams:
        sys.stdout = sys.stderr  # keep agent print() off the protocol channel

    channel.write(
        {
            "op": "ready",
            "protocol": PROTOCOL_VERSION,
            "kinds": sorted(REGISTRY),
        }
    )

    while True:
        request = channel.read()
        if request is None:
            return
        op = request.get("op")
        if op == "dispatch":
            _dispatch(channel, request)
        elif op == "shutdown":
            return
        else:
            channel.write({"op": "error", "message": "unknown op %r" % op})
