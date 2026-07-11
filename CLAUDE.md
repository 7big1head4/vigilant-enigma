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

## Current status

**Pre-code.** The repository contains this file,
`.github/pull_request_template.md`, and `LICENSE` (GPL v2). Everything in
the Architecture section below is *planned*, not built. Whoever implements
the first piece of a subsystem must update the corresponding section here in
the same PR — planned sections become real descriptions with file paths.

## Design principles

These are the commitments that make Enigma different from other agent
frameworks. Changes that violate them need a very good argument in the PR.

- **Lightweight by contract.** The reference target is a Raspberry Pi 5
  (8 GB, ARM64). The core must idle at near-zero CPU and a small, bounded
  memory footprint. If a feature cannot run comfortably on the Pi, it does
  not go in the core. ARM64 is a first-class build target from day one, not
  a port.
- **Offline-first.** Enigma must be fully usable with only local models
  (Ollama, llama.cpp). Hosted providers are an upgrade, never a requirement.
  No feature may hard-depend on a cloud service.
- **Resource budgets for agents** ("ulimit for agents"). Every agent runs
  under CPU, RAM, *and token/cost* quotas. The scheduler treats token spend
  as a schedulable resource alongside compute — a cheap local-model agent
  and an expensive hosted-model agent are scheduled differently on purpose.
- **Suspendable agents.** An idle agent serializes its state and memory to
  disk and costs nothing until an event wakes it — swap, for agents. Agents
  are assumed to be suspended most of the time; waking must be cheap.

## Architecture (planned)

None of this exists yet. It is the component map implementations should
grow into, described by analogy to a classic OS.

### Agent lifecycle & scheduler (the process model)

Spawning, pausing, resuming, and killing agents. The scheduler decides which
agent runs when, driven by events (messages, timers, watched conditions) and
constrained by each agent's resource budget — including its token/cost
quota. Idle agents are suspended to disk rather than kept resident.

### Memory system (RAM and the filesystem)

Each agent gets short-term working memory for the task at hand and access to
a long-term persistent store that survives suspension and restarts. Memory
is what makes suspension cheap: an agent's identity lives in the store, not
in a running process.

### Tools & permissions layer (the syscall boundary)

Agents get capabilities — shell, filesystem, web, APIs — only through
explicit grants, and every tool call crosses a permission check the way a
syscall crosses into the kernel. Sandboxing and gating live here, not in
individual agents.

### Inter-agent messaging (IPC)

A message bus carries events between agents and between agents and the
user. Agents subscribe to channels and are woken by messages; this is the
primary mechanism that drives scheduling.

### Model layer

Provider-agnostic. Local models (Ollama, llama.cpp) are first-class
citizens, not a fallback; hosted providers such as the Claude API plug into
the same interface. The model layer reports token usage so the scheduler
can enforce cost budgets.

## Stack & repository layout (planned)

- **Rust core**: scheduler, message bus, state and suspension, permission
  enforcement. No heavyweight runtime dependencies; must build and run well
  on ARM64/RPi5.
- **Python SDK**: how agents, tools, and integrations are written — where
  the LLM ecosystem lives.
- **Bridge**: PyO3 or IPC between core and SDK — decide when the core
  exists, and record the decision here.

Intended tree (create these directories as the code lands, and keep this
listing current):

```
.
├── .github/
│   └── pull_request_template.md   # template applied to new PRs
├── core/          # (planned) Rust workspace: the runtime
├── sdk/python/    # (planned) Python agent SDK
├── examples/      # (planned) runnable example agents
├── docs/          # (planned) design docs beyond this file
├── CLAUDE.md      # this file
└── LICENSE        # GNU GPL v2
```

## Build, test, lint

TODO — no manifests exist yet. Expected tooling, so the first PRs use it:

- Core: `cargo build` / `cargo test` / `cargo clippy` / `cargo fmt`.
- Python SDK: `uv` for environments/packaging, `pytest` for tests,
  `ruff` for lint and format.

The PR that introduces a manifest (`Cargo.toml`, `pyproject.toml`) must
replace this TODO with the real commands, including how to run a single
test and how to cross-check an ARM64 build.

## License

GNU General Public License v2.0. New Rust and Python source files should
carry a GPL v2-compatible header once a header style is chosen (record it
here). Do not introduce dependencies whose licenses are incompatible with
GPL v2 without first discussing it in a PR.

## Git workflow

- Default branch: `main`.
- Remote: `https://github.com/7big1head4/vigilant-enigma` (project name is
  Enigma; the repo keeps its generated name for now).
- Feature work happens on a topic branch; open pull requests against `main`.
- PR descriptions follow `.github/pull_request_template.md`.
- Pull requests are opened as drafts and marked ready for review once CI is
  green and the change is complete.
- Keep this file in sync with reality: any PR that changes tooling, layout,
  or conventions updates the relevant section of `CLAUDE.md` in the same PR.

## Instructions for AI assistants

- **Planned is not built.** Never describe an unimplemented subsystem as
  existing, and never fabricate commands, files, or behavior. If a section
  says TODO or planned, that is the truth — leave it that way until the
  code exists.
- When you implement (part of) a subsystem, rewrite its "planned" section
  into a real description with actual file paths, in the same PR.
- Respect the design principles above in every change — especially the
  RPi5 resource contract and offline-first. A PR that adds a hard cloud
  dependency or a heavyweight core dependency is wrong by default.
- Prefer editing this file over creating parallel documentation.
