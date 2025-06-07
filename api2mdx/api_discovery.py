"""Auto-discovery of API structure from Griffe modules.

This module provides functions to automatically discover documentable API objects
from a loaded Griffe module, generating directive strings that can be processed
by the existing documentation pipeline.
"""

from griffe import Alias, Class, Function, Module, Object


def discover_api_directives(module: Module) -> list[tuple[str, str]]:
    """Discover API directives from a module's __all__ exports.
    
    This function walks through a module's public API (as defined by __all__)
    and generates directive strings and output paths for documentation.
    
    Args:
        module: The loaded Griffe module to analyze
        
    Returns:
        List of (directive, output_path) tuples where:
        - directive: String like ":::package.module.Class" 
        - output_path: Relative path like "module/Class.mdx"
        
    Examples:
        For a module with __all__ = ["Call", "BaseCall"]:
        
        ```python
        directives = discover_api_directives(module)
        # Returns:
        # [
        #     (":::example-py-minimal", "index.mdx"),
        #     (":::example-py-minimal.calls", "calls/index.mdx"),
        #     (":::example-py-minimal.calls.Call", "calls/Call.mdx"),
        #     (":::example-py-minimal.calls.BaseCall", "calls/BaseCall.mdx"),
        # ]
        ```
    """
    directives = []
    submodules_seen = set()
    
    # Start with the main module
    module_directive = f"::: {module.canonical_path}"
    directives.append((module_directive, "index.mdx"))
    
    # Discover exports from __all__ or all public members
    exports = _get_module_exports(module)
    
    for export_name in exports:
        if export_name in module.members:
            member = module.members[export_name]
            member_directives = _discover_member_directives(member, module.canonical_path)
            
            # Check if we need to add submodule index files
            for directive, output_path in member_directives:
                if '/' in output_path:  # This is in a submodule
                    submodule_path = output_path.split('/')[0]
                    if submodule_path not in submodules_seen:
                        # Add submodule index
                        submodule_directive = f"::: {module.canonical_path}.{submodule_path}"
                        submodule_index_path = f"{submodule_path}/index.mdx"
                        directives.append((submodule_directive, submodule_index_path))
                        submodules_seen.add(submodule_path)
            
            directives.extend(member_directives)
    
    return directives


def _extract_all_exports(module: Module) -> list[str] | None:
    """Extract __all__ exports from a Griffe module.
    
    Args:
        module: The module to analyze
        
    Returns:
        List of export names if __all__ is defined, None otherwise
    """
    if '__all__' not in module.members:
        return None
    
    all_member = module.members['__all__']
    if not hasattr(all_member, 'value'):
        return None
    
    value = all_member.value
    
    # If it's a Griffe ExprList, extract the elements
    if hasattr(value, 'elements'):
        exports = []
        for elem in value.elements:
            if hasattr(elem, 'value'):
                clean_name = elem.value.strip("'\"")
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
        return ast.literal_eval(value)

    
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
        if name.startswith('_'):
            continue
            
        # Include classes, functions, and modules
        if isinstance(member, (Class, Function, Module)):
            fallback_exports.append(name)
    
    return fallback_exports


def _discover_member_directives(
    member: Object | Alias, 
    exporting_module_path: str
) -> list[tuple[str, str]]:
    """Discover directives for a specific module member.
    
    Args:
        member: The Griffe object to document
        exporting_module_path: The path of the module that exports this member
        
    Returns:
        List of (directive, output_path) tuples
    """
    directives = []
    member_name = member.name
    
    # Use canonical path for directive (what to document)
    if hasattr(member, 'canonical_path'):
        canonical_path = member.canonical_path
    else:
        canonical_path = f"{exporting_module_path}.{member_name}"
    
    # Use exporting module path for output structure (where to put it)
    path_parts = exporting_module_path.split('.')
    if len(path_parts) > 1:  # package.submodule
        submodule_parts = path_parts[1:]  # Skip package name
        submodule_path = '/'.join(submodule_parts)
        output_path = f"{submodule_path}/{member_name}.mdx"
    else:
        # Top-level member
        output_path = f"{member_name}.mdx"
    
    if isinstance(member, (Class, Function)):
        directive = f"::: {canonical_path}"
        directives.append((directive, output_path))
        
    elif hasattr(member, 'target') and getattr(member, 'target'):
        # Handle aliases by documenting the target
        target = getattr(member, 'target')
        target_path = target.canonical_path if hasattr(target, 'canonical_path') else str(target)
        directive = f"::: {target_path}"
        directives.append((directive, output_path))
    
    return directives


def discover_hierarchical_directives(module: Module) -> list[tuple[str, str]]:
    """Discover API directives with hierarchical organization.
    
    This creates a structure like:
    - index.mdx (main module)
    - submodule/index.mdx (submodule overview)  
    - submodule/Class.mdx (individual classes)
    
    Args:
        module: The loaded Griffe module to analyze
        
    Returns:
        List of (directive, output_path) tuples with hierarchical paths
    """
    directives = []
    submodules_seen = set()
    
    # Main module index
    module_directive = f"::: {module.canonical_path}"
    directives.append((module_directive, "index.mdx"))
    
    # Process the main module's exports (respecting its __all__)
    member_directives = _discover_main_module_directives(module)
    
    # Check if we need to add submodule index files
    for directive, output_path in member_directives:
        if '/' in output_path:  # This is in a submodule
            submodule_path = output_path.split('/')[0]
            if submodule_path not in submodules_seen:
                # Add submodule index
                submodule_directive = f"::: {module.canonical_path}.{submodule_path}"
                submodule_index_path = f"{submodule_path}/index.mdx"
                directives.append((submodule_directive, submodule_index_path))
                submodules_seen.add(submodule_path)
    
    directives.extend(member_directives)
    
    return directives


def _discover_main_module_directives(module: Module) -> list[tuple[str, str]]:
    """Discover directives for the main module's __all__ exports.
    
    This processes only what the main module explicitly exports,
    creating hierarchical paths based on where the exports come from.
    
    Args:
        module: The main module to process
        
    Returns:
        List of (directive, output_path) tuples
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
            member_directives = _discover_member_directives(member, module.canonical_path)
            directives.extend(member_directives)
    
    return directives


