"""Rank retrieved documents using a caller-configured number of concurrent requests."""

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel

from jevantic import Evaluation, Evaluator, NoulAnswer, Question


class Document(BaseModel):
    identifier: str
    text: str


@dataclass(frozen=True)
class RankedDocument:
    document: Document
    relevance: Evaluation[NoulAnswer]


async def rank_documents(
    evaluator: Evaluator, query: str, documents: Sequence[Document], *, concurrency: int
) -> list[RankedDocument]:
    """Return original documents ordered by estimated relevance; preserve order in ties."""
    candidates = tuple(documents)
    evaluations = await evaluator.evaluate_many(
        ({'query': query, 'document': item.text} for item in candidates),
        Question.noul('Does the document provide information relevant to answering the query?'),
        concurrency=concurrency,
    )
    ranked = [
        RankedDocument(document, evaluation) for document, evaluation in zip(candidates, evaluations, strict=True)
    ]
    return sorted(ranked, key=lambda item: item.relevance.value.probability, reverse=True)
