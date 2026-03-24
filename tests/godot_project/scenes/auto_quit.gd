extends Node

## Autoload that quits after a configurable number of frames.
## Backup for Godot's --quit-after flag.

@export var max_frames: int = 90

var _frame_count: int = 0


func _process(_delta: float) -> void:
	_frame_count += 1
	if _frame_count >= max_frames:
		get_tree().quit()
