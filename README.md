# Enigma

**An agentic operating system.**

Enigma gives AI agents what an operating system gives processes:
**scheduling** (event-driven, wake-on-message), **memory** (per-agent
persistent store with cheap suspend-to-disk), **capabilities** (permission-
gated tools), and **communication** (a topic/direct message bus) — in a
Rust core light enough for a Raspberry Pi 5 and fully usable offline with
local models via Ollama.

What makes it different:

- **Token budgets are conserved.** Every agent runs under a token budget
  charged on every model call. Agents can spawn **unlimited sub-agents**,
  but grants transfer from the parent's budget — a tree of agents can
  never spend more than its root was given.
- **Suspension is the default.** Idle agents serialize to disk and cost
  nothing; any message wakes them, even across kernel restarts.
- **Failure is contained.** An agent that errors or exhausts its budget
  dies with a recorded reason; the kernel keeps running.
- **Tiny by contract.** Two dependencies (`serde`, `serde_json`), ARM64
  checked in CI, near-zero idle footprint.

## Quick start — runtime

Needs Rust and a local [Ollama](https://ollama.com) (`ollama serve`,
`ollama pull llama3.2:1b`):

```bash
git clone https://github.com/7big1head4/vigilant-enigma.git
cd vigilant-enigma/core
cargo run --release --bin enigma -- demo --workers 3 --grant 300
cargo run --release --bin enigma -- status
```

The demo spawns an orchestrator that spawns three workers (300-token
grants each), fans out prompts, collects LLM answers, and suspends
everything to `~/.enigma/` — run `status` afterwards to see the suspended
population and what each agent spent.

Configuration: `ENIGMA_STATE_DIR`, `ENIGMA_OLLAMA_ADDR`,
`ENIGMA_OLLAMA_MODEL`.

## Quick start — dashboard

A zero-dependency, stdlib-only live dashboard (CPU, memory, disk,
temperature and Pi throttle flags, network, processes) with a **live
agents panel**: while the kernel runs it streams `status.json`, and the
page shows agents spawning, spending tokens, suspending, and dying in
real time.

```bash
python3 dashboard/enigma_dash.py    # then open http://<machine-ip>:8765/
```

It's a PWA — "Add to Home Screen" on a phone installs it like an app.
No authentication: trusted networks only.

## Status

Early but real: the Rust kernel (scheduler, budgets, suspension,
permissions, messaging, Ollama backend) and the dashboard are built and
tested (26 tests, no network needed). The Python agent SDK is planned.
Architecture, design principles, and contributor docs live in
[CLAUDE.md](CLAUDE.md).

## License

GNU GPL v2 — see [LICENSE](LICENSE).
