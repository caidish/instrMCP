"""
Consent Dialog Helpers

Utilities for automating consent dialog interactions in E2E tests.
"""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout


def wait_for_consent_dialog(page: Page, timeout: int = 5000):
    """Wait for consent dialog to appear.

    Args:
        page: Playwright page
        timeout: Timeout in milliseconds

    Returns:
        Dialog locator or None if not found
    """
    selectors = [
        ".mcp-consent-dialog",
        ".jp-Dialog.mcp-consent",
        "[data-consent-dialog]",
        ".consent-dialog",
        '.jp-Dialog:has-text("consent")',
        '.jp-Dialog:has-text("approve")',
        '.jp-Dialog:has-text("Allow")',
        '.jp-Dialog:has-text("Confirm")',
    ]

    for selector in selectors:
        try:
            dialog = page.locator(selector)
            dialog.wait_for(timeout=timeout)
            if dialog.count() > 0:
                return dialog.first
        except PlaywrightTimeout:
            continue
        except Exception:
            continue
    return None


def click_consent_approve(page: Page, dialog=None, timeout: int = 2000):
    """Click the approve/allow button in consent dialog.

    Args:
        page: Playwright page
        dialog: Optional dialog locator to scope search
        timeout: Timeout for button click

    Returns:
        True if button clicked, False otherwise
    """
    approve_selectors = [
        'button:has-text("Approve")',
        'button:has-text("Allow")',
        'button:has-text("Accept")',
        'button:has-text("Yes")',
        'button:has-text("OK")',
        'button:has-text("Confirm")',
        ".mcp-approve-btn",
        '[data-action="approve"]',
        ".jp-mod-accept",
    ]

    scope = dialog if dialog else page
    for selector in approve_selectors:
        try:
            btn = scope.locator(selector)
            if btn.count() > 0:
                btn.first.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def click_consent_deny(page: Page, dialog=None, timeout: int = 2000):
    """Click the deny/decline button in consent dialog.

    Args:
        page: Playwright page
        dialog: Optional dialog locator to scope search
        timeout: Timeout for button click

    Returns:
        True if button clicked, False otherwise
    """
    deny_selectors = [
        'button:has-text("Deny")',
        'button:has-text("Decline")',
        'button:has-text("Reject")',
        'button:has-text("Cancel")',
        'button:has-text("No")',
        ".mcp-deny-btn",
        '[data-action="deny"]',
        ".jp-mod-reject",
    ]

    scope = dialog if dialog else page
    for selector in deny_selectors:
        try:
            btn = scope.locator(selector)
            if btn.count() > 0:
                btn.first.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def handle_consent_with_action(
    page: Page, action: str = "approve", timeout: int = 5000
):
    """Wait for consent dialog and perform action.

    Args:
        page: Playwright page
        action: "approve" or "deny"
        timeout: Timeout for dialog appearance

    Returns:
        True if action performed, False if dialog not found
    """
    dialog = wait_for_consent_dialog(page, timeout=timeout)
    if not dialog:
        return False

    if action == "approve":
        return click_consent_approve(page, dialog)
    elif action == "deny":
        return click_consent_deny(page, dialog)
    return False


def is_consent_dialog_visible(page: Page, timeout: int = 1000):
    """Check if consent dialog is currently visible.

    Args:
        page: Playwright page
        timeout: Timeout to wait for dialog

    Returns:
        True if dialog is visible, False otherwise
    """
    dialog = wait_for_consent_dialog(page, timeout=timeout)
    return dialog is not None


def dismiss_any_dialog(page: Page, timeout: int = 2000):
    """Try to dismiss any open dialog by clicking cancel/close.

    Args:
        page: Playwright page
        timeout: Timeout for finding buttons

    Returns:
        True if a dialog was dismissed, False otherwise
    """
    close_selectors = [
        'button:has-text("Cancel")',
        'button:has-text("Close")',
        ".jp-Dialog-close",
        '[aria-label="Close"]',
        ".close-btn",
    ]

    for selector in close_selectors:
        try:
            btn = page.locator(selector)
            if btn.count() > 0:
                btn.first.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False
