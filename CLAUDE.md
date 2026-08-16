# CLAUDE.md

Guidance for AI assistants (and human contributors) working on **Enigma**.
Keep this file honest: if a section is out of date, fix it in the same PR
that changes tooling, layout, or conventions.

# Enigma — an agentic operating system

Enigma is a runtime that gives AI agents what an operating system gives
processes: scheduling, memory, capabilities, and communication. It is not a
kernel — it runs in userspace on top of Linux (and macOS for development),
orchestrating a population of LLM-driven agents the way an OS orchestrates
processes.

## Design principles

These are the commitments that make Enigma different from other agent
frameworks. Changes that violate them need a very good argument in the PR.

- **Lightweight by contract.** The reference target is a Raspberry Pi 5
  (8 GB, ARM64). The core must idle at near-zero CPU and a small, bounded
  memory footprint; the crate's only dependencies are `serde` and
  `serde_json`, and CI enforces an `aarch64-unknown-linux-gnu` check on
  every PR. If a feature cannot run comfortably on the Pi, it does not go
  in the core.
- **Offline-first.** Enigma must be fully usable with only local models.
  The shipped model backend talks to Ollama over localhost HTTP; hosted
  providers are an upgrade, never a requirement. No feature may
  hard-depend on a cloud service.
- **Resource budgets for agents** ("ulimit for agents"). Every agent runs
  under a token budget the scheduler enforces on every `generate` call.
  Budgets are *conserved*: an agent granting tokens to a sub-agent
  transfers them from its own budget, and a bounded agent cannot grant an
  unlimited one — spawning never mints tokens.
- **Unlimited sub-agents.** Any agent may spawn any number of sub-agents
  (`Ctx::spawn`), nested to any depth. The budget-conservation rule above
  is what makes this safe.
- **Suspendable agents.** An idle agent's snapshot and memory serialize to
  disk and it costs nothing until a message wakes it (resume-on-message).
  Agents are assumed to be suspended most of the time; waking is cheap.

## Architecture (built)

### Kernel — `core/enigma-core/src/kernel.rs` (built)

Deterministic single-threaded event loop. Spawning, killing,
suspend/resume, message dispatch, budget-conserving sub-agent spawning,
and persistence (suspended agents live under `state_dir/agents/`, the
manifest and `status.json` beside them; default state dir `~/.enigma`,
override `ENIGMA_STATE_DIR`). Agent failure kills that agent with a
recorded reason — never the kernel. While running, the kernel streams
`status.json` (throttled, 250 ms) so observers see agents live.

### Agents & lifecycle — `src/agent.rs` (built)

`Agent` trait: event-driven `on_message(ctx, envelope)` plus an optional
`snapshot()`. A factory per registered kind rebuilds instances from the
snapshot on resume — the same function serves first spawn and wake.
States: `Running`, `Suspended`, `Dead { reason }`.

### Memory — `src/memory.rs` (built)

Per-agent persistent key-value store (`ctx.memory`), serialized with the
agent at suspend. The recommended pattern keeps all durable state here so
`snapshot()` can stay `Null`.

### Tools & permissions — `src/tools.rs`, `src/permissions.rs` (built)

Capability-gated tool registry: every `ctx.call_tool` crosses the
permission check; missing capability and unknown tool are distinct errors.
Built-in: `EchoTool` (capability `tool.echo`).

### Messaging — `src/bus.rs` (built)

Envelopes with kernel-assigned total order, addressed to a single agent or
a topic (pub/sub). Delivery to a suspended agent wakes it; delivery to a
dead agent is dropped and counted.

### Model layer — `src/model.rs` (built)

`ModelBackend` trait; the shipped backend is **Ollama** over hand-rolled
localhost HTTP (no extra deps, no TLS). Token counts come from the
backend and are charged to the calling agent's budget; a word-count
fallback keeps budgets binding when counts are missing. Config:
`ENIGMA_OLLAMA_ADDR` (default `127.0.0.1:11434`), `ENIGMA_OLLAMA_MODEL`
(default `llama3.2:1b`).

### Dashboard — `dashboard/enigma_dash.py` (built)

Single-file, stdlib-only Python web server: live CPU/memory/disk/
temperature/network/process stats read straight from `/proc` and `/sys`,
plus a **live Enigma agents panel** fed by the kernel's streamed
`status.json`. Theme-aware, 1 s refresh, PWA ("Add to Home Screen" on a
phone). Binds all interfaces by default with **no authentication** —
trusted networks only.

### Python SDK & bridge — `sdk/python/`, `src/bridge.rs` (built)

Agents can be written in Python and are scheduled exactly like native
ones: same budgets, same capability checks, same suspension.

**The bridge is IPC, not PyO3** — the decision this file was waiting on.
The kernel spawns a worker process (`python3 -m enigma_sdk <module>`) and
speaks newline-delimited JSON over its stdin/stdout. A delivery is a
nested syscall loop: the kernel hands the worker a message, the worker
calls back (`generate`, `spawn`, `call_tool`, `send`, `subscribe`,
`suspend_self`), and each call is serviced through the same `Ctx` a native
agent uses. Rationale, should anyone revisit it: PyO3 would make CPython
resident in the kernel and put a compiler toolchain and wheel builds in
the way of running on a Pi — both against the lightweight contract. IPC
keeps the core at two dependencies and the SDK pure-stdlib, and it keeps
suspension honest (no interpreter state to preserve).

Protocol version is `PROTOCOL_VERSION` on both sides; the handshake
refuses a mismatch rather than guessing. `register_python_kinds` registers
every kind the worker advertised. A Python exception kills that agent with
the exception as the reason; a refused syscall raises `EnigmaError` in
Python, so agents can catch and recover. The worker redirects
`sys.stdout` to stderr so an agent's `print()` cannot corrupt the channel.

## Repository layout

```
.
├── .github/
│   ├── pull_request_template.md
│   └── workflows/ci.yml           # fmt, clippy -D warnings, tests, aarch64, py_compile
├── core/                          # Rust workspace
│   └── enigma-core/               # the runtime crate + `enigma` CLI
│       ├── src/                   # kernel, agent, bus, budget, memory, model, tools, permissions, bridge
│       ├── src/bin/enigma.rs      # CLI: demo, py-demo, status
│       └── tests/                 # kernel.rs, ollama_http.rs, python_bridge.rs (+ py/ agents)
├── sdk/python/
│   ├── enigma_sdk/                # the agent SDK (stdlib only)
│   └── tests/                     # protocol tests
├── examples/
│   └── agents.py                  # example Python agents (`enigma py-demo`)
├── dashboard/
│   └── enigma_dash.py             # live system + agents dashboard
├── CLAUDE.md
└── LICENSE                        # GNU GPL v2
```

## Build, test, lint

**Core** (from `core/`):

```
cargo build                # or --release
cargo test                 # all 39 tests, no network/LLM needed
cargo test --test kernel spawning_transfers_budget_from_parent   # single test
cargo fmt --all --check
cargo clippy --all-targets -- -D warnings
cargo check --target aarch64-unknown-linux-gnu   # RPi5 cross-check
```

`cargo test` requires `python3` on PATH: `tests/python_bridge.rs` spawns a
real worker. Override the interpreter with `ENIGMA_PYTHON`.

**Python SDK** (from `sdk/python/`, no install needed — stdlib only):

```
python3 -m unittest discover -s tests      # protocol tests
python3 -m unittest tests.test_protocol.SyscallTests   # single class
```

**Run it** (needs an Ollama server; run from the repository root):

```
cargo run --release --bin enigma -- demo --workers 3 --grant 300     # Rust agents
cargo run --release --bin enigma -- py-demo --topics 3 --grant 300   # Python agents
cargo run --release --bin enigma -- status
```

`py-demo` reads `examples/agents.py`; point it elsewhere with
`ENIGMA_PYTHON_DIR` / `ENIGMA_PYTHON_MODULE`, and set `ENIGMA_SDK_PATH` if
the SDK is not at `sdk/python`.

**Dashboard** (no install step — standard library only, Python 3.9+):

```
python3 dashboard/enigma_dash.py            # binds 0.0.0.0:8765
```

Open `http://<machine-ip>:8765/`, "Add to Home Screen" on a phone.
Smoke-test with `curl http://127.0.0.1:8765/api/stats`.

CI (`.github/workflows/ci.yml`) runs all of the above checks; keep it
green before marking a PR ready.

## Testing philosophy

No mocks in the product path. The `ModelBackend` trait is implemented in
tests by a deterministic in-test backend for exact budget arithmetic, and
the real Ollama HTTP client is tested hermetically against an in-test
`TcpListener` serving canned HTTP (`tests/ollama_http.rs`) — the exact
bytes-on-wire path ships tested without a live LLM.

The Python bridge is tested the same way, from both ends: a real kernel
driving a real `python3` worker through the real SDK
(`tests/python_bridge.rs`, agents in `tests/py/`), plus scripted-stream
tests of the protocol contract on the Python side
(`sdk/python/tests/test_protocol.py`). Neither side is simulated.

## License

GNU General Public License v2.0. Rust and Python source files carry a
copyright line plus `SPDX-License-Identifier: GPL-2.0-or-later`; crate
roots and binaries additionally carry the short two-paragraph GPL notice
(see `core/enigma-core/src/lib.rs`). Do not introduce dependencies whose
licenses are incompatible with GPL v2 without first discussing it in a PR.

## Git workflow

- Default branch: `main`. Remote:
  `https://github.com/7big1head4/vigilant-enigma` (project name is Enigma;
  the repo keeps its generated name for now).
- Feature work happens on a topic branch; open pull requests against
  `main` as drafts, marked ready once CI is green.
- PR descriptions follow `.github/pull_request_template.md`.
- Keep this file in sync with reality in the same PR that changes
  tooling, layout, or conventions. Commit early and often — work in
  progress that isn't pushed doesn't exist.

## Instructions for AI assistants

- **Planned is not built.** Never describe an unimplemented piece (the
  Python SDK) as existing, and never fabricate commands, files, or
  behavior.
- Respect the design principles in every change — especially budget
  conservation, the RPi5 resource contract, and offline-first. A PR that
  adds a hard cloud dependency or a heavyweight core dependency is wrong
  by default.
- Keep the no-mocks testing philosophy: deterministic test backends
  implement real traits; network clients get hermetic real-socket tests.
- Prefer editing this file over creating parallel documentation.
