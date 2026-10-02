"""Concise tool results keep the failure reason (instrMCP issue #48 A2).

`notebook_add_cell` on a notebook that changed on disk fails closed, but the
concise result used to drop the reason and report only ``{"success": false}``,
so the caller could not tell why. A frontend-handled failure carries its reason
in ``message`` (and sometimes ``status``); those must survive the concise
conversion, exactly like ``error`` already does.
"""

from instrmcp.servers.jupyter_qcodes.core.notebook_unsafe_tools import (
    UnsafeToolRegistrar,
)

convert = UnsafeToolRegistrar._to_concise_success_only
dummy_self = object()

CHANGED_ON_DISK = (
    "Notebook source or metadata changed on disk; refusing to overwrite it "
    "with the active frontend"
)


def test_failed_result_keeps_frontend_message_as_error():
    result = {
        "success": False,
        "message": CHANGED_ON_DISK,
        "request_id": "abc",
    }
    assert convert(dummy_self, result) == {"success": False, "error": CHANGED_ON_DISK}


def test_failed_result_keeps_status_when_present():
    result = {
        "success": False,
        "message": CHANGED_ON_DISK,
        "status": "persistence_error",
    }
    assert convert(dummy_self, result) == {
        "success": False,
        "error": CHANGED_ON_DISK,
        "status": "persistence_error",
    }


def test_explicit_error_wins_over_message():
    result = {"success": False, "error": "boom", "message": "less specific"}
    assert convert(dummy_self, result) == {"success": False, "error": "boom"}


def test_successful_results_stay_success_only():
    assert convert(dummy_self, {"success": True, "message": "Cell added"}) == {
        "success": True
    }
    assert convert(dummy_self, {"success": True}) == {"success": True}


def test_failure_without_reason_would_be_only_success_false():
    # Nothing to surface: keep the historical shape rather than inventing a reason.
    assert convert(dummy_self, {"success": False}) == {"success": False}
