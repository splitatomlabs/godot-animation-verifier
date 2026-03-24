# CLAUDE.md

## Project Overview
Godot Animation Verifier detects missing animations in Godot scenes. It captures viewport frames via `--write-movie`, analyzes motion with OpenCV, and returns structured diagnostics via CLI.

## Quick Start
```bash
pip install godot-animation-verifier
godot-animation-verifier capture my_project/scenes/main.tscn --analyze
```

## Key Facts
- **Language:** Python 3.x
- **Package manager:** pip
- **Package name:** `godot-animation-verifier` (PyPI) / `godot_animation_verifier` (import)
- **CLI command:** `godot-animation-verifier`
- **Key dependencies:** OpenCV
- **License:** MIT (open core)
- **Frame capture:** Godot `--write-movie` engine-level recording

## Detection Types
- `MISSING_ANIMATION` — abrupt state change with no transition

## Output
Structured JSON: `pass` (bool), `issues[]` (node, timestamp_ms, type, severity, hint), `frame_count`

## Project Structure
```
.
├── .claude-plugin/                # Claude Code plugin manifest and marketplace
├── src/godot_animation_verifier/  # Python package: analysis, capture, CLI
├── skills/verify-animations/      # Claude Code skill definition
├── tests/
│   └── fixtures/                  # Auto-generated PNG fixtures
└── ...
```

## Testing
```bash
python -m venv .venv && source .venv/bin/activate   # first time only
pip install -e ".[dev]"                              # first time only
python -m pytest                                     # unit/integration tests (default, safe in sandbox)
python -m pytest -m godot                            # Godot capture tests (needs dangerouslyDisableSandbox)
```
- The default `python -m pytest` excludes the `godot` marker (configured in `pyproject.toml`).
- `godot` tests spawn Godot with `--write-movie` — run them with `dangerouslyDisableSandbox: true`.
- Test fixtures under `tests/fixtures/` are auto-generated on first run via a session-scoped conftest fixture
- Fixture generator: `python tests/generate_fixtures.py`

### Frame caching
Godot capture tests cache AVI files in `tests/.frame_cache/` (gitignored) keyed by scene content hash. Repeat runs skip capture and copy from cache. Use `--refresh-cache` to force recapture:
```bash
python -m pytest -m godot --refresh-cache
```

### Regression protocol
When any file under `src/godot_animation_verifier/` changes (detection, analysis, video, capture, or CLI code), run the **full** test suite before committing:
```bash
python -m pytest                                     # unit/integration (safe in sandbox)
python -m pytest -m godot                            # Godot capture tests (needs dangerouslyDisableSandbox)
```

## Skill
The `/verify-animations` skill (in `skills/verify-animations/SKILL.md`) orchestrates the CLI for agent-driven animation verification. It runs `godot-animation-verifier capture <scene> --analyze` and parses the JSON output.

## Git Conventions
- Commit messages: imperative mood
- Branch naming: kebab-case

## Tool Notes
- `gh` CLI commands (e.g., `gh pr create`) fail under sandbox due to TLS certificate errors. Use `dangerouslyDisableSandbox: true` for `gh` commands.
- The `capture` command launches Godot with `--write-movie`, which requires a display. Use `dangerouslyDisableSandbox: true` for capture commands.
