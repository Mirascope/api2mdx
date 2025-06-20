"""The `BaseResponse` class for LLM responses."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Generic

from typing_extensions import TypeVar

from ..content import Audio, Image, Text, Video
from ..messages import Message
from ..prompt_templates import DynamicConfig
from ..types import Dataclass
from .content import ContextResponseContent, ResponseContent
from .finish_reason import FinishReason
from .usage import Usage

ResponseContentT = TypeVar(
    "ResponseContentT", bound=ResponseContent | ContextResponseContent
)
T = TypeVar("T", bound=Dataclass | None, default=None)


@dataclass
class BaseResponse(Generic[ResponseContentT, T]):
    """The response generated by an LLM."""

    raw: Any
    """The raw response from the LLM."""

    provider: str
    """The provider of the LLM (e.g. "openai", "anthropic")."""

    model: str
    """The model used to generate the response (e.g. "gpt-4", "claude-3-5-sonnet-latet")."""

    args: dict[str, Any]
    """The arguments used to generate the response."""

    dynamic_config: DynamicConfig
    """The dynamic configuration used to generate the response."""

    template: str | None
    """The string template used to define the messages array, if any."""

    messages: list[Message]
    """The messages used to generate the response. This will not include the system message."""

    content: ResponseContentT | Sequence[ResponseContentT]
    """The content generated by the LLM."""

    texts: Sequence[Text]
    """The text content in the generated response, if any."""

    images: Sequence[Image]
    """The image content in the generated response, if any."""

    audios: Sequence[Audio]
    """The audio content in the generated response, if any."""

    videos: Sequence[Video]
    """The video content in the generated response, if any."""

    finish_reason: FinishReason
    """The reason why the LLM finished generating a response."""

    usage: Usage | None
    """The usage statistics for the request to the LLM."""

    cost: float | None
    """The cost of the request to the LLM, if available."""

    @property
    def text(self) -> str | None:
        """Returns the first text in the response content, if any."""
        raise NotImplementedError()

    @property
    def image(self) -> Image | None:
        """Returns the first image in the response content, if any."""
        raise NotImplementedError()

    @property
    def audio(self) -> Audio | None:
        """Returns the first audio in the response content, if any."""
        raise NotImplementedError()

    @property
    def video(self) -> Video | None:
        """Returns the first video in the response content, if any."""
        raise NotImplementedError()

    def __iter__(self) -> Iterator[ResponseContentT]:
        """Iterate over the transformed response content.

        This method allows iteration over the response content, returning
        each item in the order they were generated. Each item will be transformed for
        convenience. For example, `Text` content will be extracted into simple `str`s,
        and `ToolCall` response content will be automatically converted into `Tool`
        instances for easy calling.

        Yields:
            The next item in the response content (text, image, audio, video, or tool).
        """
        raise NotImplementedError()

    def format(self) -> T:
        """Format the response according to the response format parser.

        This method is only available if the call was created with a T.
        It will parse the response content according to the specified format and return
        a structured object.

        Returns:
            The formatted response object of type T.

        Raises:
            ValueError: If the response cannot be formatted according to the
                specified format.
        """
        raise NotImplementedError()
