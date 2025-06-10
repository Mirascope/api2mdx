"""Auto-discovery of API structure from Griffe modules.

This module provides functions to automatically discover documentable API objects
from a loaded Griffe module, generating directive strings that can be processed
by the existing documentation pipeline.
"""

from dataclasses import dataclass
from enum import Enum
from griffe import Alias, Class, Function, Module, Object


class DirectiveType(Enum):
    CLASS = "Class"
    FUNCTION = "Function"
    MODULE = "Module"
    ALIAS = "Alias"


@dataclass
class Directive:
    object_path: str
    object_type: DirectiveType

    def __str__(self) -> str:
        return f"::: {self.object_path}  # {self.object_type.value}"


@dataclass
class DirectivesPage:
    """Represents an API directive with its output path and original name.

    Attributes:
        directives: List of Directive objects for this documentation file
        slug: The lowercase output path/slug (e.g., "agent.mdx" or "agent-fn.mdx")
        name: The original name with proper casing (e.g., "Agent" or "agent")
    """

    directives: list[Directive]
    slug: str
    name: str


class ApiDocumentation:
    """Container for all API documentation with global symbol resolution.
    
    This class wraps a list of DirectivesPage objects and provides:
    - Global symbol registry for conflict resolution
    - Canonical vs alias assignment
    - Symbol-level slug resolution
    """
    
    def __init__(self, pages: list[DirectivesPage]):
        self.pages = pages
        self._symbol_registry = self._build_symbol_registry()
    
    def _build_symbol_registry(self) -> dict[str, str]:
        """Build a registry mapping canonical paths to canonical slugs.
        
        Returns:
            Dictionary mapping canonical_path -> canonical_slug
        """
        # TODO: Implement symbol registry logic
        registry = {}
        for page in self.pages:
            for directive in page.directives:
                # For now, use simple mapping - will enhance with conflict resolution
                registry[directive.object_path] = directive.object_path
        return registry
    
    def get_canonical_slug(self, canonical_path: str) -> str:
        """Get the canonical slug for a given object path.
        
        Args:
            canonical_path: The canonical object path (e.g., "mirascope_v2_llm.calls.decorator.call")
        
        Returns:
            The canonical slug to use for this symbol
        """
        return self._symbol_registry.get(canonical_path, canonical_path)
    
    def __iter__(self):
        """Allow iteration over pages."""
        return iter(self.pages)
    
    def __len__(self):
        """Return number of pages."""
        return len(self.pages)


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


def _create_directive_from_member(member: Object | Alias) -> Directive:
    """Create a Directive from a Griffe member object.

    Args:
        member: The Griffe object to create a directive for

    Returns:
        Directive object with appropriate type and path
    """
    if isinstance(member, Class):
        return Directive(member.canonical_path, DirectiveType.CLASS)
    elif isinstance(member, Function):
        return Directive(member.canonical_path, DirectiveType.FUNCTION)
    elif isinstance(member, Module):
        return Directive(member.canonical_path, DirectiveType.MODULE)
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
        return Directive(target.canonical_path, directive_type)
    else:
        raise ValueError(f"Unknown directive type: {member.canonical_path}")


def discover_module_pages(module: Module, base_path: str = "") -> list[DirectivesPage]:
    """Recursively discover pages for a module and its submodules.

    Args:
        module: The Module object to process
        base_path: The path prefix for nested modules (e.g., "calls" for submodules)

    Returns:
        List of DirectivesPage objects for this module and all submodules
    """

    output_path = f"{base_path or 'index'}.mdx"
    module_page = DirectivesPage([], output_path, module.name)
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


def discover_api_directives(module: Module) -> ApiDocumentation:
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

    # Resolve case-insensitive filename conflicts
    resolved_pages = _resolve_case_conflicts(pages)

    return ApiDocumentation(resolved_pages)


def _resolve_case_conflicts(directives: list[DirectivesPage]) -> list[DirectivesPage]:
    """Resolve case-insensitive filename conflicts by adding -fn suffix.

    When there are conflicts (e.g., "agent.mdx" from both "Agent" and "agent"), we:
    1. Keep the one that starts with a capital letter as-is
    2. Add "-fn" suffix to the one that starts with lowercase
    3. If neither starts with capital, throw exception for fast fail

    Args:
        directives: List of ApiDirective objects

    Returns:
        List of ApiDirective objects with conflicts resolved
    """
    # Group by lowercase slug to find conflicts
    path_groups: dict[str, list[DirectivesPage]] = {}
    for directive_obj in directives:
        lower_slug = directive_obj.slug.lower()
        if lower_slug not in path_groups:
            path_groups[lower_slug] = []
        path_groups[lower_slug].append(directive_obj)

    resolved: list[DirectivesPage] = []
    for lower_slug, group in path_groups.items():
        if len(group) == 1:
            # No conflict
            resolved.extend(group)
        else:
            # We have a conflict - resolve it
            capitalized_items: list[DirectivesPage] = []
            lowercase_items: list[DirectivesPage] = []

            for directive_obj in group:
                # Check the original name, not the lowercase slug
                if directive_obj.name[0].isupper():
                    capitalized_items.append(directive_obj)
                else:
                    lowercase_items.append(directive_obj)

            # Check that we have exactly one capitalized and one+ lowercase
            if len(capitalized_items) == 0:
                raise ValueError(
                    f"Case conflict with no capitalized names: {[item.name for item in group]}"
                )

            # Add capitalized items as-is
            resolved.extend(capitalized_items)

            # Add -fn suffix to lowercase items
            for directive_obj in lowercase_items:
                base_slug = directive_obj.slug.replace(".mdx", "")
                new_slug = f"{base_slug}-fn.mdx"
                resolved.append(
                    DirectivesPage(
                        directive_obj.directives, new_slug, directive_obj.name
                    )
                )

    return resolved
