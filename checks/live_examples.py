"""Run the two documented workflows against Jev through an installed package."""

import argparse
import asyncio
import json
from pathlib import Path

import typesafe_sdk
from dotenv import dotenv_values
from pydantic import JsonValue

import jevantic
from examples.assessments import CommandContext, Draft, assess_command, assess_draft
from jevantic import Jevaluator


async def main(env_file: Path, output: Path) -> None:
    key = dotenv_values(env_file, interpolate=False).get('TYPESAFE_API_KEY')
    if not key:
        raise SystemExit('The selected environment file must define TYPESAFE_API_KEY')
    async with typesafe_sdk.AsyncTypeSafeClient(api_key=key, retry=typesafe_sdk.RetryPolicy(max_retries=0)) as client:
        async with Jevaluator(client=client) as evaluator:
            command = await assess_command(
                evaluator,
                CommandContext(command='pwd', working_directory='/workspace', user_intent='Find the current directory'),
            )
            draft = await assess_draft(
                evaluator,
                Draft(
                    brief='Explain that Jev returns structured decisions with probabilities.',
                    text=(
                        'Jev evaluates named questions against supplied state. '
                        'It returns typed decisions and probabilities.'
                    ),
                ),
            )
    report: dict[str, JsonValue] = {
        'installed_module': jevantic.__file__,
        'command': {
            'probability': command.value.probability,
            'model': command.info.model,
            'request_id': command.info.request_id,
        },
        'draft': {
            'relevance': draft.relevance.score,
            'clarity': draft.clarity.score,
            'model': draft.info.model,
            'request_id': draft.info.request_id,
        },
    }
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.env_file, args.output))
