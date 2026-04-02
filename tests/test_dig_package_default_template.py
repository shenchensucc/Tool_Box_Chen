"""Default bundled dig package template path (file may be absent in CI)."""

from pathlib import Path

from backend.pipeline.dig_package import (
    DEFAULT_DIG_PACKAGE_TEMPLATE_FILENAME,
    default_dig_package_template_path,
    read_default_dig_package_template_bytes,
)


def test_default_template_path_is_under_backend_static():
    p = default_dig_package_template_path()
    assert p.name == DEFAULT_DIG_PACKAGE_TEMPLATE_FILENAME
    assert "static" in p.parts and "templates" in p.parts and "dig_package" in p.parts


def test_read_default_template_bytes_when_present():
    p = default_dig_package_template_path()
    if not p.is_file():
        import pytest

        pytest.skip(f"Bundled template not present: {p}")
    data = read_default_dig_package_template_bytes()
    assert len(data) > 100
    assert data[:2] == b"PK"  # ZIP / xlsx signature
