# CLAUDE.md

This file provides guidance for AI assistants (Claude and others) working in this repository.

## Repository Overview

**vigilant-enigma** is a newly initialized repository. As of this writing it contains only a GPL-2.0 LICENSE file. This document establishes conventions and workflows to follow as the project grows.

- **License:** GNU General Public License v2.0
- **Remote:** `7big1head4/vigilant-enigma`
- **Default branch:** `main`

---

## Development Branch Convention

Feature work by Claude should land on branches named `claude/<short-description>-<id>`, e.g. `claude/add-claude-documentation-sd7ng`. Never push directly to `main` without explicit user approval.

---

## Git Workflow

1. Develop on the designated feature branch.
2. Write clear, descriptive commit messages (imperative mood, ≤ 72 chars subject line).
3. Push with `git push -u origin <branch-name>`.
4. Do **not** open a pull request unless the user explicitly requests one.
5. Retry failed pushes up to 4 times with exponential backoff (2 s, 4 s, 8 s, 16 s).

---

## Code Conventions (to be updated as the project is built out)

Since no source code exists yet, conventions will be defined here as the project evolves. When adding initial code, document the following in this section:

- **Language / runtime** and version requirements
- **Package manager** and install command (e.g. `npm install`, `pip install -e .`)
- **Formatter / linter** and how to run it
- **Test runner** and the command to execute tests
- **Build command** if applicable

### General principles to follow in the meantime

- Prefer editing existing files over creating new ones.
- Do not add dead code, speculative abstractions, or features not explicitly requested.
- Validate only at system boundaries (user input, external APIs); trust internal guarantees.
- Keep functions small and single-purpose.
- No commented-out code in commits.

---

## File Structure (current)

```
vigilant-enigma/
├── LICENSE          # GNU GPL v2.0
└── CLAUDE.md        # This file
```

Update this tree as directories and files are added.

---

## Testing

No tests exist yet. When a test suite is introduced, document here:

- The test framework used
- The command to run all tests
- Any required environment setup (env vars, services, etc.)

---

## Security

This project is licensed under GPL-2.0. Do not introduce code with incompatible licenses. Avoid hardcoding secrets or credentials; use environment variables or a secrets manager.

---

## Updating This File

Keep CLAUDE.md current. Whenever significant structure is added (new language, framework, CI pipeline, test setup), update the relevant sections above so future AI sessions start with accurate context.
