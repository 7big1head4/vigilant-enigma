# enigma-sdk

Write agents for [Enigma](https://github.com/7big1head4/vigilant-enigma), an
agentic operating system. The Rust kernel schedules your agents, enforces
their token budgets, persists their memory, and suspends them when idle —
this package is how you write one.

Standard library only. Nothing to compile, nothing to install on a Pi.

```python
from enigma_sdk import Agent, agent

@agent("summarizer")
class Summarizer(Agent):
    def on_message(self, ctx, msg):
        result = ctx.generate("Summarize: %s" % msg.payload["text"])
        ctx.memory["summaries"] = ctx.memory.get("summaries", 0) + 1
        if msg.from_agent is not None:
            ctx.send_to(msg.from_agent, "summary", {"text": result.text})
        ctx.suspend_self()
```

## The context

Everything an agent can do goes through `ctx`, and every call is a syscall
into the kernel — budgets and capabilities are checked there, not here.

| Call | What it does |
|---|---|
| `ctx.generate(prompt)` | Run the model; tokens are charged to this agent's budget |
| `ctx.send_to(agent_id, kind, payload)` | Message one agent (wakes it if suspended) |
| `ctx.publish(topic, kind, payload)` | Publish to every subscriber of a topic |
| `ctx.spawn(kind, name=…, max_tokens=…)` | Spawn a sub-agent; the grant transfers from your budget |
| `ctx.call_tool(name, args)` | Invoke a kernel tool (needs the capability) |
| `ctx.subscribe(topic)` | Join a topic |
| `ctx.suspend_self()` | Sleep after this handler; costs nothing until woken |
| `ctx.memory` | Plain dict the kernel persists across suspension |

A refused syscall — budget exhausted, permission denied — raises
`EnigmaError`. Catch it to recover, or let it propagate to have the kernel
kill this agent; either way the kernel keeps running.

**Durable state belongs in `ctx.memory`, not on `self`.** A fresh instance
is built for every delivery, because an agent's identity lives in the
kernel's store rather than in a resident process. That is what makes
suspension cheap.

## Running

The kernel spawns the worker for you:

```bash
# from the repo root
cargo run --release --bin enigma -- py-demo
```

To point the kernel at your own module, set `ENIGMA_PYTHON_MODULE` and
`ENIGMA_PYTHON_DIR`, or build the `Command` yourself with
`PythonBridge::spawn` (see `core/enigma-core/src/bridge.rs`).

Running the worker by hand only checks that a module imports and registers
the kinds you expect — it needs a kernel on the other end to do anything:

```bash
PYTHONPATH=sdk/python python3 -m enigma_sdk examples/agents.py
```

## Tests

```bash
cd sdk/python && python3 -m unittest discover -s tests
```

The end-to-end half (a real kernel driving a real worker) lives in
`core/enigma-core/tests/python_bridge.rs`.

## License

GNU GPL v2 or later.
