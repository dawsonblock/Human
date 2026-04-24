import pytest
import importlib

def test_package_layout():
    """
    Test that the subjective_runtime_v2_1 package is a real directory
    and that modules can be successfully imported.
    """
    # Check that main and api can be imported
    try:
        import subjective_runtime_v2_1.main
        import subjective_runtime_v2_1.api.app
        import subjective_runtime_v2_1.runtime.core
    except ImportError as e:
        pytest.fail(f"Package structure is incorrect, failed to import: {e}")
    
    # Check that the module has a __file__ path and it contains src/subjective_runtime_v2_1
    module = importlib.import_module("subjective_runtime_v2_1")
    assert "src/subjective_runtime_v2_1" in module.__file__
    
    # We should also ensure it's not a symlink.
    import os
    assert not os.path.islink(os.path.dirname(module.__file__))
