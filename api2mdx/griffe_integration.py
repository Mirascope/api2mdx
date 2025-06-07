"""Integration with Griffe for API documentation generation.

This module provides functionality to process API directives and generate
documentation using Griffe. The implementation follows a clear model-view
pattern where:
1. Data is extracted and processed into structured models (via process_* functions)
2. Models are rendered into MDX format (via render_* functions)
3. Error handling ensures graceful fallbacks for missing dependencies

The code is organized in the following sections:
- Configuration: Loader setup for parsing docstrings
- Documentation Generation: Core object processing and rendering
- Directive Processing: Handling API directives and error cases
"""

import re
from pathlib import Path

from griffe import (
    Alias,
    Class,
    Extensions,
    Function,
    GriffeLoader,
    Module,
    Object,
    Parser,
)

from api2mdx.doclinks import UpdateDocstringsExtension
from api2mdx.mdx_renderer import (
    render_object,
)
from api2mdx.api_discovery import _get_module_exports
from api2mdx.models import (
    process_object,
)

# Default content subpath for documentation
MODULE_CONTENT_SUBPATH = "docs/mirascope"


def get_loader(
    source_path: Path,
    content_dir: Path | None = None,
    content_subpath: str | None = None,
) -> GriffeLoader:
    """Create a configured Griffe loader.

    Args:
        source_path: Path to the source code directory
        content_dir: Path to the content directory for the doclinks extension
        content_subpath: Subpath (eg /docs/mirascope) for local link evaluation

    Returns:
        A configured GriffeLoader instance

    """
    # Set up the parser for Google-style docstrings
    parser = Parser("google")

    # Create loader with specified docstring parser
    loader = GriffeLoader(docstring_parser=parser)

    # Add the doclinks extension if content_dir is provided
    if content_dir and content_subpath:
        extensions = Extensions(UpdateDocstringsExtension(content_dir, content_subpath))
        loader.extensions = extensions

    return loader


def generate_error_placeholder(object_path: str, error: Exception) -> str:
    """Generate placeholder documentation for errors.

    Args:
        object_path: The path of the object that failed to process
        error: The exception that was raised

    Returns:
        Placeholder documentation with error details

    """
    if isinstance(error, KeyError):
        # Handle missing dependency issues (like opentelemetry not being available)
        missing_dep = str(error).strip("'")
        print(
            f"WARNING: Could not resolve dependency when processing {object_path}: {error}"
        )

        return f"""
## Missing Dependency Warning

Documentation for `{object_path}` could not be fully generated because of a missing dependency: `{missing_dep}`.

This is expected and safe to ignore for documentation generation purposes.
"""
    else:
        # Add general error handling to make API docs generation more robust
        print(f"WARNING: Error processing directive {object_path}: {error}")

        return f"""
## Error Processing Documentation

An error occurred while generating documentation for `{object_path}`: {error!s}

Please check that all required dependencies are installed.
"""


def process_directive_with_error_handling(
    directive: str, module: Module, doc_path: str
) -> str:
    """Process an API directive with error handling for missing dependencies.

    This wrapper catches errors during documentation generation, reports them,
    and provides placeholder documentation, allowing the process to continue
    even when dependencies are missing or other issues are encountered.

    Args:
        directive: The directive string (e.g., "::: mirascope.core.anthropic.call")
        module: The pre-loaded Griffe module
        doc_path: Optional path to the document, used for API component links

    Returns:
        The generated documentation content or error placeholder

    """
    try:
        return process_directive(directive, module, doc_path)
    except Exception as e:
        object_path = directive.replace("::: ", "")
        return generate_error_placeholder(object_path, e)


def document_object(obj: Object | Alias, doc_path: str) -> str:
    """Generate documentation for any supported Griffe object type.

    Args:
        obj: The Griffe object to document
        doc_path: Optional path to the document, used for API component links

    Returns:
        MDX documentation with enhanced component usage

    """
    # Check if this is a module - if so, render as overview only
    if isinstance(obj, Module):
        return render_module_overview(obj, doc_path)
    
    # For classes, functions, etc., render full documentation
    processed_obj = process_object(obj)
    if processed_obj is None:
        raise ValueError(f"Failed to process object: {obj}")

    return render_object(processed_obj, doc_path)


def process_directive(directive: str, module: Module, doc_path: str) -> str:
    """Process an API directive and generate documentation.

    Args:
        directive: The directive string (e.g., "::: mirascope.core.anthropic.call")
        module: The pre-loaded Griffe module
        doc_path: Optional path to the document, used for API component links

    Returns:
        The generated documentation content

    """
    # Extract the module/class/function name from the directive
    match = re.search(r"::: ([a-zA-Z0-9_.]+)(?:\s+(.+))?", directive)
    if not match:
        raise ValueError("Invalid directive format. Expected '::: module_name'.")

    object_path = match.group(1)

    # Split the path to navigate to the object
    path_parts = object_path.split(".")

    # Start with the loaded module
    current_obj: Object | Alias = module
    
    # If the directive path exactly matches the loaded module path, return the module itself
    if object_path == module.canonical_path:
        pass  # current_obj is already the target module
    else:
        # Navigate through the object path, skipping parts that match the module path
        module_parts = module.canonical_path.split(".")
        
        # Find the starting index - skip parts that match the loaded module path
        start_index = 0
        if len(path_parts) >= len(module_parts):
            if path_parts[:len(module_parts)] == module_parts:
                start_index = len(module_parts)
        
        # Navigate from the starting index
        for i, part in enumerate(path_parts[start_index:], start_index):
            if hasattr(current_obj, "members") and part in current_obj.members:
                current_obj = current_obj.members[part]
            else:
                raise ValueError(
                    f"Could not find {'.'.join(path_parts[: i + 1])} in the module."
                )

    # Use the document_object dispatcher function
    return document_object(current_obj, doc_path)


def render_module_overview(module: Module, doc_path: str) -> str:
    """Render a module as an overview with export links, not full documentation.
    
    Args:
        module: The Griffe module to render as overview
        doc_path: Path to the document, used for API component links
        
    Returns:
        MDX content showing module docstring and export links
    """
    content: list[str] = []
    
    # Module docstring
    if module.docstring:
        # Griffe docstring objects have .value, not .description
        docstring_text = str(module.docstring.value) if hasattr(module.docstring, 'value') else str(module.docstring)
        content.append(docstring_text)
        content.append("")
    
    # Get meaningful exports (using our filtering logic)
    exports = _get_module_exports(module)
    
    if not exports:
        return "\n".join(content)
    
    # Show brief info about each export
    for export_name in exports:
        if export_name in module.members:
            member = module.members[export_name]
            
            # Get brief description from docstring
            brief_desc = ""
            if hasattr(member, 'docstring') and member.docstring:
                # Use first line of docstring as brief description
                docstring_text = str(member.docstring.value) if hasattr(member.docstring, 'value') else str(member.docstring)
                brief_desc = docstring_text.split('\n')[0] if docstring_text else ""
            
            # Determine member type for ApiType component
            if isinstance(member, Module):
                member_type = "Module"
            elif isinstance(member, Class):
                member_type = "Class"
            elif isinstance(member, Function):
                member_type = "Function"
            elif isinstance(member, Alias):
                member_type = "Alias"
            else:
                member_type = "Object"
            
            # Add ApiType component with brief description
            content.append(f'## <ApiType type="{member_type}" path="{doc_path}" symbolName="{export_name}" /> {export_name}')
            content.append("")
            if brief_desc:
                content.append(brief_desc)
                content.append("")
    
    return "\n".join(content)
