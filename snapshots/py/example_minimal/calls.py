"""A minimal calls module for testing api2mdx documentation generation.

This module demonstrates various Python patterns that api2mdx should handle:
- Classes with inheritance
- Generic types
- Async methods
- Decorators
- Complex docstrings with parameters and returns
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, ParamSpec, TypeVar
from collections.abc import Callable

# Type variables for demonstration
P = ParamSpec("P")
T = TypeVar("T")
ResponseT = TypeVar("ResponseT")

__all__ = [
    "Response",
    "Stream", 
    "BaseCall",
    "Call",
    "call_decorator",
    "StructuredCall",
]


class Response:
    """A response from an LLM call.
    
    This class represents the response returned by an LLM after processing
    a prompt. It contains the generated text and metadata about the response.
    
    Attributes:
        content: The generated text content from the LLM
        model: The name of the model that generated the response
        usage: Token usage statistics for the call
    """
    
    def __init__(self, content: str, model: str = "test-model") -> None:
        """Initialize a new Response.
        
        Args:
            content: The generated text content
            model: The model name that generated this response
        """
        self.content = content
        self.model = model
        self.usage = {"prompt_tokens": 10, "completion_tokens": 20}
    
    def __str__(self) -> str:
        """Return the string representation of the response."""
        return self.content


class Stream(Generic[T]):
    """A streaming response from an LLM.
    
    This class provides an iterator interface for streaming responses,
    allowing you to process tokens as they are generated.
    
    Type Parameters:
        T: The type of items yielded by the stream
    """
    
    def __init__(self, items: list[T]) -> None:
        """Initialize a new Stream.
        
        Args:
            items: The items to yield from this stream
        """
        self.items = items
        self._index = 0
    
    def __iter__(self) -> "Stream[T]":
        """Return the iterator object."""
        return self
    
    def __next__(self) -> T:
        """Return the next item in the stream.
        
        Returns:
            The next item in the stream
            
        Raises:
            StopIteration: When there are no more items
        """
        if self._index >= len(self.items):
            raise StopIteration
        item = self.items[self._index]
        self._index += 1
        return item


@dataclass
class BaseCall(Generic[P, ResponseT], ABC):
    """Abstract base class for LLM calls.
    
    This class provides the foundation for all LLM call implementations.
    It defines the common interface and shared functionality.
    
    Type Parameters:
        P: Parameter specification for the call function signature
        ResponseT: The type of response returned by the call
        
    Attributes:
        model: The name of the LLM model to use
        temperature: Controls randomness in the response (0.0 to 1.0)
        max_tokens: Maximum number of tokens to generate
    """
    
    model: str = "default-model"
    temperature: float = 0.7
    max_tokens: int = 1000
    
    @abstractmethod
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> ResponseT:
        """Execute the call and return a response.
        
        Args:
            *args: Positional arguments for the call
            **kwargs: Keyword arguments for the call
            
        Returns:
            The response from the LLM
        """
        pass
    
    @abstractmethod
    async def call_async(self, *args: P.args, **kwargs: P.kwargs) -> ResponseT:
        """Execute the call asynchronously.
        
        Args:
            *args: Positional arguments for the call
            **kwargs: Keyword arguments for the call
            
        Returns:
            The response from the LLM
        """
        pass


@dataclass
class Call(BaseCall[P, Response]):
    """A standard LLM call implementation.
    
    This class implements the BaseCall interface for synchronous and
    asynchronous LLM interactions. It supports both regular responses
    and streaming responses.
    
    Examples:
        Basic usage:
        
        ```python
        call = Call(model="gpt-3.5-turbo")
        response = call("What is the capital of France?")
        print(response.content)  # "Paris"
        ```
        
        Streaming usage:
        
        ```python
        call = Call(model="gpt-3.5-turbo")
        for chunk in call.stream("Tell me a story"):
            print(chunk, end="")
        ```
    """
    
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Response:
        """Execute the call with arguments.
        
        Args:
            *args: Positional arguments for the call
            **kwargs: Keyword arguments for the call
            
        Returns:
            The response from the LLM
            
        Raises:
            ValueError: If no arguments provided
        """
        if not args:
            raise ValueError("At least one argument required")
        
        prompt = str(args[0])
        # Simulate LLM call
        return Response(f"Response to: {prompt}", self.model)
    
    async def call_async(self, *args: P.args, **kwargs: P.kwargs) -> Response:
        """Execute the call asynchronously.
        
        Args:
            *args: Positional arguments for the call
            **kwargs: Keyword arguments for the call
            
        Returns:
            The response from the LLM
        """
        if not args:
            raise ValueError("At least one argument required")
        
        prompt = str(args[0])
        # Simulate async LLM call
        return Response(f"Async response to: {prompt}", self.model)
    
    def stream(self, prompt: str) -> Stream[str]:
        """Stream the response from the LLM.
        
        Args:
            prompt: The input prompt for the LLM
            
        Returns:
            A stream of response chunks
        """
        # Simulate streaming response
        words = f"Streaming response to: {prompt}".split()
        return Stream(words)
    
    async def stream_async(self, prompt: str) -> Stream[str]:
        """Stream the response asynchronously.
        
        Args:
            prompt: The input prompt for the LLM
            
        Returns:
            A stream of response chunks
        """
        # Simulate async streaming response
        words = f"Async streaming response to: {prompt}".split()
        return Stream(words)


def call_decorator(
    model: str = "default-model",
    temperature: float = 0.7,
    max_tokens: int = 1000
) -> Callable[[Callable[P, str]], Call[P]]:
    """Decorator that converts a function into a Call instance.
    
    This decorator allows you to easily convert prompt template functions
    into LLM calls by adding the @call_decorator annotation.
    
    Args:
        model: The LLM model to use for the call
        temperature: Controls randomness in responses (0.0 to 1.0)
        max_tokens: Maximum number of tokens to generate
        
    Returns:
        A decorator function that creates Call instances
        
    Examples:
        ```python
        @call_decorator(model="gpt-4", temperature=0.5)
        def ask_question(question: str) -> str:
            return f"Please answer this question: {question}"
        
        # Now ask_question is a Call instance
        response = ask_question("What is AI?")
        print(response.content)
        ```
    """
    def decorator(func: Callable[P, str]) -> Call[P]:
        """The actual decorator function.
        
        Args:
            func: The function to convert into a Call
            
        Returns:
            A Call instance wrapping the function
        """
        call_instance = Call(model=model, temperature=temperature, max_tokens=max_tokens)
        
        # Store the original function for reference (would use setattr in real code)
        
        return call_instance
    
    return decorator


@dataclass
class StructuredCall(BaseCall[P, dict[str, Any]]):
    """A call that returns structured data instead of plain text.
    
    This class provides structured outputs like JSON, with automatic 
    parsing and validation of the response format.
    
    Attributes:
        output_format: The expected output format ("json", "yaml", etc.)
        schema: Optional schema for validating structured output
    """
    
    output_format: str = "json"
    schema: dict[str, Any] | None = None
    
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
        """Execute the call and return structured data.
        
        Args:
            *args: Positional arguments for the call
            **kwargs: Keyword arguments for the call
            
        Returns:
            Parsed structured data from the LLM response
            
        Raises:
            ValueError: If the response cannot be parsed as structured data
        """
        if not args:
            raise ValueError("At least one argument required")
        
        prompt = str(args[0])
        
        # Simulate structured response parsing
        return {"result": f"Structured response to: {prompt}", "format": self.output_format}
    
    async def call_async(self, *args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
        """Execute the call asynchronously and return structured data.
        
        Args:
            *args: Positional arguments for the call
            **kwargs: Keyword arguments for the call
            
        Returns:
            Parsed structured data from the LLM response
        """
        if not args:
            raise ValueError("At least one argument required")
        
        prompt = str(args[0])
        
        # Simulate async structured response
        return {"result": f"Async structured response to: {prompt}", "format": self.output_format}
    
    def validate_schema(self, data: dict[str, Any]) -> bool:
        """Validate structured data against the schema.
        
        Args:
            data: The structured data to validate
            
        Returns:
            True if data matches schema, False otherwise
        """
        if self.schema is None:
            return True
        
        # Simple schema validation (in real implementation, use jsonschema)
        required_keys = self.schema.get("required", [])
        return all(key in data for key in required_keys)