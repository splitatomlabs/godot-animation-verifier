"""Tests for animation suggestion lookup."""

import pytest

from godot_animation_verifier.models import ChangeType
from godot_animation_verifier.suggestions import get_animation_suggestions


class TestGetAnimationSuggestions:
    @pytest.mark.parametrize("change_type", list(ChangeType))
    def test_returns_list_for_all_change_types(self, change_type: ChangeType) -> None:
        result = get_animation_suggestions(change_type, "center")
        assert isinstance(result, list)
        assert 2 <= len(result) <= 4

    @pytest.mark.parametrize("change_type", list(ChangeType))
    def test_suggestion_structure(self, change_type: ChangeType) -> None:
        result = get_animation_suggestions(change_type, "center")
        for s in result:
            assert "style" in s
            assert "description" in s
            assert "fits" in s

    def test_disappear_suggestions(self) -> None:
        result = get_animation_suggestions(ChangeType.DISAPPEAR, "center")
        styles = [s["style"] for s in result]
        assert "fade" in styles

    def test_appear_suggestions(self) -> None:
        result = get_animation_suggestions(ChangeType.APPEAR, "center")
        styles = [s["style"] for s in result]
        assert "fade-in" in styles

    def test_position_jump_suggestions(self) -> None:
        result = get_animation_suggestions(ChangeType.POSITION_JUMP, "center")
        styles = [s["style"] for s in result]
        assert "slide" in styles

    def test_corner_zone_prioritizes_hud(self) -> None:
        result = get_animation_suggestions(ChangeType.DISAPPEAR, "top-left")
        # HUD-oriented should come first
        assert result[0]["fits"] == "HUD"

    def test_center_zone_prioritizes_gameplay(self) -> None:
        result = get_animation_suggestions(ChangeType.DISAPPEAR, "center")
        # Gameplay-oriented should come first
        assert result[0]["fits"] == "gameplay"

    def test_general_zone_keeps_default_order(self) -> None:
        result = get_animation_suggestions(ChangeType.DISAPPEAR, "top-center")
        # No reordering for non-corner, non-center zones
        assert result[0]["style"] == "pop"
