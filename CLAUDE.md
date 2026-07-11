# CLAUDE.md

Guidance for AI assistants (and human contributors) working in this repository.
Keep this file honest: if a section is out of date, fix it in the same PR that
changes tooling, layout, or conventions.

## Project status

`vigilant-enigma` is a freshly-initialized repository. As of this commit the
only tracked file besides this one is [`LICENSE`](./LICENSE) (GPL v2). There
is no source code, no README, no package manifest, no test suite, and no CI.

Treat this file as the source of truth for project conventions. When you add
the first piece of tooling or code, replace the relevant TODO section below
with the actual details instead of leaving assumptions in your head.

## Repository layout

```
.
├── CLAUDE.md   # this file
└── LICENSE     # GNU GPL v2
```

When you add a top-level directory (for example `src/`, `tests/`, `docs/`,
`scripts/`), add it to the tree above with a one-line description.

## License

GNU General Public License v2.0. New source files should carry a GPL v2-
compatible header once a language and header style have been chosen. Do not
introduce dependencies whose licenses are incompatible with GPL v2 without
first discussing it in a PR.

## Build & run

TODO — no build tooling exists yet.

When a package manager or build system is introduced (`package.json`,
`pyproject.toml`, `Cargo.toml`, `go.mod`, `Makefile`, etc.), replace this
section with:

- The install command (e.g. `npm ci`, `uv sync`, `cargo build`).
- The primary run command for the app or library.
- Any required environment variables, and where their example values live.

## Testing

TODO — no tests exist yet.

When tests are added, document here:

- The test framework and where tests live.
- The command to run the full suite.
- The command to run a single test file or a single test case.

## Linting & formatting

TODO — no linter or formatter is configured.

Once one is added, record:

- The lint command and the format command.
- Any pre-commit hooks (and how to install them).
- Whether formatting is enforced in CI.

## Architecture / source map

TODO — no source code exists yet.

Once a source tree exists, describe each top-level module or package in one
or two sentences. Prefer short paragraphs over exhaustive file listings.

## Conventions

TODO — no conventions have been established yet.

Capture conventions here as they emerge, for example:

- Naming rules for files, types, and functions.
- Error-handling patterns.
- Commit message style (Conventional Commits? Free-form?).
- Any patterns that should be reused instead of reinvented.

## CI / CD

TODO — there is no `.github/workflows/` directory yet.

When workflows are added, list each one, what triggers it (push, PR, tag),
and what it does (lint, test, build, release). Note any required repository
secrets by name (never paste their values).

## Git workflow

- Default branch: `main`.
- Remote: `https://github.com/7big1head4/vigilant-enigma`.
- Feature work happens on a topic branch; open pull requests against `main`.
- Pull requests are opened as drafts and marked ready for review once CI is
  green and the change is complete.
- Keep this file in sync with reality: any PR that changes tooling, layout,
  or conventions should update the relevant section of `CLAUDE.md` in the
  same PR.

## Instructions for AI assistants

- Do not fabricate details about code, tooling, or conventions that do not
  exist. If a section still says TODO, that means there is nothing to
  describe yet — leave it as TODO rather than inventing content.
- Prefer editing this file over creating parallel documentation.
- If you introduce the first version of something (a package manifest, a
  test framework, a CI workflow), replace the corresponding TODO section in
  the same commit.
