# Godot Animation Verifier

Detects missing animations in Godot scenes. AI coding agents produce functional games but often skip transitions. Positions, sizes, and opacities snap instantly instead of animating. This tool captures rendered frames, analyzes them for motion discontinuities, and returns a pass/fail diagnostic that agents or developers can act on.

This tool is independent of Godot MCP servers and works great alongside them. MCP servers give agents the ability to edit scenes and manage project state; this tool verifies the visual result of those edits.

## Getting Started

### Prerequisites

- Python 3.x
- Godot Engine 4.x

### Install

Install the Claude Code plugin:

```bash
claude plugin marketplace add splitatomlabs/godot-animation-verifier
claude plugin install godot-animation-verifier@godot-animation-verifier
```

This adds the `/verify-animations` skill. The skill handles installing the CLI and all dependencies automatically on first use.

### Usage

Invoke the skill on any scene:

```
/verify-animations
```

The skill captures the scene, runs detection, and guides fixes for any missing animations it finds.

### CLI

The CLI can integrate into any agentic coding workflow or CI/CD pipeline:

```bash
pip install godot-animation-verifier

# Capture a scene and check for missing animations
godot-animation-verifier capture scene.tscn --analyze

# Pass flags through to Godot (e.g. trigger a demo mode in your game)
godot-animation-verifier capture scene.tscn --analyze --godot-args --demo

# Analyze a previously captured video or frame directory
godot-animation-verifier analyze capture.avi
```

## What It Detects

**Missing animations** — abrupt state changes where position, size, or opacity jumps between values in a single frame instead of transitioning smoothly.

The output is structured JSON:

```json
{
  "pass": false,
  "issues": [
    {
      "type": "MISSING_ANIMATION",
      "severity": "high",
      "timestamp_ms": 200,
      "hint": "Add a Tween or AnimationPlayer to smooth the transition"
    }
  ],
  "frame_count": 60
}
```

Exit code 0 means pass, 1 means issues detected.

## Capture

The `capture` command launches Godot with `--write-movie` to record frames — no GDScript setup required. The scene must be inside a Godot project (a directory containing `project.godot`).

Use `--godot-args` to pass flags through to Godot via the `--` separator. Your game can read them with `OS.get_cmdline_user_args()` to trigger specific flows — demo modes, test scenarios, menu navigation — so you can verify animations for any state your UI can reach.

> **Note:** `--headless` is incompatible with `--write-movie`. Capture requires a windowed Godot process (a display server must be available).

## Test Suite

121 Godot scenes test detection accuracy across a wide range of scenarios:

| Category | Scenes | What it tests |
|---|---|---|
| Object size | 10 | Tiny (20px) through huge (400px) objects |
| Multiple objects | 10 | 2-5 simultaneous objects, mixed motion types |
| Background complexity | 10 | Gradients, checkerboards, noise, color blocks |
| Transition magnitude | 10 | Subtle (50px) through large (400px) movements |
| Animation timing | 10 | Full duration, early stop, late start, multi-phase |
| Spawn and despawn | 10 | Fade in/out, grow/shrink, instant appear/disappear |
| Combined properties | 10 | Simultaneous position + opacity + size changes |
| Viewport position | 10 | Corners, edges, off-screen to center |
| Color and contrast | 10 | Low contrast, high contrast, color snaps |
| Threshold boundaries | 10 | Edge cases near detection thresholds |
| Non-rectangular shapes | 10 | Circles, triangles, mixed shapes |
| Scene transitions | 10 | Scene cuts, loading screens, HUD swaps, cross-dissolves |
| Text animations | 1 | Scale bumps with easing and mid-animation text changes |

On top of these, ~100 unit tests cover the detection pipeline, CLI, and error paths without needing Godot.

```bash
pytest                    # unit/integration (no Godot required)
pytest -m godot           # all Godot capture tests (requires Godot + display)
```

Godot tests cache captured AVI files in `tests/.frame_cache/` keyed by scene content hash. After the first run, repeat runs reuse cached frames and don't need Godot. Use `--refresh-cache` to force recapture.

## Looking Forward

**Better detection accuracy.** The current detector works well on synthetic test scenes. Real-world Godot projects have more visual complexity, including background motion, particle effects, and overlapping UI layers. Improving robustness against these conditions is the immediate priority.

**Animation quality analysis.** Beyond detecting *missing* animations, we want to assess the *quality* of animations that are present. This means flagging easing curves that feel mechanical, transitions that are too fast or too slow, and timing that doesn't match platform conventions.

**Richer agent feedback.** The current output tells an agent what is wrong. Future versions could provide more specific remediation guidance, such as which node to animate, what property to tween, and what duration and easing to use, so agents can fix issues in fewer iterations.

## License

MIT
