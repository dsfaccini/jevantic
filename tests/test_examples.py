from conftest import Backend

from examples.assessments import CommandContext, Draft, assess_command, assess_draft
from examples.ranking import Document, rank_documents
from jevantic import Evaluator


async def test_command_assessment(backend: Backend) -> None:
    context = CommandContext(command='pwd', working_directory='/workspace', user_intent='Find the current directory')
    backend.respond({'answer': {'type': 'noul', 'noul': 0.01}})
    async with Evaluator(client=backend.client) as evaluator:
        result = await assess_command(evaluator, context)
    assert result.value.probability == 0.01
    assert backend.transport.requests[0]['state'] == context.model_dump()


async def test_two_rubrics_share_one_request(backend: Backend) -> None:
    backend.respond(
        {
            'relevance': {
                'type': 'score',
                'score': 1.5,
                'probabilities': {'0': 0.1, '1': 0.3, '2': 0.6},
                'legend': {
                    '0': 'Does not address the brief',
                    '1': 'Addresses part of the brief',
                    '2': 'Directly addresses the brief',
                },
                'confidence': 0.5,
            },
            'clarity': {
                'type': 'score',
                'score': 1.9,
                'probabilities': {'0': 0.0, '1': 0.1, '2': 0.9},
                'legend': {
                    '0': 'Difficult to understand',
                    '1': 'Understandable with effort',
                    '2': 'Clear and easy to follow',
                },
                'confidence': 0.7,
            },
        }
    )
    async with Evaluator(client=backend.client) as evaluator:
        result = await assess_draft(evaluator, Draft(brief='Explain Jev', text='Jev estimates structured decisions.'))
    assert (result.relevance.score, result.clarity.score) == (1.5, 1.9)
    assert len(backend.transport.requests) == 1


async def test_rank_documents_preserves_identity_and_stable_ties(backend: Backend) -> None:
    documents: list[Document] = [
        Document(identifier='first', text='Unrelated text'),
        Document(identifier='second', text='First relevant text'),
        Document(identifier='third', text='Second relevant text'),
    ]
    for probability in (0.1, 0.9, 0.9):
        backend.respond({'answer': {'type': 'noul', 'noul': probability}})
    result = await rank_documents(Evaluator(client=backend.client), 'query', documents, concurrency=2)
    assert [item.document.identifier for item in result] == ['second', 'third', 'first']
    assert [item.relevance.value.probability for item in result] == [0.9, 0.9, 0.1]
    assert result[0].document is documents[1]
    assert result[1].document is documents[2]
    assert [request['state'] for request in backend.transport.requests] == [
        {'query': 'query', 'document': item.text} for item in documents
    ]
