"""Smoke tests for tools/dig_package_kpi (registry flatten + progress math)."""

import importlib.util
import sys
from pathlib import Path

import pytest

_PKG = Path(__file__).resolve().parents[1] / "tools" / "dig_package_kpi"


def _load_check_kpi():
    spec = importlib.util.spec_from_file_location("check_kpi", _PKG / "check_kpi.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    # Register before exec_module so @dataclass can resolve cls.__module__
    # (Python 3.13 looks the module up in sys.modules during class processing).
    sys.modules["check_kpi"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not (_PKG / "kpi_registry.yaml").is_file(), reason="KPI registry missing")
def test_flatten_registry_has_86_kpis():
    yaml_mod = pytest.importorskip("yaml")
    ck = _load_check_kpi()
    with open(_PKG / "kpi_registry.yaml", encoding="utf-8") as f:
        raw = yaml_mod.safe_load(f)
    rows = ck.flatten_registry(raw)
    assert len(rows) == 86


@pytest.mark.skipif(not (_PKG / "kpi_registry.yaml").is_file(), reason="KPI registry missing")
def test_build_report_smoke():
    pytest.importorskip("yaml")
    ck = _load_check_kpi()
    rows, summary = ck.build_report(with_tests=False)
    assert len(rows) == 86
    assert summary["total"] == 86
    assert 0 <= summary["percent"] <= 100
