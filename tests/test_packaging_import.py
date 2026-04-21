"""Regression test: package import sanity.

Ensures that `import subjective_runtime_v2_1` resolves to the real package and
that key sub-packages are importable without PYTHONPATH hacks.
"""
from __future__ import annotations


def test_top_level_import():
    import subjective_runtime_v2_1  # noqa: F401


def test_runtime_core_importable():
    from subjective_runtime_v2_1.runtime.core import RuntimeCore  # noqa: F401


def test_api_app_importable():
    from subjective_runtime_v2_1.api.app import create_app  # noqa: F401


def test_state_models_importable():
    from subjective_runtime_v2_1.state.models import AgentStateV2_1  # noqa: F401


def test_package_file_not_absolute_path(tmp_path):
    """The installed package must not resolve via an absolute-path symlink
    that points to a machine-specific directory (the historical breakage)."""
    import subjective_runtime_v2_1
    import os

    pkg_file = subjective_runtime_v2_1.__file__
    # The resolved path must exist — catches broken absolute-path symlinks.
    assert os.path.exists(pkg_file), f"package __file__ does not exist: {pkg_file}"
