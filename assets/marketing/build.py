#!/usr/bin/env python3
"""Render the Jevantic comparison animations from their executable examples."""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from functools import cache
from pathlib import Path

FPS = 30
FRAME_COUNT = 120
WIDTH = 1920
HEIGHT = 1080
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
RSVG = Path('/opt/homebrew/bin/rsvg-convert')
FFMPEG = Path('/opt/homebrew/bin/ffmpeg')
FFPROBE = Path('/opt/homebrew/bin/ffprobe')


@dataclass(frozen=True)
class Clip:
    name: str
    headline: str
    before_label: str
    after_label: str
    supporting_line: str
    source: str = 'comparisons.py'


CLIPS = (
    Clip(
        name='choice',
        headline='Select directly from your objects.',
        before_label='Manual mapping',
        after_label='Jevaluator.select',
        supporting_line='Fields inferred. Original object returned.',
    ),
    Clip(
        name='fanout',
        headline='One question, many inputs.',
        before_label='Custom orchestration',
        after_label='evaluate_many',
        supporting_line='Bounded requests. Input-order results.',
    ),
    Clip(
        name='input-guardrail',
        headline="Guard an agent's input.",
        before_label='Explicit policy wiring',
        after_label='InputGuardrail',
        supporting_line='One condition. An explicit threshold.',
        source='input_guardrail_comparison.py',
    ),
    Clip(
        name='output-guardrail',
        headline="Guard an agent's output.",
        before_label='Explicit policy wiring',
        after_label='OutputGuardrail',
        supporting_line='Check the completed response.',
        source='output_guardrail_comparison.py',
    ),
)


def executable(name: Path) -> str:
    if shutil.which(str(name)):
        return str(name)
    raise RuntimeError(f'Required executable is unavailable: {name}')


@cache
def marked_excerpt(clip: Clip, side: str) -> list[str]:
    example = PROJECT_ROOT / 'examples' / clip.source
    source = example.read_text(encoding='utf-8')
    start = f'# clip: {clip.name}-{side}-start'
    end = f'# clip: {clip.name}-{side}-end'
    try:
        body = source.split(start, 1)[1].split(end, 1)[0]
    except IndexError as error:
        raise RuntimeError(f'Missing markers {start!r} / {end!r} in {example}') from error
    return textwrap.dedent(body).strip().splitlines()


def syntax_line(line: str) -> str:
    """Apply a deliberately restrained syntax treatment without changing the excerpt."""
    token = re.compile(
        r"""('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|"""
        r'\b(?:async|await|return|for|in|with|as)\b|'
        r'\b(?:Question|Jevaluator|InputGuardrail|OutputGuardrail)\b)'
    )
    parts: list[str] = []
    position = 0
    for match in token.finditer(line):
        parts.append(html.escape(line[position : match.start()]))
        value = html.escape(match.group())
        if value.startswith(('"', "'")):
            color = '#a8dba8'
        elif value in {'Question', 'Jevaluator', 'InputGuardrail', 'OutputGuardrail'}:
            color = '#c9b5ff'
        else:
            color = '#f1c982'
        parts.append(f'<tspan fill="{color}">{value}</tspan>')
        position = match.end()
    parts.append(html.escape(line[position:]))
    return ''.join(parts) or ' '


def card_svg(clip: Clip, side: str, opacity: float = 1.0) -> str:
    code = marked_excerpt(clip, side)
    excerpts = (marked_excerpt(clip, 'before'), marked_excerpt(clip, 'after'))
    longest_line = max(len(line) for excerpt in excerpts for line in excerpt)
    line_height = min(52, 260 / max(1, max(len(excerpt) for excerpt in excerpts) - 1))
    font_size = min(30, 1468 / (longest_line * 0.61), line_height * 0.85)
    is_after = side == 'after'
    label = clip.after_label if is_after else clip.before_label
    accent = '#71b878' if is_after else '#8e72d8'
    label_color = '#a8dba8' if is_after else '#c9b5ff'
    card_y = 398
    code_y = card_y + 182
    lines: list[str] = []
    for number, line in enumerate(code, start=1):
        y = code_y + (number - 1) * line_height
        lines.append(
            f'<text x="{192}" y="{y}" class="line-number">{number:02d}</text>'
            f'<text x="{260}" y="{y}" class="code" style="font-size:{font_size:.2f}px" '
            f'xml:space="preserve">{syntax_line(line)}</text>'
        )
    support = clip.supporting_line if is_after else ' '
    support_opacity = '1' if is_after else '0'
    return f'''<g opacity="{opacity:.5f}">
  <rect x="132" y="{card_y}" width="1656" height="510" rx="30" fill="#202127"/>
  <rect x="132" y="{card_y}" width="14" height="510" rx="7" fill="{accent}"/>
  <rect x="188" y="448" width="346" height="54" rx="27" fill="{accent}" opacity="0.18"/>
  <text x="218" y="484" class="label" fill="{label_color}">{html.escape(label)}</text>
  <line x1="188" y1="526" x2="1728" y2="526" stroke="#42444d" stroke-width="2"/>
  {''.join(lines)}
  <text x="188" y="885" class="support" fill="#a8dba8" opacity="{support_opacity}">{html.escape(support)}</text>
</g>'''


def frame_svg(clip: Clip, before_opacity: float, after_opacity: float) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
<style>
  .eyebrow {{ font: 500 25px Menlo, monospace; letter-spacing: 2px; fill: #5d5b61; }}
  .headline {{ font: 700 72px Menlo, monospace; letter-spacing: -2.7px; fill: #222226; }}
  .label {{ font: 700 23px Menlo, monospace; letter-spacing: .2px; }}
  .code {{ font: 500 30px Menlo, monospace; fill: #f4f0eb; }}
  .line-number {{ font: 500 22px Menlo, monospace; fill: #8f929e; }}
  .support {{ font: 700 30px Menlo, monospace; }}
  .footer {{ font: 500 22px Menlo, monospace; fill: #5d5b61; }}
  .brand {{ font: 700 26px Menlo, monospace; letter-spacing: 1px; fill: #222226; }}
</style>
<rect width="{WIDTH}" height="{HEIGHT}" fill="#f7f2ea"/>
<rect x="0" y="0" width="{WIDTH}" height="12" fill="#8e72d8"/>
<text x="264" y="176" class="eyebrow">JEVANTIC · TYPED DECISIONS</text>
<text x="264" y="284" class="headline">{html.escape(clip.headline)}</text>
{card_svg(clip, 'before', before_opacity)}
{card_svg(clip, 'after', after_opacity)}
<text x="264" y="938" class="footer">Excerpt · full runnable example included</text>
<text x="1487" y="938" class="brand">jevantic</text>
</svg>'''


def render_svg(svg: Path, png: Path) -> None:
    subprocess.run(
        [executable(RSVG), '--width', str(WIDTH), '--height', str(HEIGHT), '-o', str(png), str(svg)], check=True
    )


def write_clip(clip: Clip) -> Path:
    output = ROOT / clip.name
    output.mkdir(parents=True, exist_ok=True)

    for side in ('before', 'after'):
        svg = output / f'{side}.svg'
        png = output / f'{side}.png'
        svg.write_text(frame_svg(clip, float(side == 'before'), float(side == 'after')), encoding='utf-8')
        render_svg(svg, png)

    mp4 = output / f'{clip.name}.mp4'
    with tempfile.TemporaryDirectory(prefix=f'{clip.name}-frames-', dir=output) as frames_directory:
        frames = Path(frames_directory)
        for frame in range(FRAME_COUNT):
            if frame < 57:
                before, after = 1.0, 0.0
            elif frame < 63:
                after = (frame - 56) / 7
                before = 1 - after
            else:
                before, after = 0.0, 1.0
            svg = frames / f'frame-{frame:03d}.svg'
            png = frames / f'frame-{frame:03d}.png'
            svg.write_text(frame_svg(clip, before, after), encoding='utf-8')
            render_svg(svg, png)

        subprocess.run(
            [
                executable(FFMPEG),
                '-y',
                '-hide_banner',
                '-loglevel',
                'error',
                '-framerate',
                str(FPS),
                '-start_number',
                '0',
                '-i',
                str(frames / 'frame-%03d.png'),
                '-frames:v',
                str(FRAME_COUNT),
                '-c:v',
                'libx264',
                '-pix_fmt',
                'yuv420p',
                '-movflags',
                '+faststart',
                '-r',
                str(FPS),
                str(mp4),
            ],
            check=True,
        )
    return mp4


def verify(mp4: Path) -> None:
    probe = subprocess.run(
        [
            executable(FFPROBE),
            '-v',
            'error',
            '-count_frames',
            '-select_streams',
            'v:0',
            '-show_entries',
            'stream=width,height,r_frame_rate,nb_read_frames:format=duration',
            '-of',
            'default=noprint_wrappers=1',
            str(mp4),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    expected = {'width=1920', 'height=1080', 'r_frame_rate=30/1', 'nb_read_frames=120', 'duration=4.000000'}
    missing = expected.difference(probe.splitlines())
    if missing:
        raise RuntimeError(f'Unexpected media metadata for {mp4}: {probe} (missing {sorted(missing)!r})')
    print(f'Verified {mp4.relative_to(PROJECT_ROOT)}: 1920x1080, 30fps, 120 frames, 4.0 seconds')


def main() -> None:
    for clip in CLIPS:
        verify(write_clip(clip))


if __name__ == '__main__':
    main()
