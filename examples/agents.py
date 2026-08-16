# Copyright (C) 2026 the Enigma authors
# SPDX-License-Identifier: GPL-2.0-or-later

"""Example Python agents — run with ``enigma py-demo`` from the repo root.

A researcher fans work out to summarizer sub-agents, each funded from the
researcher's own token budget, then collects their answers and suspends.
It shows the four things the runtime gives you: unlimited sub-agents with
conserved budgets, the message bus, model calls, and cheap suspension.
"""

from enigma_sdk import Agent, agent

TOPICS = [
    "how an OS scheduler decides what runs next",
    "why virtual memory exists",
    "what a system call actually does",
    "how processes talk to each other",
    "why context switches are expensive",
]


@agent("researcher")
class Researcher(Agent):
    """Spawns one summarizer per topic and gathers the results."""

    def on_message(self, ctx, msg):
        if msg.kind == "start":
            count = min(msg.payload.get("topics", 3), len(TOPICS))
            grant = msg.payload.get("grant", 300)
            ctx.memory["expected"] = count

            for i in range(count):
                # The grant is transferred out of this agent's budget, so
                # the whole tree stays inside what the researcher was given.
                worker = ctx.spawn(
                    "summarizer", name="summarizer-%d" % i, max_tokens=grant
                )
                print("[researcher] spawned agent-%d for topic %d" % (worker, i))
                ctx.send_to(worker, "summarize", {"topic": TOPICS[i]})

        elif msg.kind == "summary":
            done = ctx.memory.get("done", 0) + 1
            ctx.memory["done"] = done
            ctx.memory.setdefault("summaries", []).append(msg.payload["text"])
            print("[researcher] summary %d: %s" % (done, msg.payload["text"][:70]))

            if done >= ctx.memory.get("expected", 0):
                print("[researcher] everything is in — suspending myself")
                ctx.suspend_self()


@agent("summarizer")
class Summarizer(Agent):
    """Answers one topic with the local model, reports back, then sleeps."""

    def on_message(self, ctx, msg):
        if msg.kind != "summarize":
            return

        result = ctx.generate(
            "In one short sentence, explain %s" % msg.payload["topic"]
        )
        ctx.memory["topic"] = msg.payload["topic"]
        ctx.memory["tokens"] = result.tokens_used
        print("[agent-%s] %d tokens" % (ctx.agent_id, result.tokens_used))

        if msg.from_agent is not None:
            ctx.send_to(msg.from_agent, "summary", {"text": result.text})

        # Costs nothing until someone sends it another topic.
        ctx.suspend_self()
