# Template: CLI Tool Scaffold

Use this as a starting structure for a new command-line tool.

## Recommended File Structure

```
[tool-name]/
├── src/
│   ├── main.[ext]       # Entry point
│   ├── cli.[ext]        # Argument parsing
│   └── [feature].[ext]  # Core logic modules
├── tests/
│   └── test_[feature].[ext]
├── README.md
├── [package manifest]   # package.json / pyproject.toml / Cargo.toml
└── .gitignore
```

## Checklist
- [ ] Input validation at CLI boundary
- [ ] Meaningful exit codes (0 = success, 1 = user error, 2 = internal error)
- [ ] `--help` flag implemented
- [ ] `--version` flag implemented
- [ ] README covers: install, usage, examples
