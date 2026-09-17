"""Validation and snapshots of caller-supplied JSON content."""

from collections.abc import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

type JsonContent = str | Mapping[str, JsonValue] | Sequence[JsonValue]
"""Text, a JSON object, or a JSON array, including structured instructions."""

content_adapter: TypeAdapter[JsonContent] = TypeAdapter(
    JsonContent, config=ConfigDict(strict=True, allow_inf_nan=False)
)


def content_snapshot(value: object) -> JsonContent:
    if isinstance(value, BaseModel):
        return content_adapter.validate_json(value.model_dump_json())
    validated = content_adapter.validate_python(value)
    # The SDK sends every Python sequence as a JSON array, including tuples.
    return content_adapter.validate_json(content_adapter.dump_json(validated))
