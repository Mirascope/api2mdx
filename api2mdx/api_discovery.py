"""Auto-discovery of API structure from Griffe modules.

This module provides functions to automatically discover documentable API objects
from a loaded Griffe module, generating directive strings that can be processed
by the existing documentation pipeline.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import NewType
from griffe import Alias, Class, Function, Module, Object


# Type aliases for better type safety
ObjectPath = NewType("ObjectPath", str)
"""Canonical path to a Python object (e.g., 'mirascope_v2_llm.calls.decorator.call')"""


class Slug(str):
    """A filesystem-safe slug matching [a-z0-9-_]* pattern."""

    _pattern = re.compile(r"^[a-z0-9-_]+$")

    def __new__(cls, value: str) -> "Slug":
        if not cls._pattern.match(value):
            raise ValueError(f"Invalid slug '{value}': must match [a-z0-9-_]*")
        return super().__new__(cls, value)

    @classmethod
    def from_name(cls, name: str) -> "Slug":
        """Create a slug from a name by converting to lowercase and replacing invalid chars."""
        slug = name.lower().replace(".", "-").replace("_", "-")
        # Remove any remaining invalid characters
        slug = re.sub(r"[^a-z0-9-_]", "", slug)
        return cls(slug)


class DirectiveType(Enum):
    CLASS = "Class"
    FUNCTION = "Function"
    MODULE = "Module"
    ALIAS = "Alias"


@dataclass
class RawDirective:
    object_path: ObjectPath
    object_type: DirectiveType

    def __str__(self) -> str:
        return f"::: {self.object_path}  # {self.object_type.value}"

    def symbol_name(self) -> str:
        """Extract the symbol name from the object path.
        
        Returns:
            The last component of the object path (e.g., "call" from "mirascope_v2_llm.calls.decorator.call")
        """
        return self.object_path.split(".")[-1]


@dataclass
class RawDirectivesPage:
    """Represents an API directive with its output path and original name.

    Attributes:
        directives: List of Directive objects for this documentation file
        directory: Directory path for nested structures (e.g., "calls" or "" for root)
        slug: The clean slug identifier (e.g., "agent" or "base-tool")
        name: The original name with proper casing (e.g., "Agent" or "agent")
    """

    directives: list[RawDirective]
    directory: str
    slug: Slug
    name: str

    @property
    def file_path(self) -> str:
        """Get the full file path with .mdx extension."""
        if self.directory:
            return f"{self.directory}/{self.slug}.mdx"
        return f"{self.slug}.mdx"


@dataclass
class Directive:
    """Enriched directive with computed slug and canonical docs path."""
    
    raw_directive: RawDirective
    slug: Slug
    canonical_docs_path: str
    
    @property
    def object_path(self) -> ObjectPath:
        """Get the object path from the underlying raw directive."""
        return self.raw_directive.object_path
    
    @property
    def object_type(self) -> DirectiveType:
        """Get the object type from the underlying raw directive."""
        return self.raw_directive.object_type
    
    def symbol_name(self) -> str:
        """Extract the symbol name from the object path."""
        return self.raw_directive.symbol_name()
    
    def __str__(self) -> str:
        return f"::: {self.object_path}  # {self.object_type.value}"
    
    def render(self) -> str:
        """Render directive as JSX-like component for debugging."""
        return f'<Directive\n  path="{self.object_path}"\n  slug="{self.slug}"\n  canonicalPath="{self.canonical_docs_path}"\n/>'


@dataclass
class DirectivesPage:
    """Enriched directives page with computed file path and enriched directives."""
    
    raw_page: RawDirectivesPage
    directives: list[Directive]
    
    @property
    def directory(self) -> str:
        """Get the directory from the underlying raw page."""
        return self.raw_page.directory
    
    @property
    def slug(self) -> Slug:
        """Get the slug from the underlying raw page."""
        return self.raw_page.slug
    
    @property
    def name(self) -> str:
        """Get the name from the underlying raw page."""
        return self.raw_page.name
    
    @property
    def file_path(self) -> str:
        """Get the full file path with .mdx extension."""
        return self.raw_page.file_path


class ApiDocumentation:
    """Container for all API documentation with global symbol resolution.

    This class wraps a list of DirectivesPage objects and provides:
    - Global symbol registry for conflict resolution
    - Canonical vs alias assignment
    - Symbol-level slug resolution
    - Canonical docs path mapping for cross-references
    """

    def __init__(self, raw_pages: list[RawDirectivesPage]):
        # Validate unique file paths
        file_paths = set()
        for page in raw_pages:
            if page.file_path in file_paths:
                raise ValueError(f"Duplicate file path: {page.file_path}")
            file_paths.add(page.file_path)

        self.raw_pages = raw_pages
        self._symbol_registry = self._build_symbol_registry()
        self._canonical_docs_registry = self._build_canonical_docs_registry()
        self.pages = self._build_enriched_pages()

    def _build_symbol_registry(self) -> dict[ObjectPath, str]:
        """Build a registry mapping canonical paths to canonical slugs.

        Uses conflict resolution to ensure unique slugs:
        1. Try the symbol name as slug
        2. If taken, try symbol_name + "_" + type_suffix
        3. If still taken, append _1, _2, etc.

        Returns:
            Dictionary mapping ObjectPath -> canonical_slug
        """
        registry: dict[ObjectPath, str] = {}
        used_slugs: dict[str, ObjectPath] = {}

        # Type suffix mappings for disambiguation
        type_suffixes = {
            DirectiveType.FUNCTION: "fn",
            DirectiveType.CLASS: "cls",
            DirectiveType.MODULE: "mod",
            DirectiveType.ALIAS: "alias",
        }

        for page in self.raw_pages:
            for directive in page.directives:
                # Get the symbol name
                symbol_name = directive.symbol_name()
                # Convert camelCase/PascalCase to kebab-case for readability
                base_slug = self._camel_to_kebab(symbol_name)

                # Try the base slug first
                if base_slug not in used_slugs:
                    registry[directive.object_path] = base_slug
                    used_slugs[base_slug] = directive.object_path
                    continue

                # Try with type suffix
                type_suffix = type_suffixes.get(directive.object_type, "unknown")
                typed_slug = f"{base_slug}_{type_suffix}"

                if typed_slug not in used_slugs:
                    registry[directive.object_path] = typed_slug
                    used_slugs[typed_slug] = directive.object_path
                    continue

                # Try with numbered suffix
                counter = 1
                while True:
                    numbered_slug = f"{typed_slug}_{counter}"
                    if numbered_slug not in used_slugs:
                        registry[directive.object_path] = numbered_slug
                        used_slugs[numbered_slug] = directive.object_path
                        break
                    counter += 1

        return registry

    def _build_canonical_docs_registry(self) -> dict[ObjectPath, str]:
        """Build a registry mapping object paths to their canonical docs locations.
        
        Uses first encounter as canonical location for cross-references.
        
        Returns:
            Dictionary mapping ObjectPath -> canonical_docs_path (e.g., "calls/decorator")
        """
        registry: dict[ObjectPath, str] = {}
        
        for page in self.raw_pages:
            # Get docs path without .mdx extension
            docs_path = page.file_path.replace(".mdx", "")
            
            for directive in page.directives:
                # Only record first encounter as canonical
                if directive.object_path not in registry:
                    registry[directive.object_path] = docs_path
        
        return registry

    def _camel_to_kebab(self, name: str) -> str:
        """Convert camelCase/PascalCase to kebab-case."""
        # Insert hyphens before uppercase letters (except at start)
        result = re.sub(r"(?<!^)(?=[A-Z])", "-", name)
        return result.lower()

    def get_canonical_slug(self, canonical_path: ObjectPath) -> Slug:
        """Get the canonical slug for a given object path.

        Args:
            canonical_path: The canonical object path (e.g., "mirascope_v2_llm.calls.decorator.call")

        Returns:
            The canonical slug to use for this symbol
        """
        slug_str = self._symbol_registry.get(canonical_path, str(canonical_path))
        return Slug(slug_str)

    def get_canonical_docs_path(self, canonical_path: ObjectPath) -> str:
        """Get the canonical docs path for a given object path.

        Args:
            canonical_path: The canonical object path (e.g., "mirascope_v2_llm.calls.decorator.call")

        Returns:
            The canonical docs path where this symbol should be linked (e.g., "calls/decorator" or "index")
        """
        return self._canonical_docs_registry.get(canonical_path, "index")

    def _build_enriched_pages(self) -> list[DirectivesPage]:
        """Build enriched pages with computed slugs.
        
        Returns:
            List of enriched DirectivesPage objects
        """
        enriched_pages = []
        
        for raw_page in self.raw_pages:
            enriched_directives = []
            
            for raw_directive in raw_page.directives:
                # Get the computed slug for this directive
                slug = self.get_canonical_slug(raw_directive.object_path)
                
                # Get the canonical docs path for this directive
                canonical_docs_path = self.get_canonical_docs_path(raw_directive.object_path)
                
                # Create enriched directive
                enriched_directive = Directive(
                    raw_directive=raw_directive,
                    slug=slug,
                    canonical_docs_path=canonical_docs_path
                )
                enriched_directives.append(enriched_directive)
            
            # Create enriched page
            enriched_page = DirectivesPage(
                raw_page=raw_page,
                directives=enriched_directives
            )
            enriched_pages.append(enriched_page)
        
        return enriched_pages

    def __iter__(self):
        """Allow iteration over pages."""
        return iter(self.pages)

    def __len__(self):
        """Return number of pages."""
        return len(self.pages)

    @classmethod
    def from_module(cls, module: Module) -> "ApiDocumentation":
        """Discover API directives with hierarchical organization.

        This creates a structure like:
        - index.mdx (main module with its exports)
        - submodule.mdx (submodule with its exports)
        - nested/submodule.mdx (nested submodules)

        Args:
            module: The loaded Griffe module to analyze

        Returns:
            ApiDocumentation object containing all pages with symbol registry
        """
        # Use the new recursive discovery function
        pages = discover_module_pages(module)

        return cls(pages)


def _resolve_member(module: Module, name: str) -> Object | Alias:
    """Resolve a member name, prioritizing imports over submodules for name conflicts."""
    # Try custom import resolution first
    if hasattr(module, "imports") and name in module.imports:
        import_path = module.imports[name]

        # Determine the base module for resolution
        if import_path.startswith("."):
            # Relative import - use current module as base
            base_module = module
        else:
            # Absolute import - use root module as base
            base_module = module
            while base_module.parent is not None:
                parent = base_module.parent
                if isinstance(parent, Module):
                    base_module = parent
                else:
                    break

        member = _resolve_import_path(import_path, base_module)
        if member is not None:
            return member

    # Fall back to normal resolution
    try:
        return module[name]
    except Exception:
        return module.members[name]


def _resolve_import_path(
    import_path: str, root_module: Module
) -> Object | Alias | None:
    """Recursive import resolution with final-step import prioritization.

    This allows us to correctly resolve "shadowed imports" despite an underlying bug in
    Griffe. Consider the case with imports like:
    from .call import Call
    from .decorator import call

    The call symbol resolves to a function from decorator.py, but Griffe will try to resolve
    it to the module corresponding to call.py.

    So instead we resolve it by checking the imports. However, we only do this on the last
    step. That way if we have the following situation:

    from .calls import call, Call

    When Call resolves to .calls.call.Call, we do not want the middle step in resolution
    to get the decorator - in that case we really do want to step into the call.py module
    and find Call
    """

    parts = import_path.split(".")
    current = root_module

    # Skip the root module name if it matches the first part
    start_index = 0
    if parts[0] == current.name:
        start_index = 1

    # Navigate down the path
    for i in range(start_index, len(parts)):
        part = parts[i]
        is_final_step = i == len(parts) - 1

        if is_final_step:
            # Final step: prioritize imports (the actual target we want)
            if hasattr(current, "imports") and part in current.imports:
                nested_import_path = current.imports[part]
                return _resolve_import_path(nested_import_path, root_module)

            # Fall back to members for final step
            if hasattr(current, "members") and part in current.members:
                current = current.members[part]
            else:
                return None
        else:
            # Intermediate step: prioritize members (navigation through module structure)
            if hasattr(current, "members") and part in current.members:
                current = current.members[part]
            else:
                return None

    return current


def _extract_all_exports(module: Module) -> list[str] | None:
    """Extract __all__ exports from a Griffe module.

    Args:
        module: The module to analyze

    Returns:
        List of export names if __all__ is defined, None otherwise
    """
    if "__all__" not in module.members:
        # Fallback to public members (no hacky filtering)
        fallback_exports = []
        for name, member in module.members.items():
            # Skip private members
            if name.startswith("_"):
                continue

            # Include classes, functions, and modules
            if isinstance(member, (Class, Function, Module)):
                fallback_exports.append(name)

        return fallback_exports

    all_member = module.members["__all__"]

    # Use getattr to safely access the value attribute
    value = getattr(all_member, "value", None)
    if value is None:
        return None

    # If it's a Griffe ExprList, extract the elements
    elements = getattr(value, "elements", None)
    if elements is not None:
        exports = []
        for elem in elements:
            elem_value = getattr(elem, "value", None)
            if elem_value is not None:
                clean_name = str(elem_value).strip("'\"")
                exports.append(clean_name)
            else:
                exports.append(str(elem).strip("'\""))
        return exports
    # If it's already a list, use it
    elif isinstance(value, list):
        return [str(item).strip("'\"") for item in value]
    # If it's a string representation, try to safely evaluate it
    elif isinstance(value, str):
        import ast

        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return None

    return None


def _create_directive_from_member(member: Object | Alias) -> RawDirective:
    """Create a Directive from a Griffe member object.

    Args:
        member: The Griffe object to create a directive for

    Returns:
        Directive object with appropriate type and path
    """
    if isinstance(member, Class):
        return RawDirective(ObjectPath(member.canonical_path), DirectiveType.CLASS)
    elif isinstance(member, Function):
        return RawDirective(ObjectPath(member.canonical_path), DirectiveType.FUNCTION)
    elif isinstance(member, Module):
        return RawDirective(ObjectPath(member.canonical_path), DirectiveType.MODULE)
    elif hasattr(member, "target") and getattr(member, "target"):
        # Handle aliases - use the target's type instead of ALIAS
        target = getattr(member, "target")
        if isinstance(target, Class):
            directive_type = DirectiveType.CLASS
        elif isinstance(target, Function):
            directive_type = DirectiveType.FUNCTION
        elif isinstance(target, Module):
            directive_type = DirectiveType.MODULE
        else:
            directive_type = DirectiveType.ALIAS
        return RawDirective(ObjectPath(target.canonical_path), directive_type)
    else:
        raise ValueError(f"Unknown directive type: {member.canonical_path}")


def discover_module_pages(
    module: Module, base_path: str = ""
) -> list[RawDirectivesPage]:
    """Recursively discover pages for a module and its submodules.

    Args:
        module: The Module object to process
        base_path: The path prefix for nested modules (e.g., "calls" for submodules)

    Returns:
        List of DirectivesPage objects for this module and all submodules
    """

    if base_path:
        parts = base_path.split("/")
        directory = "/".join(parts[:-1]) if len(parts) > 1 else ""
        slug_name = parts[-1]
    else:
        directory = ""
        slug_name = "index"

    module_page = RawDirectivesPage(
        [], directory, Slug.from_name(slug_name), module.name
    )
    pages = [module_page]

    # Get all exports from this module
    export_names = _extract_all_exports(module)

    if export_names is None:
        raise ValueError(f"Module {module.canonical_path} has no __all__")

    # Process each export
    for export_name in export_names:
        if export_name not in module.members:
            raise ValueError(
                f"Export '{export_name}' in __all__ not found in module {module.canonical_path}"
            )

        member = _resolve_member(module, export_name)

        if isinstance(member, Module):
            # This is a submodule - give it dedicated page(s) (recursive)
            submodule_base_path = (
                f"{base_path}/{export_name}" if base_path else export_name
            )
            submodule_pages = discover_module_pages(member, submodule_base_path)
            pages.extend(submodule_pages)

        # Add a directive to this module's page (including for submodules - will render a link)
        directive = _create_directive_from_member(member)
        module_page.directives.append(directive)

    return pages
