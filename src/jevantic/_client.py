"""Async evaluation, explicit batches, and SDK client ownership."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType, TracebackType
from typing import Generic, Self, TypeVar

import anyio
import httpx2
import typesafe_sdk
from pydantic import BaseModel

from ._errors import QuestionError, ResponseValidationError
from ._json import JsonContent, content_snapshot
from ._questions import Question

AnswerT = TypeVar('AnswerT')
AnswerT_co = TypeVar('AnswerT_co', covariant=True)


@dataclass(frozen=True)
class Usage:
    """Provider-reported token counts; absent counts remain unknown."""

    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True)
class ResponseInfo:
    """The returned model, accounting, and raw HTTP evidence for one SDK call."""

    model: str
    requested_model: str
    usage: Usage
    request_id: str | None
    raw_http_response: httpx2.Response


@dataclass(frozen=True)
class Evaluation[AnswerT_co]:
    """A typed answer and the metadata of its evaluation."""

    value: AnswerT_co
    info: ResponseInfo


@dataclass(frozen=True)
class Handle(Generic[AnswerT_co]):  # noqa: UP046
    """A typed reference returned by ``Batch.add`` and used with its results."""

    name: str
    question: Question[AnswerT_co]


@dataclass(frozen=True)
class BatchResult:
    """Validated answers from one evaluation of a batch."""

    info: ResponseInfo
    _handles: Mapping[str, Handle[object]]
    _answers: Mapping[str, typesafe_sdk.Answer]

    def answer(self, handle: Handle[AnswerT]) -> AnswerT:
        """Retrieve the precise answer type associated with a handle from this batch."""
        if self._handles.get(handle.name) is not handle:
            raise ValueError('The handle does not belong to this batch')
        return handle.question.decode(self._answers[handle.name])


class ResponseAnswerNames(BaseModel):
    """Read raw answer names, including kinds the SDK may have skipped."""

    answers: dict[str, object]


class RequestModel(BaseModel):
    """Read the model actually sent after SDK configuration is applied."""

    model: str


class Evaluator:
    """Evaluate questions through TypeSafe's asynchronous SDK.

    Without ``client``, a client is created from ``api_key`` or the SDK's
    environment configuration. Close the evaluator or use ``async with`` to
    release it. A supplied SDK client belongs to the caller and is not closed.
    """

    def __init__(
        self,
        *,
        client: typesafe_sdk.AsyncTypeSafeClient | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        if client is not None and api_key is not None:
            raise ValueError('Configure credentials on the supplied SDK client')
        self._owns_client = client is None
        self._client = typesafe_sdk.AsyncTypeSafeClient(api_key=api_key) if client is None else client
        self._model = model
        self._closed = False
        self._entered = False

    def batch(self, state: JsonContent | BaseModel) -> 'Batch':
        """Prepare a shared-state batch without making a provider request."""
        return Batch(content_snapshot(state), self._request)

    async def evaluate(self, state: JsonContent | BaseModel, question: Question[AnswerT]) -> Evaluation[AnswerT]:
        """Evaluate one question, preserving its exact answer type and request metadata."""
        batch = self.batch(state)
        handle = batch.add('answer', question)
        result = await batch.run()
        return Evaluation(result.answer(handle), result.info)

    async def _request(
        self,
        state: JsonContent,
        handles: Mapping[str, Handle[object]],
    ) -> BatchResult:
        if self._closed:
            raise RuntimeError('The evaluator is closed')
        questions: dict[str, typesafe_sdk.Question] = {
            name: handle.question.to_request() for name, handle in handles.items()
        }
        response = await self._client.system_one(state, questions, model=self._model)
        raw_names = ResponseAnswerNames.model_validate_json(response.raw_http_response.content).answers.keys()
        if raw_names != handles.keys() or response.answers.keys() != handles.keys():
            raise ResponseValidationError(
                'Returned answer names do not match the requested questions',
                question=None,
                request_id=response.request_id,
            )
        for name, handle in handles.items():
            try:
                handle.question.decode(response.answers[name])
            except ValueError as error:
                raise ResponseValidationError(str(error), question=name, request_id=response.request_id) from error
        usage = Usage(response.usage.input_tokens, response.usage.output_tokens)
        requested_model = RequestModel.model_validate_json(response.raw_http_response.request.content).model
        info = ResponseInfo(response.model, requested_model, usage, response.request_id, response.raw_http_response)
        return BatchResult(info, MappingProxyType(dict(handles)), MappingProxyType(dict(response.answers)))

    async def aclose(self) -> None:
        """Close this evaluator and its owned SDK client; leave a borrowed client open."""
        if not self._closed:
            self._closed = True
            if self._owns_client:
                close_error: Exception | None = None

                async def close_client() -> None:
                    nonlocal close_error
                    # A child shields cleanup from both cancel scopes and direct Task.cancel().
                    with anyio.CancelScope(shield=True):
                        try:
                            await self._client.aclose()
                        except Exception as error:
                            close_error = error

                async with anyio.create_task_group() as group:
                    group.start_soon(close_client)
                if close_error is not None:
                    raise close_error

    async def __aenter__(self) -> Self:
        if self._closed:
            raise RuntimeError('The evaluator is closed')
        if self._entered:
            raise RuntimeError('An evaluator context cannot be nested')
        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()


class Batch:
    """A set of questions evaluated together against one snapshot of state.

    The first ``run`` freezes registration. Further runs explicitly repeat the
    same batch; concurrent results do not share answer storage. SDK retries can
    make additional HTTP attempts within each run.
    """

    def __init__(
        self,
        state: JsonContent,
        request: Callable[[JsonContent, Mapping[str, Handle[object]]], Awaitable[BatchResult]],
    ) -> None:
        self._request = request
        self._state = state
        self._handles: dict[str, Handle[object]] = {}
        self._frozen = False

    def add(self, name: str, question: Question[AnswerT]) -> Handle[AnswerT]:
        """Register a question and return its typed reference; names must be unique."""
        if self._frozen:
            raise QuestionError('A batch cannot be changed after evaluation starts')
        if name in self._handles:
            raise QuestionError('Question names must be unique within a batch')
        handle = Handle(name, question)
        self._handles[name] = handle
        return handle

    async def run(self) -> BatchResult:
        """Evaluate every registered question together and validate every answer."""
        if not self._handles:
            raise QuestionError('A batch needs at least one question')
        self._frozen = True
        return await self._request(self._state, self._handles)
