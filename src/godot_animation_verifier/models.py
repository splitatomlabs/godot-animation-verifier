"""Data models for godot_animation_verifier diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IssueType(Enum):
    """Type of animation issue detected."""

    MISSING_ANIMATION = "MISSING_ANIMATION"


class ChangeType(Enum):
    """Classification of the visual change detected."""

    APPEAR = "appear"
    DISAPPEAR = "disappear"
    COLOR_CHANGE = "color_change"
    POSITION_JUMP = "position_jump"
    SIZE_CHANGE = "size_change"


@dataclass
class Issue:
    """A single animation issue found in a Godot UI node."""

    node: str
    timestamp_ms: int
    type: IssueType
    severity: str
    hint: str
    change: ChangeType | None = None
    region: dict | None = None
    screen_zone: str = ""
    metrics: dict = field(default_factory=dict)
    animation_suggestions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict matching the PRD schema."""
        return {
            "node": self.node,
            "timestamp_ms": self.timestamp_ms,
            "type": self.type.value,
            "severity": self.severity,
            "hint": self.hint,
            "change": self.change.value if self.change else None,
            "region": self.region,
            "screen_zone": self.screen_zone,
            "metrics": self.metrics,
            "animation_suggestions": self.animation_suggestions,
        }


@dataclass
class DiagnosticResult:
    """Top-level result returned by godot_animation_verifier analysis.

    ``pass_field`` serializes as ``"pass"`` in JSON output because ``pass``
    is a reserved keyword in Python.
    """

    pass_field: bool
    issues: list[Issue] = field(default_factory=list)
    frame_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict matching the PRD schema."""
        return {
            "pass": self.pass_field,
            "issues": [issue.to_dict() for issue in self.issues],
            "frame_count": self.frame_count,
        }
