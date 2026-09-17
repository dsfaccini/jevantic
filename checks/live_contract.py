"""Opt-in live contract probe using synthetic content and a caller-selected .env."""

import argparse
import asyncio
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import typesafe_sdk
from dotenv import dotenv_values
from pydantic import JsonValue, TypeAdapter

from jevantic import Question

response_adapter: TypeAdapter[dict[str, JsonValue]] = TypeAdapter(dict[str, JsonValue])


@dataclass
class Case:
    name: str
    questions: dict[str, Question[object]]
    raw_questions: dict[str, typesafe_sdk.Question] = field(default_factory=dict[str, typesafe_sdk.Question])


async def main(env_file: Path, output: Path, selected_case: str | None) -> None:
    api_key = dotenv_values(env_file, interpolate=False).get('TYPESAFE_API_KEY')
    if not api_key:
        raise SystemExit('The selected environment file must define TYPESAFE_API_KEY')
    state: dict[str, JsonValue] = {
        'ticket': 'I was charged twice for my subscription. Please refund the duplicate payment.'
    }
    many_levels: list[str] = [f'A request matching category {index}' for index in range(11)]
    cases: list[Case] = [
        Case(
            'three_primitives',
            {
                'refund': Question.noul('Does the customer request a refund?'),
                'department': Question.choice(
                    {'billing': 'Charges and payments', 'shipping': 'Parcel delivery', 'technical': 'Software faults'},
                    instructions='Which department should handle this request?',
                ),
                'urgency': Question.score(
                    ['No action requested', 'Routine request', 'Immediate harm'],
                    instructions='How urgent is this request?',
                ),
            },
        ),
        Case(
            'structured_rubric',
            {
                'fit': Question.score(
                    [('Unrelated', 'No billing issue'), {'meaning': 'Concerns a charge or payment'}],
                    instructions={'question': 'Does this request concern billing?'},
                )
            },
        ),
        Case('omitted_instructions', {'refund': Question.noul(true='Requests a refund', false='No refund requested')}),
        Case('one_level_score', {'fit': Question.score(['Billing request'], instructions='How well does it fit?')}),
        Case(
            'eleven_level_score',
            {},
            {'fit': typesafe_sdk.Score(criteria=many_levels, instructions='Which category fits best?')},
        ),
        Case(
            'precision',
            {
                'tone': Question.choice(
                    {
                        'neutral': None,
                        'mildly_annoyed': None,
                        'frustrated': None,
                        'polite': None,
                        'concerned': None,
                        'angry': None,
                    },
                    instructions='What is the single best description of the tone?',
                ),
                'impact': Question.score(
                    [
                        'No impact',
                        'Small inconvenience',
                        'Moderate difficulty',
                        'Substantial disruption',
                        'Severe harm',
                    ],
                    instructions='Estimate the wider impact of this problem on the customer from the limited evidence.',
                ),
                'clarity': Question.score(
                    ['Impossible to understand', 'Partly clear', 'Understandable', 'Mostly clear', 'Completely clear'],
                    instructions='How clear is the request about the desired outcome and how to achieve it?',
                ),
            },
        ),
    ]
    if selected_case is not None and selected_case not in {case.name for case in cases}:
        raise SystemExit('Unknown probe case')
    observations: list[JsonValue] = []
    async with typesafe_sdk.AsyncTypeSafeClient(
        api_key=api_key, retry=typesafe_sdk.RetryPolicy(max_retries=0)
    ) as client:
        for case in cases:
            if selected_case is not None and selected_case != case.name:
                continue
            observation: dict[str, JsonValue] = {'case': case.name}
            try:
                response = await client.system_one(
                    state,
                    {name: question.to_request() for name, question in case.questions.items()} | case.raw_questions,
                )
            except typesafe_sdk.TypeSafeAPIError as error:
                observation.update(
                    status=error.status,
                    error_type=type(error).__name__,
                    request_id=error.request_id,
                    detail=str(error).replace(api_key, '[redacted]'),
                )
                observations.append(observation)
                if error.status in (401, 403, 429):
                    break
            except typesafe_sdk.TypeSafeError as error:
                observation['error_type'] = type(error).__name__
                observations.append(observation)
                break
            else:
                validation_errors: dict[str, JsonValue] = {}
                numeric_deltas: dict[str, JsonValue] = {}
                for name, question in case.questions.items():
                    if name not in response.answers:
                        validation_errors[name] = 'Missing answer'
                        continue
                    raw_answer = response.answers[name]
                    if isinstance(raw_answer, typesafe_sdk.ScoreAnswer):
                        numeric_deltas[name] = abs(
                            raw_answer.score - math.fsum(level * p for level, p in raw_answer.probabilities.items())
                        )
                    elif isinstance(raw_answer, typesafe_sdk.ChoiceAnswer):
                        numeric_deltas[name] = abs(math.fsum(raw_answer.probabilities.values()) - 1)
                    try:
                        question.decode(raw_answer)
                    except ValueError as error:
                        validation_errors[name] = str(error)
                observation.update(
                    status=response.raw_http_response.status_code,
                    request_id=response.request_id,
                    response=response_adapter.validate_json(response.raw_http_response.content),
                    validation_errors=validation_errors,
                    numeric_deltas=numeric_deltas,
                )
                observations.append(observation)
    report: dict[str, JsonValue] = {
        'observed_at': datetime.now(UTC).isoformat(),
        'sdk_version': version('typesafe-sdk'),
        'input': state,
        'observations': observations,
    }
    output.write_text(json.dumps(report, indent=2) + '\n')
    for recorded in observations:
        print(json.dumps(recorded))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', default=None)
    args = parser.parse_args()
    asyncio.run(main(args.env_file, args.output, args.case))
