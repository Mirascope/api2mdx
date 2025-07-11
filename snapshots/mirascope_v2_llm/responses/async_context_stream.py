"""Interface for streaming responses asynchronously with context from LLMs.

This module defines interfaces for streaming responses asynchronously from language models
that have contextual information or data, such as the history of messages and dependencies
used to generate the response.

TODO: this interface is missing stuff from v1 like usage etc. that we collect during
the stream for convenience (e.g. calling stream.cost after the stream is done).
"""

from collections.abc import AsyncIterator
from typing import Generic

from typing_extensions import TypeVar

from .context_stream_chunk import ContextStreamChunk

DepsT = TypeVar("DepsT", default=None)


class AsyncContextStream(Generic[DepsT]):
    """An asynchronous stream of response chunks from an LLM with context.

    This class supports async iteration to process chunks as they arrive from the model.
    Each chunk includes access to the context dependencies.

    Example:
        ```python
        from mirascope import llm

        class Book:
            title: str
            author: str

        @llm.call("openai:gpt-4o-mini", deps_type=Book)
        def answer_question(ctx: llm.Context[Book], question: str) -> str:
            return f"Answer this question: {question}"

        with llm.context(deps=Book(title="1984", author="George Orwell")) as ctx:
            stream = await answer_question.astream(ctx, "What is the book about?")
            async for chunk in stream:
                print(chunk.content, end="", flush=True)
                # Access the context with chunk.ctx
        ```
    """

    def __aiter__(self) -> AsyncIterator[ContextStreamChunk[DepsT, None]]:
        """Iterate through the chunks of the stream asynchronously.

        Returns:
            An async iterator yielding ContextStreamChunk objects.
        """
        raise NotImplementedError()
