"""Tests for API discovery functionality."""

import sys
from pathlib import Path

from api2mdx.api_discovery import discover_api_directives
from api2mdx.griffe_integration import get_loader


def test_discover_minimal_example():
    """Test API discovery on our minimal example."""
    # Add the example to Python path
    example_path = Path(__file__).parent.parent / "example-py-minimal"
    sys.path.insert(0, str(example_path))
    
    try:
        # Load the module
        loader = get_loader(example_path)
        module = loader.load("example-py-minimal")
        
        # Discover directives - cast to Module since we know it's loaded correctly
        from griffe import Module
        if isinstance(module, Module):
            directives = discover_api_directives(module)
        else:
            raise RuntimeError("Failed to load module as Module type")
        
        # Print results for manual verification
        print("Discovered directives:")
        for directive, output_path in directives:
            print(f"  {directive} -> {output_path}")
        
        # Debug: Print module structure
        print("\nModule structure:")
        print(f"Module path: {module.canonical_path}")
        exports = [name for name in module.members.keys() if not name.startswith('_')]
        print(f"Module exports: {exports}")
        
        for export_name in exports:
            if export_name in module.members:
                member = module.members[export_name]
                print(f"  {export_name}: {type(member).__name__}")
                if hasattr(member, 'canonical_path'):
                    print(f"    canonical_path: {member.canonical_path}")
        
        # Basic assertions
        assert len(directives) > 0, "Should discover at least one directive"
        
        # Check that we have the main module
        module_directives = [d for d, _ in directives if d == ":::example-py-minimal"]
        assert len(module_directives) == 1, "Should have main module directive"
        
        # Check that we have the exports from __all__
        expected_exports = ["Call", "BaseCall", "call_decorator"]
        found_exports = []
        
        for directive, output_path in directives:
            for export in expected_exports:
                if directive.endswith(f".{export}"):
                    found_exports.append(export)
        
        print(f"Expected exports: {expected_exports}")
        print(f"Found exports: {found_exports}")
        
        # Should find all the exports
        for export in expected_exports:
            assert export in found_exports, f"Should find export {export}"
        
        print("✅ Test passed!")
        return directives
        
    finally:
        # Clean up sys.path
        if str(example_path) in sys.path:
            sys.path.remove(str(example_path))


if __name__ == "__main__":
    test_discover_minimal_example()