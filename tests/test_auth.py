"""Tests for app/core/auth.py"""

import json
import pytest
from unittest.mock import MagicMock, patch, mock_open

from app.core.auth import (
    get_client_id,
    get_client_secret,
    save_credentials_to_db,
    get_credentials_from_db,
    get_oauth_flow,
)

_CREDS_JSON = json.dumps({
    "installed": {
        "client_id": "fake-client-id",
        "client_secret": "fake-client-secret",
    }
})


class TestGetClientId:
    @pytest.mark.asyncio
    async def test_reads_client_id_from_credentials_json(self):
        with patch("builtins.open", mock_open(read_data=_CREDS_JSON)):
            result = await get_client_id()
        assert result == "fake-client-id"

    @pytest.mark.asyncio
    async def test_returns_none_when_key_missing(self):
        data = json.dumps({"installed": {}})
        with patch("builtins.open", mock_open(read_data=data)):
            result = await get_client_id()
        assert result is None


class TestGetClientSecret:
    @pytest.mark.asyncio
    async def test_reads_client_secret_from_credentials_json(self):
        with patch("builtins.open", mock_open(read_data=_CREDS_JSON)):
            result = await get_client_secret()
        assert result == "fake-client-secret"

    @pytest.mark.asyncio
    async def test_returns_none_when_key_missing(self):
        data = json.dumps({"installed": {}})
        with patch("builtins.open", mock_open(read_data=data)):
            result = await get_client_secret()
        assert result is None


class TestGetOAuthFlow:
    @pytest.mark.asyncio
    async def test_raises_if_credentials_file_missing(self, tmp_path):
        with patch("app.core.auth.CREDENTIALS_PATH", str(tmp_path / "missing.json")):
            with pytest.raises(FileNotFoundError, match="not found"):
                await get_oauth_flow()

    @pytest.mark.asyncio
    async def test_returns_flow_when_file_exists(self, tmp_path):
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(_CREDS_JSON)
        mock_flow = MagicMock()

        with patch("app.core.auth.CREDENTIALS_PATH", str(creds_file)), \
             patch("app.core.auth.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow):
            result = await get_oauth_flow()

        assert result is mock_flow


class TestSaveCredentialsToDB:
    def _make_creds(self, refresh="refresh123", token="access123", expiry=None):
        creds = MagicMock()
        creds.refresh_token = refresh
        creds.token = token
        creds.expiry = expiry
        return creds

    @pytest.mark.asyncio
    async def test_creates_new_user_when_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.core.auth.SessionLocal", return_value=mock_db):
            await save_credentials_to_db("new@example.com", self._make_creds())

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_updates_existing_user_tokens(self):
        existing = MagicMock()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        with patch("app.core.auth.SessionLocal", return_value=mock_db):
            await save_credentials_to_db("existing@example.com", self._make_creds("new_r", "new_a"))

        assert existing.refresh_token == "new_r"
        assert existing.access_token == "new_a"
        mock_db.add.assert_not_called()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_on_exception(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = Exception("DB error")

        with patch("app.core.auth.SessionLocal", return_value=mock_db):
            with pytest.raises(Exception, match="DB error"):
                await save_credentials_to_db("user@example.com", self._make_creds())

        mock_db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_db_session_always_closed(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.core.auth.SessionLocal", return_value=mock_db):
            await save_credentials_to_db("user@example.com", self._make_creds())

        mock_db.close.assert_called_once()


class TestGetCredentialsFromDB:
    @pytest.mark.asyncio
    async def test_raises_value_error_when_user_not_found(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.core.auth.SessionLocal", return_value=mock_db), \
             patch("builtins.open", mock_open(read_data=_CREDS_JSON)):
            with pytest.raises(ValueError, match="No credentials found"):
                await get_credentials_from_db("missing@example.com")

    @pytest.mark.asyncio
    async def test_returns_credentials_for_existing_user(self):
        mock_user = MagicMock(access_token="access123", refresh_token="refresh123")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_creds = MagicMock(expired=False)

        with patch("app.core.auth.SessionLocal", return_value=mock_db), \
             patch("builtins.open", mock_open(read_data=_CREDS_JSON)), \
             patch("app.core.auth.Credentials", return_value=mock_creds):
            result = await get_credentials_from_db("user@example.com")

        assert result is mock_creds

    @pytest.mark.asyncio
    async def test_refreshes_expired_credentials(self):
        mock_user = MagicMock(access_token="old_access", refresh_token="refresh123")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_creds = MagicMock(expired=True, refresh_token="refresh123")

        with patch("app.core.auth.SessionLocal", return_value=mock_db), \
             patch("builtins.open", mock_open(read_data=_CREDS_JSON)), \
             patch("app.core.auth.Credentials", return_value=mock_creds), \
             patch("app.core.auth.Request") as mock_request:
            await get_credentials_from_db("user@example.com")

        mock_creds.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_always_closed(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.core.auth.SessionLocal", return_value=mock_db), \
             patch("builtins.open", mock_open(read_data=_CREDS_JSON)):
            with pytest.raises(ValueError):
                await get_credentials_from_db("x@example.com")

        mock_db.close.assert_called_once()
