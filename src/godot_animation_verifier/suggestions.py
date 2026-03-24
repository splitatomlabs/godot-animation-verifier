"""Animation suggestion lookup table mapping (change_type, screen_zone) to suggestions."""

from __future__ import annotations

from godot_animation_verifier.models import ChangeType

# Base suggestions by change type
_BASE_SUGGESTIONS: dict[ChangeType, list[dict]] = {
    ChangeType.DISAPPEAR: [
        {"style": "pop", "description": "Scale down to zero with slight overshoot", "fits": "gameplay"},
        {"style": "absorb", "description": "Shrink toward a focal point with easing", "fits": "gameplay"},
        {"style": "fade", "description": "Fade alpha to 0 over ~300ms", "fits": "general"},
        {"style": "slide-out", "description": "Slide off-screen in the nearest direction", "fits": "HUD"},
    ],
    ChangeType.APPEAR: [
        {"style": "grow", "description": "Scale from zero with elastic overshoot", "fits": "gameplay"},
        {"style": "fade-in", "description": "Fade alpha from 0 to 1 over ~300ms", "fits": "general"},
        {"style": "slide-in", "description": "Slide in from off-screen edge", "fits": "HUD"},
    ],
    ChangeType.POSITION_JUMP: [
        {"style": "slide", "description": "Tween position with ease-out over ~300ms", "fits": "general"},
        {"style": "teleport-flash", "description": "Brief flash at old and new positions", "fits": "gameplay"},
    ],
    ChangeType.COLOR_CHANGE: [
        {"style": "crossfade", "description": "Blend between old and new color over ~200ms", "fits": "general"},
        {"style": "pulse", "description": "Pulse highlight before settling on new color", "fits": "gameplay"},
    ],
    ChangeType.SIZE_CHANGE: [
        {"style": "scale-tween", "description": "Tween scale with ease-out over ~300ms", "fits": "general"},
        {"style": "bounce", "description": "Scale with elastic bounce at target size", "fits": "gameplay"},
    ],
}

# Corner zones suggest HUD-oriented animations
_CORNER_ZONES = {"top-left", "top-right", "bottom-left", "bottom-right"}
# Center zone suggests gameplay-oriented animations
_CENTER_ZONES = {"center"}


def get_animation_suggestions(change_type: ChangeType, screen_zone: str) -> list[dict]:
    """Return 2-4 animation suggestions for a given change type and screen zone.

    Screen zone modifies the ordering: corner zones prioritize HUD-oriented
    suggestions, center zones prioritize gameplay-oriented suggestions.
    """
    base = _BASE_SUGGESTIONS.get(change_type, [])
    if not base:
        return []

    suggestions = [dict(s) for s in base]  # shallow copy each dict

    if screen_zone in _CORNER_ZONES:
        # Prioritize HUD-oriented suggestions
        suggestions.sort(key=lambda s: 0 if s["fits"] == "HUD" else 1)
    elif screen_zone in _CENTER_ZONES:
        # Prioritize gameplay-oriented suggestions
        suggestions.sort(key=lambda s: 0 if s["fits"] == "gameplay" else 1)

    return suggestions[:4]
