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


def test_package_file_not_absolute_path():
    """The installed package must not resolve via an absolute-path symlink
    that points to a machine-specific directory (the historical breakage)."""
    import subjective_runtime_v2_1
    import os

    pkg_file = os.path.abspath(subjective_runtime_v2_1.__file__)
    # The imported module file must exist — catches broken symlinks/imports.
    assert os.path.exists(pkg_file), f"package __file__ does not exist: {pkg_file}"

    current = pkg_file
    while True:
        if os.path.islink(current):
            link_target = os.readlink(current)
            assert not os.path.isabs(link_target), (
                "package import path must not use an absolute-path symlink: "
                f"{current} -> {link_target}"
            )

        if os.path.basename(current) == "subjective_runtime_v2_1":
            break

        parent = os.path.dirname(current)
        assert parent != current, (
            "could not locate package directory while validating import path: "
            f"{pkg_file}"
        )
        current = parent
