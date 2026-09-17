# Jevantic comparison clips

Two silent, four-second 1920×1080 `MP4` clips compare a small caller-owned implementation with the corresponding Jevantic convenience API.

| Clip | Before | After | Timing |
| --- | --- | --- | --- |
| `choice` | Manual mapping | `Question.select` | 1.9s / 0.2s fade / 1.9s |
| `fanout` | Custom orchestration | `evaluate_many` | 1.9s / 0.2s fade / 1.9s |

The snippets are read directly from the marked blocks in [the complete runnable comparison](../../examples/comparisons.py). This prevents marketing media from drifting from the examples. The cards identify their content as an excerpt; the source is the full example.

## Reproduce

Run from the repository root with the project’s Python 3.13 environment:

```sh
./.venv/bin/python assets/marketing/build.py
```

`build.py` uses only the standard library plus `/opt/homebrew/bin/rsvg-convert`, `ffmpeg`, and `ffprobe`. It emits each endpoint poster (`before.svg`/`after.svg` and `PNG` counterparts) and an `H.264` `yuv420p` `faststart` `MP4` in each clip directory. Render frames are temporary. The script fails unless `ffprobe` confirms 1920×1080, 30fps, 120 frames, and exactly 4.0 seconds.

The media makes no speed, quality, percentage, line-count, or raw-SDK claims.
