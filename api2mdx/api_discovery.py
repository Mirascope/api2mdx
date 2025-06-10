"""Auto-discovery of API structure from Griffe modules.

This module provides functions to automatically discover documentable API objects
from a loaded Griffe module, generating directive strings that can be processed
by the existing documentation pipeline.
"""

from dataclasses import dataclass
from griffe import Alias, Class, Function, Module, Object


@dataclass
class ApiDirective:
    """Represents an API directive with its output path and original name.

    Attributes:
        directive: The API directive string (e.g., ":::package.module.Class")
        slug: The lowercase output path/slug (e.g., "agent.mdx" or "agent-fn.mdx")
        name: The original name with proper casing (e.g., "Agent" or "agent")
    """

    directive: str
    slug: str
    name: str


def _extract_all_exports(module: Module) -> list[str] | None:
    """Extract __all__ exports from a Griffe module.

    Args:
        module: The module to analyze

    Returns:
        List of export names if __all__ is defined, None otherwise
    """
    if "__all__" not in module.members:
        return None

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


def _get_module_exports(module: Module) -> list[str]:
    """Get the list of exports from a module.

    Checks for __all__ first, falls back to meaningful public members.

    Args:
        module: The module to analyze

    Returns:
        List of export names
    """
    # Try to get __all__ exports first
    exports = _extract_all_exports(module)
    if exports is not None:
        return exports

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


def _discover_member_directives(
    member: Object | Alias, exporting_module_path: str
) -> list[ApiDirective]:
    """Discover directives for a specific module member.

    Args:
        member: The Griffe object to document
        exporting_module_path: The path of the module that exports this member

    Returns:
        List of ApiDirective objects
    """
    directives = []
    member_name = member.name
    original_name = member_name  # Preserve original casing

    # Use canonical path for directive (what to document)
    if hasattr(member, "canonical_path"):
        canonical_path = member.canonical_path
    else:
        canonical_path = f"{exporting_module_path}.{member_name}"

    # Create lowercase filename (conflicts will be resolved later)
    filename = member_name.lower()

    # Use exporting module path for output structure (where to put it)
    path_parts = exporting_module_path.split(".")
    if len(path_parts) > 1:  # package.submodule
        submodule_parts = path_parts[1:]  # Skip package name
        submodule_path = "/".join(submodule_parts)
        output_path = f"{submodule_path}/{filename}.mdx"
    else:
        # Top-level member
        output_path = f"{filename}.mdx"

    if isinstance(member, (Class, Function)):
        directive = f"::: {canonical_path}"
        directives.append(ApiDirective(directive, output_path, original_name))

    elif hasattr(member, "target") and getattr(member, "target"):
        # Handle aliases by documenting the target
        target = getattr(member, "target")
        target_path = (
            target.canonical_path if hasattr(target, "canonical_path") else str(target)
        )
        directive = f"::: {target_path}"
        directives.append(ApiDirective(directive, output_path, original_name))

    return directives


def discover_api_directives(module: Module) -> list[ApiDirective]:
    """Discover API directives with hierarchical organization.

    This creates a structure like:
    - index.mdx (main module)
    - submodule/index.mdx (submodule overview)
    - submodule/Class.mdx (individual classes)

    Args:
        module: The loaded Griffe module to analyze

    Returns:
        List of ApiDirective objects with hierarchical paths
    """
    directives = []
    submodules_seen = set()

    # Main module index
    module_directive = f"::: {module.canonical_path}"
    directives.append(ApiDirective(module_directive, "index.mdx", "index"))

    # Process the main module's exports (respecting its __all__)
    member_directives = _discover_main_module_directives(module)

    # Check if we need to add submodule index files
    for directive_obj in member_directives:
        if "/" in directive_obj.slug:  # This is in a submodule
            submodule_path = directive_obj.slug.split("/")[0]
            if submodule_path not in submodules_seen:
                # Add submodule index
                submodule_directive = f"::: {module.canonical_path}.{submodule_path}"
                submodule_index_path = f"{submodule_path}/index.mdx"
                directives.append(
                    ApiDirective(
                        submodule_directive, submodule_index_path, submodule_path
                    )
                )
                submodules_seen.add(submodule_path)

    directives.extend(member_directives)

    # Resolve case-insensitive filename conflicts
    resolved_directives = _resolve_case_conflicts(directives)

    return resolved_directives


def _discover_main_module_directives(module: Module) -> list[ApiDirective]:
    """Discover directives for the main module's __all__ exports.

    This processes only what the main module explicitly exports,
    creating hierarchical paths based on where the exports come from.

    Args:
        module: The main module to process

    Returns:
        List of ApiDirective objects
    """
    directives = []

    # Get exports using the consolidated function
    exports = _extract_all_exports(module)
    if exports is None:
        return directives

    for export_name in exports:
        if export_name in module.members:
            member = module.members[export_name]

            # Use the existing member directive logic to get hierarchical paths
            member_directives = _discover_member_directives(
                member, module.canonical_path
            )
            directives.extend(member_directives)

    return directives


def _resolve_case_conflicts(directives: list[ApiDirective]) -> list[ApiDirective]:
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
    path_groups = {}
    for directive_obj in directives:
        lower_slug = directive_obj.slug.lower()
        if lower_slug not in path_groups:
            path_groups[lower_slug] = []
        path_groups[lower_slug].append(directive_obj)

    resolved = []
    for lower_slug, group in path_groups.items():
        if len(group) == 1:
            # No conflict
            resolved.extend(group)
        else:
            # We have a conflict - resolve it
            capitalized_items = []
            lowercase_items = []

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
                    ApiDirective(directive_obj.directive, new_slug, directive_obj.name)
                )

    return resolved
