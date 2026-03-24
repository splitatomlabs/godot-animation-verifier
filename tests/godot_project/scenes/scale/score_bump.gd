extends Node2D

## Score label scale-bump with TRANS_BACK.
##
## After 0.2s idle: tween scale to 1.2 (EASE_OUT, 0.1s), change text in
## callback, tween scale back to 1.0 (EASE_OUT + TRANS_BACK, 0.15s).

var _label: Label
var _bumped: bool = false
var _elapsed: float = 0.0


func _ready() -> void:
	_label = $Label
	_label.text = "Score: 0"
	_label.pivot_offset = _label.size / 2.0


func _process(delta: float) -> void:
	_elapsed += delta
	if not _bumped and _elapsed >= 0.2:
		_bumped = true
		_bump_score()


func _bump_score() -> void:
	var tween := create_tween()
	# Scale up to 1.2 over 0.1s, ease-out
	tween.tween_property(_label, "scale", Vector2(1.2, 1.2), 0.1) \
		.set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_CUBIC)
	# Change text at peak scale
	tween.tween_callback(_change_text)
	# Scale back to 1.0 over 0.15s, ease-out + TRANS_BACK
	tween.tween_property(_label, "scale", Vector2(1.0, 1.0), 0.15) \
		.set_ease(Tween.EASE_OUT).set_trans(Tween.TRANS_BACK)


func _change_text() -> void:
	_label.text = "Score: 1"
