"""Interfaces for LLM responses.

This module defines interfaces for the responses returned by language models,
including methods for formatting the response according to a specified format.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from typing_extensions import TypeVar

from ..tools import Tool
from ..types import Dataclass, Jsonable
from .base_response import BaseResponse
from .content import ResponseContent

T = TypeVar("T", bound=Dataclass | None, default=None)


@dataclass
class Response(BaseResponse[ResponseContent, T]):
    """The response generated by an LLM."""

    tools: Sequence[Tool[..., Jsonable]]
    """The tools the LLM wants called on its behalf, if any."""

    @property
    def tool(self) -> Tool[..., Jsonable] | None:
        """Returns the first tool used in the response, if any."""
        raise NotImplementedError()
