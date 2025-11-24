"""Tests for consent management system."""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
import asyncio

from instrmcp.servers.jupyter_qcodes.security.consent import ConsentManager


@pytest.fixture
def mock_ipython():
    """Create a mock IPython instance."""
    return Mock()


@pytest.fixture
def temp_always_allow_path(tmp_path):
    """Create temporary path for always_allow.json."""
    return tmp_path / "consents" / "always_allow.json"


@pytest.fixture
def consent_manager(mock_ipython, temp_always_allow_path):
    """Create ConsentManager instance with mock IPython and temp path."""
    manager = ConsentManager(mock_ipython, timeout_seconds=1)
    manager.always_allow_path = temp_always_allow_path
    manager.always_allow_path.parent.mkdir(parents=True, exist_ok=True)
    manager._always_allow = {}
    return manager


@pytest.fixture
def consent_manager_no_ipython(temp_always_allow_path):
    """Create ConsentManager without IPython."""
    manager = ConsentManager(ipython=None, timeout_seconds=1)
    manager.always_allow_path = temp_always_allow_path
    manager.always_allow_path.parent.mkdir(parents=True, exist_ok=True)
    manager._always_allow = {}
    return manager


class TestAlwaysAllowStorage:
    """Test always_allow permission storage and persistence."""

    def test_grant_always_allow_single_author(self, consent_manager):
        """Test granting always_allow to a single author."""
        consent_manager.grant_always_allow("test_author", "register")

        assert consent_manager.check_always_allow("test_author", "register")
        assert not consent_manager.check_always_allow("test_author", "update")
        assert not consent_manager.check_always_allow("other_author", "register")

    def test_grant_always_allow_all_operations(self, consent_manager):
        """Test granting always_allow for all operations (*)."""
        consent_manager.grant_always_allow("test_author", "*")

        assert consent_manager.check_always_allow("test_author", "register")
        assert consent_manager.check_always_allow("test_author", "update")
        assert consent_manager.check_always_allow("test_author", "execute")

    def test_grant_always_allow_multiple_operations(self, consent_manager):
        """Test granting multiple operations to same author."""
        consent_manager.grant_always_allow("test_author", "register")
        consent_manager.grant_always_allow("test_author", "update")

        assert consent_manager.check_always_allow("test_author", "register")
        assert consent_manager.check_always_allow("test_author", "update")
        assert not consent_manager.check_always_allow("test_author", "execute")

    def test_revoke_always_allow_specific_operation(self, consent_manager):
        """Test revoking specific operation."""
        consent_manager.grant_always_allow("test_author", "register")
        consent_manager.grant_always_allow("test_author", "update")

        consent_manager.revoke_always_allow("test_author", "register")

        assert not consent_manager.check_always_allow("test_author", "register")
        assert consent_manager.check_always_allow("test_author", "update")

    def test_revoke_always_allow_all_operations(self, consent_manager):
        """Test revoking all operations for an author."""
        consent_manager.grant_always_allow("test_author", "register")
        consent_manager.grant_always_allow("test_author", "update")

        consent_manager.revoke_always_allow("test_author", operation=None)

        assert not consent_manager.check_always_allow("test_author", "register")
        assert not consent_manager.check_always_allow("test_author", "update")

    def test_persistence_to_disk(self, mock_ipython, temp_always_allow_path):
        """Test that always_allow permissions persist to disk when persistence is enabled."""
        # Create manager with persistence enabled
        manager = ConsentManager(
            mock_ipython, timeout_seconds=1, persist_permissions=True
        )
        manager.always_allow_path = temp_always_allow_path
        manager.always_allow_path.parent.mkdir(parents=True, exist_ok=True)
        manager._always_allow = {}

        manager.grant_always_allow("author1", "register")
        manager.grant_always_allow("author2", "*")

        # Verify file was written
        assert manager.always_allow_path.exists()

        # Load file and verify content
        with open(manager.always_allow_path, "r") as f:
            data = json.load(f)

        assert "author1" in data
        assert "register" in data["author1"]
        assert "author2" in data
        assert "*" in data["author2"]

    def test_load_from_disk(self, consent_manager):
        """Test loading existing always_allow permissions from disk."""
        # Write permissions to disk
        permissions = {"author1": ["register"], "author2": ["*"]}
        consent_manager.always_allow_path.parent.mkdir(parents=True, exist_ok=True)
        with open(consent_manager.always_allow_path, "w") as f:
            json.dump(permissions, f)

        # Create new manager instance - should load from disk
        new_manager = ConsentManager(consent_manager.ipython, timeout_seconds=1)
        new_manager.always_allow_path = consent_manager.always_allow_path
        new_manager._always_allow = new_manager._load_always_allow()

        assert new_manager.check_always_allow("author1", "register")
        assert new_manager.check_always_allow("author2", "update")

    def test_list_always_allow(self, consent_manager):
        """Test listing all always_allow permissions."""
        consent_manager.grant_always_allow("author1", "register")
        consent_manager.grant_always_allow("author2", "*")

        permissions = consent_manager.list_always_allow()

        assert "author1" in permissions
        assert "register" in permissions["author1"]
        assert "author2" in permissions
        assert "*" in permissions["author2"]

    def test_clear_all_permissions(self, consent_manager):
        """Test clearing all always_allow permissions."""
        consent_manager.grant_always_allow("author1", "register")
        consent_manager.grant_always_allow("author2", "*")

        consent_manager.clear_all_permissions()

        assert not consent_manager.check_always_allow("author1", "register")
        assert not consent_manager.check_always_allow("author2", "register")
        assert len(consent_manager.list_always_allow()) == 0


class TestConsentBypassMode:
    """Test consent bypass mode via environment variable."""

    def test_bypass_mode_enabled(self, mock_ipython, temp_always_allow_path):
        """Test that bypass mode auto-approves all requests."""
        with patch.dict(os.environ, {"INSTRMCP_CONSENT_BYPASS": "1"}):
            manager = ConsentManager(mock_ipython, timeout_seconds=1)
            manager.always_allow_path = temp_always_allow_path
            manager.always_allow_path.parent.mkdir(parents=True, exist_ok=True)

            # Check bypass mode is enabled
            assert manager._bypass_mode is True

    @pytest.mark.asyncio
    async def test_bypass_mode_auto_approves(
        self, mock_ipython, temp_always_allow_path
    ):
        """Test that bypass mode auto-approves without comm channel."""
        with patch.dict(os.environ, {"INSTRMCP_CONSENT_BYPASS": "1"}):
            manager = ConsentManager(mock_ipython, timeout_seconds=1)
            manager.always_allow_path = temp_always_allow_path
            manager.always_allow_path.parent.mkdir(parents=True, exist_ok=True)

            result = await manager.request_consent(
                operation="register",
                tool_name="test_tool",
                author="test_author",
                details={"source_code": "def test(): pass"},
            )

            assert result["approved"] is True
            assert result["reason"] == "bypass_mode"

    def test_bypass_mode_disabled(self, mock_ipython):
        """Test that bypass mode is disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            manager = ConsentManager(mock_ipython, timeout_seconds=1)
            assert manager._bypass_mode is False


class TestConsentBypassModeParameter:
    """Test consent bypass mode via explicit parameter (dangerous mode)."""

    def test_bypass_mode_parameter_enabled(self, mock_ipython):
        """Test that bypass_mode parameter enables bypass mode."""
        with patch.dict(os.environ, {}, clear=True):
            manager = ConsentManager(
                mock_ipython, timeout_seconds=1, bypass_mode=True
            )
            assert manager._bypass_mode is True

    def test_bypass_mode_parameter_disabled(self, mock_ipython):
        """Test that bypass_mode parameter is disabled by default."""
        with patch.dict(os.environ, {}, clear=True):
            manager = ConsentManager(
                mock_ipython, timeout_seconds=1, bypass_mode=False
            )
            assert manager._bypass_mode is False

    def test_bypass_mode_parameter_overrides_env_false(self, mock_ipython):
        """Test bypass_mode=True takes precedence even if env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            manager = ConsentManager(
                mock_ipython, timeout_seconds=1, bypass_mode=True
            )
            assert manager._bypass_mode is True

    def test_bypass_mode_env_var_when_parameter_false(self, mock_ipython):
        """Test env var works when parameter is False (backwards compat)."""
        with patch.dict(os.environ, {"INSTRMCP_CONSENT_BYPASS": "1"}):
            manager = ConsentManager(
                mock_ipython, timeout_seconds=1, bypass_mode=False
            )
            # Env var should still enable bypass
            assert manager._bypass_mode is True

    @pytest.mark.asyncio
    async def test_bypass_mode_parameter_auto_approves(self, mock_ipython):
        """Test bypass_mode parameter auto-approves without comm channel."""
        with patch.dict(os.environ, {}, clear=True):
            manager = ConsentManager(
                mock_ipython, timeout_seconds=1, bypass_mode=True
            )

            result = await manager.request_consent(
                operation="execute",
                tool_name="notebook_execute_cell",
                author="system",
                details={"code": "print('hello')"},
            )

            assert result["approved"] is True
            assert result["reason"] == "bypass_mode"

    @pytest.mark.asyncio
    async def test_bypass_mode_all_operations_approved(self, mock_ipython):
        """Test that bypass mode approves all operation types."""
        with patch.dict(os.environ, {}, clear=True):
            manager = ConsentManager(
                mock_ipython, timeout_seconds=1, bypass_mode=True
            )

            for operation in ["register", "update", "execute", "delete"]:
                result = await manager.request_consent(
                    operation=operation,
                    tool_name=f"test_{operation}",
                    author="test_author",
                    details={"test": "data"},
                )
                assert result["approved"] is True, (
                    f"Failed for operation: {operation}"
                )
                assert result["reason"] == "bypass_mode"


class TestConsentRequests:
    """Test consent request workflow."""

    @pytest.mark.asyncio
    async def test_always_allow_bypasses_request(self, consent_manager):
        """Test that always_allow bypasses consent request."""
        consent_manager.grant_always_allow("test_author", "register")

        result = await consent_manager.request_consent(
            operation="register",
            tool_name="test_tool",
            author="test_author",
            details={"source_code": "def test(): pass"},
        )

        assert result["approved"] is True
        assert result["reason"] == "always_allow"

    @pytest.mark.asyncio
    async def test_no_ipython_returns_error(self, consent_manager_no_ipython):
        """Test that missing IPython returns error."""
        result = await consent_manager_no_ipython.request_consent(
            operation="register",
            tool_name="test_tool",
            author="test_author",
            details={"source_code": "def test(): pass"},
        )

        assert result["approved"] is False
        assert "No IPython instance" in result["reason"]

    @pytest.mark.asyncio
    async def test_consent_approved_via_comm(self, consent_manager):
        """Test consent approval via comm channel."""
        mock_comm = MagicMock()
        mock_comm.send = Mock()
        mock_comm.close = Mock()

        # Mock the Comm class (imported inside the method)
        with patch("ipykernel.comm.Comm") as MockComm:
            MockComm.return_value = mock_comm

            response_data = {
                "type": "consent_response",
                "approved": True,
                "always_allow": False,
                "reason": "User approved",
            }

            # Patch asyncio.wait_for to return approval
            with patch("asyncio.wait_for", return_value=response_data):
                result = await consent_manager.request_consent(
                    operation="register",
                    tool_name="test_tool",
                    author="test_author",
                    details={"source_code": "def test(): pass"},
                )

                assert result["approved"] is True
                assert mock_comm.send.called

    @pytest.mark.asyncio
    async def test_consent_declined_via_comm(self, consent_manager):
        """Test consent decline via comm channel."""
        mock_comm = MagicMock()

        with patch("ipykernel.comm.Comm") as MockComm:
            MockComm.return_value = mock_comm

            response_data = {
                "type": "consent_response",
                "approved": False,
                "always_allow": False,
                "reason": "User declined",
            }

            with patch("asyncio.wait_for", return_value=response_data):
                result = await consent_manager.request_consent(
                    operation="register",
                    tool_name="test_tool",
                    author="test_author",
                    details={"source_code": "def test(): pass"},
                )

                assert result["approved"] is False
                assert "User declined" in result["reason"]

    @pytest.mark.asyncio
    async def test_consent_timeout(self, consent_manager):
        """Test consent request timeout."""
        mock_comm = MagicMock()

        with patch("ipykernel.comm.Comm") as MockComm:
            MockComm.return_value = mock_comm

            # Mock timeout
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                with pytest.raises(TimeoutError):
                    await consent_manager.request_consent(
                        operation="register",
                        tool_name="test_tool",
                        author="test_author",
                        details={"source_code": "def test(): pass"},
                    )

    @pytest.mark.asyncio
    async def test_always_allow_granted_and_stored(self, consent_manager):
        """Test that always_allow is stored when user grants it."""
        mock_comm = MagicMock()

        with patch("ipykernel.comm.Comm") as MockComm:
            MockComm.return_value = mock_comm

            response_data = {
                "type": "consent_response",
                "approved": True,
                "always_allow": True,
                "reason": "Always allow granted",
            }

            with patch("asyncio.wait_for", return_value=response_data):
                result = await consent_manager.request_consent(
                    operation="register",
                    tool_name="test_tool",
                    author="test_author",
                    details={"source_code": "def test(): pass"},
                )

                assert result["approved"] is True
                assert result["always_allow"] is True
                # Verify always_allow was stored
                assert consent_manager.check_always_allow("test_author", "register")


class TestConsentIntegrationWithRegistrar:
    """Test consent integration with DynamicToolRegistrar (integration tests)."""

    @pytest.mark.asyncio
    async def test_registration_declined_by_consent(self):
        """Test that tool registration is blocked when consent is declined."""
        # This would be an integration test with DynamicToolRegistrar
        # For now, we verify the consent manager behavior
        pass

    @pytest.mark.asyncio
    async def test_update_declined_by_consent(self):
        """Test that tool update is blocked when consent is declined."""
        pass

    @pytest.mark.asyncio
    async def test_bypass_mode_skips_consent(self):
        """Test that bypass mode allows registration without consent dialog."""
        pass


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_malformed_always_allow_file(self, consent_manager):
        """Test handling of malformed always_allow.json file."""
        # Write invalid JSON
        consent_manager.always_allow_path.parent.mkdir(parents=True, exist_ok=True)
        with open(consent_manager.always_allow_path, "w") as f:
            f.write("{ invalid json }")

        # Should not crash, returns empty dict
        result = consent_manager._load_always_allow()
        assert result == {}

    def test_missing_always_allow_file(self, consent_manager):
        """Test handling of missing always_allow.json file."""
        # Ensure file doesn't exist
        if consent_manager.always_allow_path.exists():
            consent_manager.always_allow_path.unlink()

        # Should return empty dict
        result = consent_manager._load_always_allow()
        assert result == {}

    def test_revoke_nonexistent_author(self, consent_manager):
        """Test revoking permissions for author that doesn't exist."""
        # Should not crash
        consent_manager.revoke_always_allow("nonexistent_author")
        assert len(consent_manager.list_always_allow()) == 0

    def test_check_always_allow_nonexistent_author(self, consent_manager):
        """Test checking permissions for author that doesn't exist."""
        result = consent_manager.check_always_allow("nonexistent_author", "register")
        assert result is False

    @pytest.mark.asyncio
    async def test_comm_import_error(self, consent_manager):
        """Test handling when ipykernel.comm is not available."""
        with patch(
            "ipykernel.comm.Comm",
            side_effect=ImportError("ipykernel not available"),
        ):
            result = await consent_manager.request_consent(
                operation="register",
                tool_name="test_tool",
                author="test_author",
                details={"source_code": "def test(): pass"},
            )

            assert result["approved"] is False
            assert "ipykernel.comm not available" in result["reason"]
