# Copyright (C) 2026 the Enigma authors
# SPDX-License-Identifier: GPL-2.0-or-later

"""Protocol-level tests for the worker loop.

These drive :func:`enigma_sdk.serve` with scripted streams, so they pin the
exact JSON contract the Rust kernel relies on without needing the kernel.
The other half of the contract — a real kernel driving a real worker — is
covered by ``core/enigma-core/tests/python_bridge.rs``.
"""

import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enigma_sdk import Agent, EnigmaError, agent, serve  # noqa: E402
from enigma_sdk.core import REGISTRY  # noqa: E402


@agent("echoer")
class Echoer(Agent):
    def on_message(self, ctx, msg):
        ctx.memory["seen"] = ctx.memory.get("seen", 0) + 1
        ctx.memory["kind"] = msg.kind
        ctx.memory["sender"] = msg.from_agent


@agent("generator")
class Generator(Agent):
    def on_message(self, ctx, msg):
        result = ctx.generate("prompt-" + msg.kind)
        ctx.memory["text"] = result.text
        ctx.memory["cost"] = result.tokens_used


@agent("catcher")
class Catcher(Agent):
    def on_message(self, ctx, msg):
        try:
            ctx.generate("too expensive")
        except EnigmaError as exc:
            ctx.memory["refused"] = str(exc)


@agent("crasher")
class Crasher(Agent):
    def on_message(self, ctx, msg):
        raise RuntimeError("kaboom")


def run(lines):
    """Feed scripted kernel messages to the worker; return what it wrote."""
    stdin = io.StringIO("".join(json.dumps(line) + "\n" for line in lines))
    stdout = io.StringIO()
    serve(stdin, stdout)
    return [json.loads(line) for line in stdout.getvalue().splitlines()]


def dispatch(kind, agent_id=1, memory=None, msg=None):
    return {
        "op": "dispatch",
        "kind": kind,
        "agent_id": agent_id,
        "memory": memory or {},
        "msg": msg or {"seq": 1, "kind": "tick", "payload": {}, "from": {"type": "system"}},
    }


class HandshakeTests(unittest.TestCase):
    def test_announces_protocol_and_kinds(self):
        out = run([])
        self.assertEqual(out[0]["op"], "ready")
        self.assertEqual(out[0]["protocol"], 1)
        # Every decorated class in this module is advertised.
        for kind in ("echoer", "generator", "catcher", "crasher"):
            self.assertIn(kind, out[0]["kinds"])

    def test_registry_rejects_duplicate_kinds(self):
        with self.assertRaises(ValueError):

            @agent("echoer")
            class Other(Agent):
                pass

    def test_registry_holds_the_decorated_class(self):
        self.assertIs(REGISTRY["echoer"], Echoer)


class DispatchTests(unittest.TestCase):
    def test_returns_mutated_memory(self):
        out = run([dispatch("echoer", memory={"seen": 4})])
        done = out[-1]
        self.assertEqual(done["op"], "done")
        self.assertEqual(done["memory"]["seen"], 5)
        self.assertEqual(done["memory"]["kind"], "tick")

    def test_sender_is_none_for_system_messages(self):
        out = run([dispatch("echoer")])
        self.assertIsNone(out[-1]["memory"]["sender"])

    def test_sender_is_the_agent_id_for_agent_messages(self):
        msg = {"seq": 2, "kind": "task", "payload": {}, "from": {"type": "agent", "id": 7}}
        out = run([dispatch("echoer", msg=msg)])
        self.assertEqual(out[-1]["memory"]["sender"], 7)

    def test_unregistered_kind_reports_an_error(self):
        out = run([dispatch("nonexistent")])
        self.assertEqual(out[-1]["op"], "error")
        self.assertIn("no agent registered", out[-1]["message"])

    def test_unknown_op_is_reported(self):
        out = run([{"op": "wat"}])
        self.assertEqual(out[-1]["op"], "error")
        self.assertIn("unknown op", out[-1]["message"])

    def test_shutdown_ends_the_loop(self):
        out = run([{"op": "shutdown"}, dispatch("echoer")])
        # Only the handshake: the dispatch after shutdown is never read.
        self.assertEqual([m["op"] for m in out], ["ready"])


class SyscallTests(unittest.TestCase):
    def test_generate_round_trip(self):
        out = run(
            [
                dispatch("generator"),
                {"ok": {"text": "hello", "tokens_used": 12}},
            ]
        )
        call = out[1]
        self.assertEqual(call["op"], "generate")
        self.assertEqual(call["prompt"], "prompt-tick")
        self.assertEqual(out[-1]["memory"], {"text": "hello", "cost": 12})

    def test_refused_syscall_raises_enigma_error(self):
        out = run([dispatch("catcher"), {"err": "budget exhausted for agent-1"}])
        # The agent caught it, so the dispatch still completes normally.
        self.assertEqual(out[-1]["op"], "done")
        self.assertIn("budget exhausted", out[-1]["memory"]["refused"])

    def test_uncaught_exception_becomes_an_error_frame(self):
        out = run([dispatch("crasher")])
        self.assertEqual(out[-1]["op"], "error")
        self.assertIn("RuntimeError", out[-1]["message"])
        self.assertIn("kaboom", out[-1]["message"])
        self.assertIn("Traceback", out[-1]["traceback"])


class ContextApiTests(unittest.TestCase):
    """Each context helper emits the frame the kernel's `service` expects."""

    probes = 0

    def frame_for(self, body):
        ContextApiTests.probes += 1
        kind = "probe_%d" % ContextApiTests.probes

        @agent(kind)
        class Probe(Agent):
            def on_message(self, ctx, msg):
                body(ctx)

        # One reply is enough: every helper below makes a single syscall.
        out = run([dispatch(kind), {"ok": {"agent_id": 9}}])
        return out[1]

    def test_send_to(self):
        frame = self.frame_for(lambda ctx: ctx.send_to(4, "result", {"x": 1}))
        self.assertEqual(frame["op"], "send")
        self.assertEqual(frame["to"], {"type": "agent", "id": 4})
        self.assertEqual(frame["kind"], "result")
        self.assertEqual(frame["payload"], {"x": 1})

    def test_publish(self):
        frame = self.frame_for(lambda ctx: ctx.publish("news", "headline"))
        self.assertEqual(frame["to"], {"type": "topic", "name": "news"})

    def test_spawn_defaults(self):
        frame = self.frame_for(lambda ctx: ctx.spawn("worker"))
        self.assertEqual(frame["op"], "spawn")
        self.assertEqual(frame["spec"]["kind"], "worker")
        self.assertEqual(frame["spec"]["name"], "worker")
        self.assertIsNone(frame["spec"]["max_tokens"])

    def test_spawn_with_grant_and_caps(self):
        frame = self.frame_for(
            lambda ctx: ctx.spawn(
                "worker", name="w0", max_tokens=250, caps=["tool.echo"], topics=["news"]
            )
        )
        self.assertEqual(frame["spec"]["max_tokens"], 250)
        self.assertEqual(frame["spec"]["caps"], ["tool.echo"])
        self.assertEqual(frame["spec"]["topics"], ["news"])

    def test_spawn_returns_the_new_agent_id(self):
        seen = {}

        def body(ctx):
            seen["id"] = ctx.spawn("worker")

        self.frame_for(body)
        self.assertEqual(seen["id"], 9)

    def test_call_tool(self):
        frame = self.frame_for(lambda ctx: ctx.call_tool("echo", {"a": 1}))
        self.assertEqual(frame["op"], "call_tool")
        self.assertEqual(frame["name"], "echo")
        self.assertEqual(frame["args"], {"a": 1})

    def test_subscribe(self):
        frame = self.frame_for(lambda ctx: ctx.subscribe("news"))
        self.assertEqual(frame, {"op": "subscribe", "topic": "news"})

    def test_suspend_self(self):
        frame = self.frame_for(lambda ctx: ctx.suspend_self())
        self.assertEqual(frame, {"op": "suspend_self"})


if __name__ == "__main__":
    unittest.main()
