#!/usr/bin/env python3
"""Generate MDX API documentation from Python source code.

This tool extracts API documentation from Python source code and generates
MDX files for use with React-based documentation sites.

Usage:
  api2mdx --source-path ./src --package mypackage --output ./docs/api
"""

import argparse
import sys
from pathlib import Path

from api2mdx.doclinks_postprocessor import process_doc_links
from api2mdx.documentation_generator import DocumentationGenerator


def generate_documentation(
    source_path: Path,
    package: str,
    docs_path: str,
    output_path: Path,
    pattern: str | None = None,
    directive_output_path: Path | None = None,
) -> bool:
    """Generate API documentation from source code.

    Args:
        source_path: Path to the source code directory
        package: Python package name to document
        docs_path: Path within the package where docs are located
        output_path: Path where generated documentation should be written
        pattern: Optional file pattern to regenerate only specific files
        directive_output_path: Optional path to output intermediate directive files

    Returns:
        True if successful, False otherwise

    """
    try:
        # Initialize the documentation generator
        generator = DocumentationGenerator(source_path, package, docs_path, output_path)
        generator.setup()

        # Generate documentation
        if pattern:
            # Always regenerate metadata for consistency
            generator.generate_selected(pattern, skip_meta=False)
        else:
            generator.generate_all(directive_output_path=directive_output_path)

        # Process documentation links
        modified_count = process_doc_links(str(output_path))
        print(f"Processed documentation links, modified {modified_count} files")

        print(f"Successfully generated documentation for {package}")
        return True
    except Exception as e:
        print(f"Error generating documentation: {e}", file=sys.stderr)
        return False


def main(cmd_args: list[str] | None = None) -> int:
    """Execute the API documentation generation process.

    Args:
        cmd_args: Command line arguments

    Returns:
        Exit code

    """
    parser = argparse.ArgumentParser(
        description="Generate MDX API documentation from Python source code."
    )
    parser.add_argument(
        "--source-path",
        type=Path,
        required=True,
        help="Path to the source code directory",
    )
    parser.add_argument(
        "--package",
        required=True,
        help="Python package name to document",
    )
    parser.add_argument(
        "--docs-path",
        default="docs/api",
        help="Path within the package where docs are located (default: docs/api)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path where generated documentation should be written",
    )
    parser.add_argument(
        "--pattern",
        help="Optional pattern to regenerate only matching files",
    )
    parser.add_argument(
        "--output-directives",
        type=Path,
        help="Optional path to output intermediate directive files (e.g., snapshots/directives/)",
    )

    parsed_args = parser.parse_args(cmd_args)

    print(f"Generating documentation for {parsed_args.package}...")
    print(f"Source path: {parsed_args.source_path}")
    print(f"Output path: {parsed_args.output}")

    # Generate documentation
    success = generate_documentation(
        source_path=parsed_args.source_path,
        package=parsed_args.package,
        docs_path=parsed_args.docs_path,
        output_path=parsed_args.output,
        pattern=parsed_args.pattern,
        directive_output_path=parsed_args.output_directives,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
