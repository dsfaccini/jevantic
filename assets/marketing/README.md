# Jevantic comparison clips

Four silent, four-second 1920×1080 `MP4` clips compare explicit caller wiring with the corresponding Jevantic convenience API.

| Clip | Before | After | Timing |
| --- | --- | --- | --- |
| `choice` | Manual mapping | `Jevaluator.select` | 1.9s / 0.2s fade / 1.9s |
| `fanout` | Custom orchestration | `evaluate_many` | 1.9s / 0.2s fade / 1.9s |
| `input-guardrail` | Question, evaluator, callback | `block_if` and `threshold` | 1.9s / 0.2s fade / 1.9s |
| `output-guardrail` | Question, evaluator, callback | `block_if` and `threshold` | 1.9s / 0.2s fade / 1.9s |

The snippets come directly from marked blocks in the [core comparison](../../examples/comparisons.py), [input guardrail comparison](../../examples/input_guardrail_comparison.py), and [output guardrail comparison](../../examples/output_guardrail_comparison.py). Their tests exercise the complete functions through the SDK, using deterministic local HTTP responses. The guardrail comparisons show two supported ways to express the same policy. They do not present historical syntax as executable current code.

The cards identify their content as an excerpt. Font size and line spacing account for the complete excerpt, with the same scale on both sides of each comparison.

## Reproduce

Run from the repository root with the project’s Python 3.13 environment:

```sh
./.venv/bin/python assets/marketing/build.py
```

`build.py` uses only the standard library plus `/opt/homebrew/bin/rsvg-convert`, `ffmpeg`, and `ffprobe`. It emits each endpoint poster (`before.svg`/`after.svg` and `PNG` counterparts) and an `H.264` `yuv420p` `faststart` `MP4` in each clip directory. Render frames are temporary. The script fails unless `ffprobe` confirms 1920×1080, 30fps, 120 frames, and exactly 4.0 seconds.

The media makes no speed, quality, percentage, line-count, or raw-SDK claims.
