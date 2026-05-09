"""
Regression tests for qcodes >=0.55 compatibility.

The ``qcodes.instrument.base`` module was a deprecated re-export in
qcodes 0.45-0.54 and was removed in qcodes 0.55+. instrMCP previously
imported ``InstrumentBase`` from that module path inside
``try/except ImportError`` blocks, which silently swallowed the
``ModuleNotFoundError`` on newer qcodes versions and made the
``isinstance(obj, InstrumentBase)`` check skip every instrument.

These tests guard against re-introduction of the deprecated path
and verify that real qcodes instruments are detected by the backend.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from instrmcp.servers.jupyter_qcodes.backend.base import SharedState
from instrmcp.servers.jupyter_qcodes.backend.qcodes import QCodesBackend
from instrmcp.servers.jupyter_qcodes.backend.notebook import NotebookBackend


def _make_state(namespace):
    return SharedState(
        ipython=MagicMock(),
        namespace=namespace,
        cache=MagicMock(),
        rate_limiter=MagicMock(),
        poller=MagicMock(),
    )


@pytest.fixture
def real_qcodes_instrument():
    """Tiny real qcodes Instrument so the InstrumentBase isinstance check is exercised."""
    from qcodes.instrument import Instrument

    Instrument.close_all()
    inst = Instrument("dummy_for_compat_test")
    yield inst
    inst.close()


class TestInstrumentBaseDetection:
    @pytest.mark.asyncio
    async def test_list_instruments_detects_real_qcodes_instrument(
        self, real_qcodes_instrument
    ):
        namespace = {
            "dummy_for_compat_test": real_qcodes_instrument,
            "not_an_instrument": 42,
        }
        backend = QCodesBackend(_make_state(namespace))

        result = await backend.list_instruments()
        names = [i["name"] for i in result]

        assert "dummy_for_compat_test" in names, (
            "Real qcodes Instrument not detected — InstrumentBase isinstance "
            f"check is broken. Got: {names}"
        )
        assert "not_an_instrument" not in names

    def test_get_instrument_rejects_non_instrument(self, real_qcodes_instrument):
        namespace = {
            "dummy_for_compat_test": real_qcodes_instrument,
            "not_an_instrument": 42,
        }
        backend = QCodesBackend(_make_state(namespace))

        assert (
            backend._get_instrument("dummy_for_compat_test") is real_qcodes_instrument
        )
        with pytest.raises(ValueError, match="not a QCoDeS instrument"):
            backend._get_instrument("not_an_instrument")

    @pytest.mark.asyncio
    async def test_get_variable_info_marks_qcodes_instrument(
        self, real_qcodes_instrument
    ):
        namespace = {"dummy_for_compat_test": real_qcodes_instrument}
        backend = NotebookBackend(_make_state(namespace))

        info = await backend.get_variable_info("dummy_for_compat_test")

        assert info.get("qcodes_instrument") is True, (
            "qcodes_instrument flag should be True for a real Instrument. "
            f"Got: {info}"
        )


class TestStaticImportGuard:
    def test_no_deprecated_qcodes_instrument_base_import(self):
        repo_root = Path(__file__).resolve().parents[2]
        instrmcp_dir = repo_root / "instrmcp"
        offenders = []
        for path in instrmcp_dir.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "qcodes.instrument.base" in text:
                offenders.append(str(path.relative_to(repo_root)))
        assert offenders == [], (
            "qcodes.instrument.base was removed in qcodes 0.55+. Use "
            "`from qcodes.instrument import InstrumentBase` instead. "
            f"Offending files: {offenders}"
        )
