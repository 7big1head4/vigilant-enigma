# Enigma

**An agentic operating system for LLM-driven agents.**

Enigma gives AI agents what a traditional operating system gives processes: scheduling, memory (with cheap suspension), explicit capabilities/permissions, and inter-agent communication — all while staying lightweight enough to run comfortably on a Raspberry Pi 5 and fully usable offline with local models (Ollama, llama.cpp, etc.).

> **Current status**: Early development. Only the live system-stats dashboard is implemented. The core runtime, Python SDK, and agent orchestration layer are planned (see `CLAUDE.md` for the full architecture and design principles).

## Quick Start — Dashboard

The only component that exists today is a zero-dependency, stdlib-only live dashboard showing CPU, memory, disk, temperature, network, top processes, and (soon) agent status.

```bash
git clone https://github.com/7big1head4/vigilant-enigma.git
cd vigilant-enigma
python3 dashboard/enigma_dash.py
