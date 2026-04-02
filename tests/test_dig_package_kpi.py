"""KPI registry stays aligned with layout-based dig package generation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_CHECK_KPI = _REPO / "tools" / "dig_package_kpi" / "check_kpi.py"


def _load_check_kpi():
    if "dig_package_check_kpi_mod" not in sys.modules:
        spec = importlib.util.spec_from_file_location("dig_package_check_kpi_mod", _CHECK_KPI)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.path.insert(0, str(_CHECK_KPI.parent))
        spec.loader.exec_module(mod)
        sys.modules["dig_package_check_kpi_mod"] = mod
    return sys.modules["dig_package_check_kpi_mod"]


def test_kpi_auto_only_joint_summary_section_fails():
    """All automated checks pass except C-* gates until Joint Summary is implemented."""
    ck = _load_check_kpi()
    rows, summary = ck.build_report(with_tests=False)
    failed = [r for r in rows if not r["counts_pass"]]
    assert failed, "expected C-* gates to fail until populate_joint_summary exists"
    for r in failed:
        assert str(r["id"]).startswith("C-"), (
            f"unexpected KPI failure {r['id']}: {r.get('detail')}"
        )
    assert summary["percent"] < 100.0
    assert summary["passed"] == len(rows) - len(failed)


def test_registry_flattens_all_sections():
    ck = _load_check_kpi()
    raw = ck._load_yaml()
    rows = ck.flatten_registry(raw)
    ids = {r.id for r in rows}
    assert "K-21" in ids
    assert "A-1" in ids
    assert len(rows) >= 83
