"""Typer CLI for godot_animation_verifier diagnostics."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import typer

from godot_animation_verifier.analyze import analyze
from godot_animation_verifier.capture import capture_scene
from godot_animation_verifier.frames import load_frames
from godot_animation_verifier.video import load_frames_from_video

app = typer.Typer(invoke_without_command=True)


@app.callback()
def main() -> None:
    """Godot Animation Verifier — detect animation issues in Godot UI."""


@app.command(name="analyze")
def analyze_cmd(
    path: Path = typer.Argument(..., help="Video file or directory of PNGs to analyze"),
    pretty: bool = typer.Option(False, help="Pretty-print JSON output"),
) -> None:
    """Analyze frames for animation issues."""
    try:
        if path.is_dir():
            frames = load_frames(path)
        elif path.is_file():
            frames = load_frames_from_video(path)
        else:
            typer.echo(f"Error: path not found: {path}", err=True)
            raise typer.Exit(code=2)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2)

    result = analyze(frames)

    indent = 2 if pretty else None
    typer.echo(json.dumps(result.to_dict(), indent=indent))

    if not result.pass_field:
        raise typer.Exit(code=1)


@app.command(name="capture")
def capture_cmd(
    scene: Path = typer.Argument(..., help="Filesystem path to the Godot scene file (.tscn)"),
    output: Path = typer.Option(Path("capture.avi"), "--output", "-o", help="Output video file path"),
    godot: str = typer.Option("godot", "--godot", help="Path to Godot binary"),
    duration: int = typer.Option(60, "--duration", "-n", help="Number of frames to capture"),
    run_analyze: bool = typer.Option(False, "--analyze", help="Run analysis on captured video"),
    pretty: bool = typer.Option(False, help="Pretty-print JSON output"),
    godot_args: list[str] = typer.Option([], "--godot-args", help="Extra args passed to Godot (via -- separator). Repeatable."),
) -> None:
    """Capture a Godot scene using --write-movie."""
    try:
        video_path = capture_scene(
            scene_path=scene,
            output_path=output,
            godot_binary=godot,
            duration_frames=duration,
            extra_args=godot_args or None,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=2)

    typer.echo(f"Captured to {video_path}")

    if run_analyze:
        frames = load_frames_from_video(video_path)
        diag = analyze(frames)
        indent = 2 if pretty else None
        typer.echo(json.dumps(diag.to_dict(), indent=indent))
        if not diag.pass_field:
            raise typer.Exit(code=1)


