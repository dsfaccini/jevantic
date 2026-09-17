"""Errors in question definitions and otherwise successful provider responses."""


class QuestionError(ValueError):
    """A question or batch is invalid before a provider request is made."""


class ResponseValidationError(ValueError):
    """A provider response does not satisfy the requested questions.

    Transport and HTTP failures retain the TypeSafe SDK's exception types.
    """

    def __init__(self, message: str, *, question: str | None, request_id: str | None) -> None:
        self.question = question
        self.request_id = request_id
        super().__init__(message)
