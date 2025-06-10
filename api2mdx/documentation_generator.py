"""Documentation generation tools for API reference documentation.

This module provides a DocumentationGenerator class that handles generating API
documentation from source repositories by extracting docstrings and processing
API directives using Griffe.
"""

import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from api2mdx.admonition_converter import convert_admonitions
from api2mdx.api_discovery import DirectivesPage, discover_api_directives
from api2mdx.griffe_integration import (
    get_loader,
    process_directive,
)
from api2mdx.meta import (
    generate_meta_file_content,
    generate_meta_from_directives,
)


class DocumentationGenerator:
    """Handles the generation of API documentation from source repositories.

    This class encapsulates the entire documentation generation process, including:
    - Loading the module with Griffe
    - Processing API documentation files
    - Generating formatted MDX output

    Attributes:
        project_root: Root directory of the project
        repo_path: Path to the cloned repository
        module: Loaded Griffe module
        organized_files: Dictionary of files organized by directory

    """

    def __init__(
        self, source_path: Path, package: str, docs_path: str, output_path: Path
    ) -> None:
        """Initialize the DocumentationGenerator.

        Args:
            source_path: Path to the source code directory
            package: Python package name to document
            docs_path: Path within the package where docs are located
            output_path: Path where generated documentation should be written

        """
        self.source_path = source_path
        self.package = package
        self.docs_path = docs_path
        self.output_path = output_path
        self.module: Any | None = None
        self.api_directives: list[DirectivesPage] | None = None

    def setup(self) -> "DocumentationGenerator":
        """Set up the generator by loading module and discovering API structure.

        Returns:
            Self for method chaining

        """
        # Load the module
        self.module = self._load_module()

        # Discover API directives from module structure
        if self.module is None:
            raise RuntimeError("Module must be loaded before discovering directives")
        self.api_directives = discover_api_directives(self.module)
        print(f"Discovered {len(self.api_directives)} API directives")

        return self

    def generate_all(self, directive_output_path: Path | None = None) -> None:
        """Generate all documentation files.

        Args:
            directive_output_path: Optional path to output intermediate directive files
        """
        if not self.api_directives:
            raise RuntimeError("Setup must be called before generating documentation")

        # Output directive snapshots if requested
        if directive_output_path:
            self.output_directive_snapshots(directive_output_path)

        # Clear target directory if it exists
        if self.output_path.exists():
            shutil.rmtree(self.output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)

        # Generate files from discovered directives
        for api_directive in self.api_directives:
            self.generate_directive(api_directive)

        # Generate metadata
        self._generate_meta_file()

    def generate_directive(self, api_directive: DirectivesPage) -> None:
        """Generate documentation for a specific directive.

        Args:
            api_directive: The ApiDirective object containing directive string and output path

        """
        if not self.module:
            raise RuntimeError("Setup must be called before generating documentation")

        try:
            target_path = self.output_path / api_directive.slug

            # Ensure target directory exists
            target_path.parent.mkdir(exist_ok=True, parents=True)

            # Process directive
            self._process_directive(api_directive)
        except Exception as e:
            print(f"ERROR: Failed to process directive {api_directive.directives}: {e}")
            # Re-raise the exception to maintain the original behavior
            raise

    def generate_selected(self, pattern: str, skip_meta: bool = True) -> None:
        """Generate documentation only for directives matching the pattern.

        Args:
            pattern: Pattern to match against directive or output paths
            skip_meta: Whether to skip metadata generation (default: True)

        """
        if not self.api_directives:
            raise RuntimeError("Setup must be called before generating documentation")

        found = False
        self.output_path.mkdir(parents=True, exist_ok=True)

        for api_directive in self.api_directives:
            # Check if any directive or output path matches pattern
            directive_matches = any(
                fnmatch.fnmatch(directive.object_path, pattern)
                for directive in api_directive.directives
            )
            if (
                directive_matches
                or fnmatch.fnmatch(api_directive.slug, pattern)
                or fnmatch.fnmatch(api_directive.slug.replace(".mdx", ""), pattern)
            ):
                print(f"Generating: {api_directive.directives} -> {api_directive.slug}")
                self.generate_directive(api_directive)
                found = True

        if not found:
            print(f"No directives matched pattern: {pattern}")
        elif not skip_meta:
            # Regenerate metadata only if skip_meta is False
            print("Regenerating metadata file...")
            self._generate_meta_file()

    def output_directive_snapshots(self, directive_output_path: Path) -> None:
        """Output directives as intermediate .md files for debugging/inspection.

        Args:
            directive_output_path: Path where directive files should be written
        """
        if not self.api_directives:
            raise RuntimeError("API directives must be discovered before output")

        # Clear and create directive output directory
        if directive_output_path.exists():
            shutil.rmtree(directive_output_path)
        directive_output_path.mkdir(parents=True, exist_ok=True)

        for api_directive in self.api_directives:
            directive_content = f"# {api_directive.name}\n\n" + "\n\n".join(
                str(directive) for directive in api_directive.directives
            )

            # Write to .md file in directive output directory
            directive_file_path = directive_output_path / api_directive.slug.replace(
                ".mdx", ".md"
            )
            directive_file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(directive_file_path, "w") as f:
                f.write(directive_content)

        print(
            f"Generated {len(self.api_directives)} directive files in {directive_output_path}"
        )

    def _load_module(self) -> Any:
        """Load the module using Griffe.

        Returns:
            Loaded Griffe module

        """
        try:
            # Add source path to sys.path temporarily
            sys.path.insert(0, str(self.source_path))

            # Load the module with basic loader
            loader = get_loader(self.source_path)

            # Try to preload common external dependencies to improve alias resolution
            common_dependencies = [
                "collections.abc",
                "typing",
                "openai",
                "mistralai",
                "functools",
                "base64",
                "typing_extensions",
                "__future__",
            ]
            for dep in common_dependencies:
                try:
                    loader.load(dep)
                    print(f"Preloaded {dep} for alias resolution")
                except Exception as e:
                    print(f"Info: {dep} preload skipped: {e}")

            # Load the main module
            module = loader.load(self.package)

            # Handle alias resolution errors gracefully
            try:
                loader.resolve_aliases(external=True)
            except Exception as e:
                print(f"Warning: Some aliases could not be resolved: {e}")
                print("Documentation generation will continue despite this warning.")

            print(f"Loaded module {self.package}")
            return module
        finally:
            # Clean up sys.path
            if str(self.source_path) in sys.path:
                sys.path.remove(str(self.source_path))

    def _process_directive(self, api_directive: DirectivesPage) -> None:
        """Process directives and generate the corresponding MDX file.

        Args:
            api_directive: The ApiDirective object containing directives and output info

        """
        if not self.module:
            raise RuntimeError("Module must be loaded before processing directives")

        # Get target path from the directive's slug
        target_path = self.output_path / api_directive.slug

        # Extract title from directive name
        title = api_directive.name

        # Get the relative file path for the API component
        relative_path = target_path.relative_to(self.output_path)
        doc_path = str(relative_path.with_suffix(""))  # Remove .mdx extension

        # Write the target file with frontmatter and processed content
        with open(target_path, "w") as f:
            f.write("---\n")
            # Add auto-generation notice as a comment in the frontmatter
            f.write("# AUTO-GENERATED API DOCUMENTATION - DO NOT EDIT\n")
            f.write(f"title: {title}\n")
            f.write(f"description: API documentation for {title}\n")
            f.write("---\n\n")
            f.write(f"# {title}\n\n")

            # Process each directive
            for directive in api_directive.directives:
                doc_content = process_directive(directive, self.module, doc_path)
                f.write(doc_content)
                f.write("\n\n")

    def _create_index_file(self) -> None:
        """Create the index.mdx file in the target directory."""
        index_path = self.output_path / "index.mdx"
        product_name = self.package.title()

        with open(index_path, "w") as f:
            f.write("---\n")
            # Add auto-generation notice as a comment in the frontmatter
            f.write("# AUTO-GENERATED API DOCUMENTATION - DO NOT EDIT\n")
            f.write(f"title: {product_name} API Reference\n")
            f.write(f"description: API documentation for {product_name}\n")
            f.write("---\n\n")
            f.write(f"# {product_name} API Reference\n\n")

            # Break long lines for the welcome text
            welcome_text = (
                f"Welcome to the {product_name} API reference documentation. "
                "This section provides detailed information about the classes, "
                f"methods, and interfaces that make up the {product_name} library."
            )
            f.write(f"{welcome_text}\n\n")
            f.write(
                "Use the sidebar to navigate through the different API components.\n"
            )

    def _generate_meta_file(self) -> None:
        """Generate metadata file and format it with prettier."""
        if not self.api_directives:
            raise RuntimeError(
                "API directives must be discovered before generating metadata"
            )

        api_section = generate_meta_from_directives(self.api_directives, weight=None)
        content = generate_meta_file_content(api_section)

        # Write to file
        meta_path = self.output_path / "_meta.json"
        with open(meta_path, "w") as f:
            f.write(content)
        print(f"Generated API meta file at {meta_path}")

        # Run prettier to format the file
        try:
            subprocess.run(
                ["bun", "prettier", "--write", str(meta_path)],
                check=True,
                capture_output=True,
            )
            print(f"Generated and formatted API meta file at {meta_path}")
        except subprocess.CalledProcessError as e:
            print(f"Warning: Prettier formatting failed: {e}")
            print(f"Generated unformatted API meta file at {meta_path}")
