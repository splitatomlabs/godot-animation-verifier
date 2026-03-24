#!/usr/bin/env python3
"""Smoke test: verifies that Claude Code can use the verify-animations skill end-to-end.

This is a standalone script (not pytest) because it requires the `claude` CLI,
a Godot binary with a display, and tests that the skill auto-installs
`godot-animation-verifier` when it is not already present.

Usage:
    python tests/skill_smoke_test.py

For a meaningful test, run from an environment where `godot-animation-verifier`
is NOT already installed (e.g. a fresh venv).
"""

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# Paths relative to repo root
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE_PROJECT_GODOT = os.path.join(REPO_ROOT, "tests", "godot_project", "project.godot")
SOURCE_SKILL_MD = os.path.join(REPO_ROOT, "skills", "verify-animations", "SKILL.md")
SOURCE_SCENES_DIR = os.path.join(REPO_ROOT, "tests", "godot_project", "scenes")


# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------

def check_prerequisites():
    """Check for required binaries. Returns a list of missing prerequisite names."""
    missing = []

    if shutil.which("claude") is None:
        missing.append("claude (Claude Code CLI — install from https://claude.ai/code)")

    # Accept common Godot binary names
    godot_names = ["godot", "godot4", "godot-4", "Godot", "Godot4"]
    if not any(shutil.which(name) for name in godot_names):
        missing.append("godot (Godot 4 binary — must be on PATH)")

    if shutil.which("godot-animation-verifier") is not None:
        print(
            "WARNING: godot-animation-verifier is already on PATH — "
            "the self-install path will NOT be exercised.\n"
            "  For a meaningful test, run from a fresh venv without the package installed."
        )

    return missing


# ---------------------------------------------------------------------------
# Workspace creation
# ---------------------------------------------------------------------------

_workspace_dir: str | None = None


def create_workspace() -> str:
    """Create a temporary workspace and return its path."""
    global _workspace_dir

    workspace = tempfile.mkdtemp(prefix="gav_smoke_")
    _workspace_dir = workspace

    # Register cleanup to run on exit
    atexit.register(_cleanup_workspace)

    # 1. Copy project.godot
    shutil.copy2(SOURCE_PROJECT_GODOT, os.path.join(workspace, "project.godot"))

    # 2. Copy SKILL.md into .claude/skills/verify-animations/
    skill_dest_dir = os.path.join(workspace, ".claude", "skills", "verify-animations")
    os.makedirs(skill_dest_dir, exist_ok=True)
    shutil.copy2(SOURCE_SKILL_MD, os.path.join(skill_dest_dir, "SKILL.md"))

    # 3. Write CLAUDE.md
    claude_md_content = """\
# Agent Instructions

You are operating inside a Godot project workspace. Use the `/verify-animations` skill
to capture and analyze Godot scenes.

## Important notes

- The capture command launches Godot with `--write-movie`, which requires a display.
  Always run Bash capture commands with `dangerouslyDisableSandbox: true`.
- Scene paths passed to the tool must be absolute filesystem paths, not `res://` paths.
- Use the `--analyze` flag to get structured JSON diagnostic output.
"""
    with open(os.path.join(workspace, "CLAUDE.md"), "w") as f:
        f.write(claude_md_content)

    # 4. Write .claude/settings.json
    settings = {
        "permissions": {
            "allow": ["Bash(*)"],
            "deny": [],
        }
    }
    settings_path = os.path.join(workspace, ".claude", "settings.json")
    # .claude dir was already created above
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    # 5. Symlink scenes directory
    scenes_link = os.path.join(workspace, "scenes")
    os.symlink(SOURCE_SCENES_DIR, scenes_link)

    return workspace


def _cleanup_workspace():
    global _workspace_dir
    if _workspace_dir and os.path.isdir(_workspace_dir):
        shutil.rmtree(_workspace_dir, ignore_errors=True)
        _workspace_dir = None


def verify_workspace(workspace: str):
    """Assert that all expected files and symlinks exist in the workspace."""
    expected = [
        "project.godot",
        "CLAUDE.md",
        os.path.join(".claude", "settings.json"),
        os.path.join(".claude", "skills", "verify-animations", "SKILL.md"),
        "scenes",  # symlink
    ]
    missing = []
    for rel_path in expected:
        full_path = os.path.join(workspace, rel_path)
        if not os.path.exists(full_path):
            missing.append(rel_path)
    if missing:
        raise RuntimeError(
            f"Workspace verification failed — missing: {', '.join(missing)}"
        )

    # Verify the symlink actually points to the right place
    scenes_link = os.path.join(workspace, "scenes")
    if not os.path.islink(scenes_link):
        raise RuntimeError("'scenes' entry is not a symlink")
    if os.readlink(scenes_link) != SOURCE_SCENES_DIR:
        raise RuntimeError(
            f"'scenes' symlink target mismatch: {os.readlink(scenes_link)!r} != {SOURCE_SCENES_DIR!r}"
        )

    # Verify settings.json is valid JSON with the expected structure
    settings_path = os.path.join(workspace, ".claude", "settings.json")
    with open(settings_path) as f:
        settings = json.load(f)
    if "Bash(*)" not in settings.get("permissions", {}).get("allow", []):
        raise RuntimeError("settings.json does not allow Bash(*)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== Skill Smoke Test ===")
    print()

    # Check prerequisites
    missing = check_prerequisites()
    if missing:
        print("FAIL — missing prerequisites:")
        for item in missing:
            print(f"  - {item}")
        sys.exit(1)

    print("Prerequisites OK.")
    print()

    # Create and verify workspace
    print("Creating temp workspace...")
    workspace = create_workspace()
    print(f"  Workspace: {workspace}")

    print("Verifying workspace contents...")
    try:
        verify_workspace(workspace)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    print("  All expected files present.")
    print()

    # Run agent skill invocation
    print("Running Claude agent with /verify-animations skill...")
    print()

    pass_scene = os.path.join(workspace, "scenes", "missing_pass_static.tscn")
    fail_scene = os.path.join(workspace, "scenes", "missing_fail_position_teleport.tscn")
    results_file = os.path.join(workspace, "results.json")

    prompt = (
        f"Run /verify-animations on these two scenes and write the results to results.json.\n\n"
        f"1. Run: godot-animation-verifier capture {pass_scene} --analyze --output capture_pass.avi --duration 15\n"
        f"   Save the JSON output as pass_scene in results.json.\n\n"
        f"2. Run: godot-animation-verifier capture {fail_scene} --analyze --output capture_fail.avi --duration 15\n"
        f"   Save the JSON output as fail_scene in results.json.\n\n"
        f"Write results.json with this exact structure:\n"
        f'{{"pass_scene": <json from scene 1>, "fail_scene": <json from scene 2>}}\n\n'
        f"The results.json file must be written to: {results_file}\n"
        f"Use dangerouslyDisableSandbox: true for the capture commands."
    )

    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        print(f"ERROR: claude -p exited with code {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr[:500]}")
        sys.exit(1)

    # Read and validate results.json
    if not os.path.exists(results_file):
        print("ERROR: results.json was not created by the agent.")
        if result.stdout:
            print(f"  Agent output (first 500 chars): {result.stdout[:500]}")
        sys.exit(1)

    try:
        with open(results_file) as f:
            results = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"ERROR: results.json is not valid JSON: {exc}")
        sys.exit(1)

    errors = []

    pass_result = results.get("pass_scene")
    if pass_result is None:
        errors.append("results.json missing 'pass_scene' key")
    elif not pass_result.get("pass"):
        errors.append(
            f"Expected pass_scene to have pass=true, got pass={pass_result.get('pass')}"
        )

    fail_result = results.get("fail_scene")
    if fail_result is None:
        errors.append("results.json missing 'fail_scene' key")
    elif "pass" not in fail_result or fail_result["pass"] is not False:
        errors.append(
            f"Expected fail_scene to have pass=false, got: {fail_result}"
        )

    if errors:
        print("FAIL — assertion errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("PASS — both scenes produced expected results:")
    print(f"  pass_scene: pass={pass_result.get('pass')}")
    print(f"  fail_scene: pass={fail_result.get('pass')}, issues={len(fail_result.get('issues', []))}")
    sys.exit(0)


if __name__ == "__main__":
    main()
