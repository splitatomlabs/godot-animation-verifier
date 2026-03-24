---
name: verify-animations
description: Capture and analyze a Godot scene for missing animations using --write-movie
---

# Verify Animations

Capture a Godot scene and analyze it for missing or broken animations.

## Prerequisites

Before running any commands, check that the `godot-animation-verifier` CLI is available on PATH. If not found, install it from the repo:

```
pip install godot-animation-verifier
```

Adapt the install command to the platform — use `pipx`, `pip install --user`, `pip3`, or a virtual environment, whichever is appropriate for the user's system. Confirm with `godot-animation-verifier --version`.

## Usage

1. **Capture and analyze** a scene in one step:

```bash
godot-animation-verifier capture <scene-path> --analyze --output capture.avi
```

- `<scene-path>` is the **filesystem path** to a `.tscn` file (not `res://`).
- Use `--godot <path>` if the Godot binary is not on PATH.
- Use `--duration <frames>` to control how many frames to capture (default: 60). Omit this flag to let the scene run until it quits on its own (e.g. demo mode).
- Godot captures at its natural frame rate. Analysis always samples at 15 fps.

**Important:** The capture command launches Godot with `--write-movie`, which requires a display. Run the Bash command with `dangerouslyDisableSandbox: true`.

2. **Parse the JSON output.** The `--analyze` flag prints a JSON diagnostic:

```json
{
  "pass": false,
  "issues": [
    {
      "node": "root",
      "timestamp_ms": 200,
      "type": "MISSING_ANIMATION",
      "severity": "error",
      "hint": "Abrupt position change detected..."
    }
  ],
  "frame_count": 60
}
```

- `pass: true` means no animation issues were found.
- Each issue includes the node, timestamp, type, severity, and a hint for fixing.

3. **Fix and re-verify.** If issues are found, fix the animation in the scene file and run the capture again to confirm the fix.

## Analyze existing video

To analyze a previously captured video or directory of PNG frames without re-capturing:

```bash
godot-animation-verifier analyze <path>
```
