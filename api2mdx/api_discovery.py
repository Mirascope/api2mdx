"""Auto-discovery of API structure from Griffe modules.

This module provides functions to automatically discover documentable API objects
from a loaded Griffe module, generating directive strings that can be processed
by the existing documentation pipeline.
"""

from pathlib import Path
from typing import Any

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
    module_directive = f":::{module.canonical_path}"
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
                        submodule_directive = f":::{module.canonical_path}.{submodule_path}"
                        submodule_index_path = f"{submodule_path}/index.mdx"
                        directives.append((submodule_directive, submodule_index_path))
                        submodules_seen.add(submodule_path)
            
            directives.extend(member_directives)
    
    return directives


def _get_module_exports(module: Module) -> list[str]:
    """Get the list of exports from a module.
    
    Checks for __all__ first, falls back to public members (no underscore prefix).
    
    Args:
        module: The module to analyze
        
    Returns:
        List of export names
    """
    # Check if module has __all__ defined
    if hasattr(module, 'all') and module.all:
        return list(module.all)
    
    # Fallback to public members (no underscore prefix)
    return [name for name in module.members.keys() if not name.startswith('_')]


def _discover_member_directives(
    member: Object | Alias, 
    module_path: str
) -> list[tuple[str, str]]:
    """Discover directives for a specific module member.
    
    Args:
        member: The Griffe object to document
        module_path: The canonical path of the containing module
        
    Returns:
        List of (directive, output_path) tuples
    """
    directives = []
    member_name = member.name
    
    # For aliases, use the canonical path of the target
    if hasattr(member, 'canonical_path'):
        canonical_path = member.canonical_path
    else:
        canonical_path = f"{module_path}.{member_name}"
    
    # Extract the submodule path for hierarchical structure
    # e.g., "example-py-minimal.calls.Call" -> "calls/Call.mdx"
    path_parts = canonical_path.split('.')
    if len(path_parts) > 2:  # package.module.member
        submodule_parts = path_parts[1:-1]  # Skip package and member name
        submodule_path = '/'.join(submodule_parts)
        output_path = f"{submodule_path}/{member_name}.mdx"
    else:
        # Top-level member
        output_path = f"{member_name}.mdx"
    
    if isinstance(member, (Class, Function)):
        directive = f":::{canonical_path}"
        directives.append((directive, output_path))
        
    elif hasattr(member, 'target') and member.target:
        # Handle aliases by documenting the target
        target_path = member.target.canonical_path if hasattr(member.target, 'canonical_path') else str(member.target)
        directive = f":::{target_path}"
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
    
    # Main module index
    module_directive = f":::{module.canonical_path}"
    directives.append((module_directive, "index.mdx"))
    
    # Process all submodules and their exports
    directives.extend(_discover_submodule_directives(module, ""))
    
    return directives


def _discover_submodule_directives(
    module: Module, 
    path_prefix: str
) -> list[tuple[str, str]]:
    """Recursively discover directives for submodules.
    
    Args:
        module: The module to process
        path_prefix: The current path prefix for output files
        
    Returns:
        List of (directive, output_path) tuples
    """
    directives = []
    
    # Get exports for this module
    exports = _get_module_exports(module)
    
    for export_name in exports:
        if export_name in module.members:
            member = module.members[export_name]
            
            if isinstance(member, Module):
                # Submodule - create hierarchical structure
                submodule_prefix = f"{path_prefix}{export_name}/" if path_prefix else f"{export_name}/"
                
                # Submodule index
                submodule_directive = f":::{member.canonical_path}"
                submodule_index_path = f"{submodule_prefix}index.mdx"
                directives.append((submodule_directive, submodule_index_path))
                
                # Recursively process submodule
                directives.extend(_discover_submodule_directives(member, submodule_prefix))
                
            else:
                # Regular member (class, function, etc.)
                canonical_path = f"{module.canonical_path}.{export_name}"
                output_path = f"{path_prefix}{export_name}.mdx"
                directive = f":::{canonical_path}"
                directives.append((directive, output_path))
    
    return directives