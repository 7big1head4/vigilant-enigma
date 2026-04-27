# Template: CLI Tool Scaffold

Create a new CLI with:
- Clean command structure + help text
- Input validation + error handling
- Example usage for every command
- Follow four priorities: Speed → Correctness → Maintainability → Minimalism

## Recommended File Structure

```
[tool-name]/
├── src/
│   ├── main.[ext]       # Entry point
│   ├── cli.[ext]        # Argument parsing + help text
│   └── [feature].[ext]  # Core logic modules
├── tests/
│   └── test_[feature].[ext]
├── README.md
└── [package manifest]   # package.json / pyproject.toml / Cargo.toml
```

## Checklist

- [ ] `--help` and `--version` on every command
- [ ] Input validated at CLI boundary only
- [ ] Meaningful exit codes: 0 = success, 1 = user error, 2 = internal error
- [ ] Example usage block in README for every command
- [ ] No logic in the entry point — delegate immediately
