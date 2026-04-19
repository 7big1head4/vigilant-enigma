# CLAUDE.md

This file provides guidance for AI assistants (Claude and others) working in this repository.

## Repository Overview

**vigilant-enigma** is a personal AI workspace that implements a four-folder persistent memory system for Claude. It contains structured context Claude reads at the start of each session to maintain continuity across conversations.

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

## Persistent Memory System

At the start of every session, Claude should read the following in order:

1. **`ABOUT_ME/profile.md`** — User background, working style, priorities, and standing instructions
2. **`Projects/`** — Read the relevant project file(s) for the current session's focus
3. **`Templates/`** — Check here before creating any reusable artifact from scratch
4. **`Outputs/`** — Reference past outputs when continuing existing work

| Folder | Purpose |
|---|---|
| `ABOUT_ME/` | Who the user is and how they want to work |
| `Projects/` | Active project briefs, organized by type (software/, business/, personal/) |
| `Templates/` | Reusable prompts, docs, code scaffolds, and comms |
| `Outputs/` | Saved artifacts organized by project |

---

## File Structure (current)

```
vigilant-enigma/
├── ABOUT_ME/
│   └── profile.md               # User profile and Claude instructions
├── Projects/
│   ├── README.md                # How to add/manage projects
│   ├── software/                # Software & app projects
│   ├── business/                # Strategy, plans, SOPs
│   └── personal/                # Learning & personal projects
├── Templates/
│   ├── README.md
│   ├── prompts/                 # Reusable Claude prompts
│   ├── docs/                    # PRDs, briefs, reports
│   ├── code/                    # Scaffolds & boilerplate
│   └── comms/                   # Emails, proposals, posts
├── Outputs/
│   └── README.md                # Output naming & storage conventions
├── LICENSE                      # GNU GPL v2.0
└── CLAUDE.md                    # This file
```

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
