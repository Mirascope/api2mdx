"""The `llm` module for writing provider-agnostic LLM Generations.

This module provides a unified interface for interacting with different LLM providers,
including messages, tools, response formatting, and streaming. It allows you to write
code that works with multiple LLM providers without changing your application logic.
"""

from .agents import Agent, agent
from .calls import (
    call,
)


__all__ = ["call", "agent", "Agent"]
