"""Require Pyright to reject every marked invalid public API expression."""

import subprocess
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel


class Position(BaseModel):
    line: int


class Range(BaseModel):
    start: Position


class Diagnostic(BaseModel):
    severity: Literal['error', 'warning', 'information']
    rule: str | None = None
    range: Range


class Report(BaseModel):
    generalDiagnostics: list[Diagnostic]


def main() -> None:
    fixture = Path('typecheck/invalid.py')
    expected: set[tuple[int, str]] = {
        (line_number, line.partition('# expect: ')[2].strip())
        for line_number, line in enumerate(fixture.read_text().splitlines())
        if '# expect: ' in line
    }
    if not expected:
        raise SystemExit('No negative typing expectations found')
    process = subprocess.run(
        [sys.executable, '-m', 'pyright', str(fixture), '--outputjson'],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 1:
        raise SystemExit(f'Expected Pyright type errors; exit={process.returncode}\n{process.stdout}\n{process.stderr}')
    report = Report.model_validate_json(process.stdout)
    actual = {(item.range.start.line, item.rule) for item in report.generalDiagnostics if item.severity == 'error'}
    expected_lines = {line for line, _ in expected}
    missing = expected - actual
    unexpected = {(line, rule) for line, rule in actual if line not in expected_lines}
    if missing or unexpected:
        raise SystemExit(f'Negative typing mismatch: missing={missing}, unexpected={unexpected}')
    print('Negative public API type checks passed')


if __name__ == '__main__':
    main()
