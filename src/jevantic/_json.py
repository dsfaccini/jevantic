"""Validation and snapshots of caller-supplied JSON content."""

from collections.abc import Mapping, Sequence
from dataclasses import Field, is_dataclass
from functools import lru_cache
from typing import ClassVar, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

type JsonContent = str | Mapping[str, JsonValue] | Sequence[JsonValue]
"""Text, a JSON object, or a JSON array, including structured instructions."""


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[object]]]


type Content = JsonContent | BaseModel | DataclassInstance
"""JSON content, a Pydantic model, or a dataclass instance serialized through its fields."""

content_adapter: TypeAdapter[JsonContent] = TypeAdapter(
    JsonContent, config=ConfigDict(strict=True, allow_inf_nan=False)
)


@lru_cache
def dataclass_adapter(cls: type[object]) -> TypeAdapter[object]:
    return TypeAdapter(cls)


def content_snapshot(value: object) -> JsonContent:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode='json', warnings='error')
    elif is_dataclass(value) and not isinstance(value, type):
        value = dataclass_adapter(type(value)).dump_python(value, mode='json', warnings='error')
    validated = content_adapter.validate_python(value)
    # The SDK sends every Python sequence as a JSON array, including tuples.
    return content_adapter.validate_json(content_adapter.dump_json(validated))
