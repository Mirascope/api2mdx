"""MDX component classes for consistent rendering.

This module provides Python classes that represent MDX components,
ensuring consistent rendering and type safety for component props.
"""

from dataclasses import dataclass
from enum import Enum


class ApiTypeKind(Enum):
    """Types of API objects that can be documented."""
    MODULE = "Module"
    FUNCTION = "Function"
    CLASS = "Class"
    ATTRIBUTE = "Attribute"
    ALIAS = "Alias"


@dataclass
class ApiType:
    """Represents an <ApiType> MDX component."""
    
    type: ApiTypeKind
    path: str  # Document path
    symbol_name: str  # Name of the symbol
    
    def render(self) -> str:
        """Render the ApiType component as a string."""
        return f'<ApiType type="{self.type.value}" path="{self.path}" symbolName="{self.symbol_name}" />'