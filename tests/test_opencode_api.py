import logging
from unittest.mock import MagicMock, patch
import pytest

from utils.log_utils import LogUtils
from utils.opencode_api import OpencodeAPI


@pytest.fixture
def logger():
    logger_instance = LogUtils(path="/tmp", console=False)
    return logger_instance


@pytest.fixture
def opencode_api(logger):
    return OpencodeAPI(
        logger=logger,
        base_url="http://localhost:8080",
        username="test_user",
        password="test_password"
    )


class TestOpencodeAPI:

    def test_init(self, logger):
        api = OpencodeAPI(
            logger=logger,
            base_url="http://localhost:8080",
            username="test_user",
            password="test_password"
        )
        assert api.base_url == "http://localhost:8080"
        assert api._username == "test_user"
        assert api._password == "test_password"

    def test_get_basic_auth_header(self, opencode_api):
        auth_header = opencode_api.get_basic_auth()
        assert auth_header.username == "test_user"
        assert auth_header.password == "test_password"

    @patch("utils.opencode_api.requests.get")
    def test_get_health_success(self, mock_get, opencode_api):
        """Test get_health returns None when request succeeds."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = opencode_api.get_health()

        assert mock_get.called
        assert result is None

    @patch("utils.opencode_api.requests.get")
    def test_get_health_request_error(self, mock_get, opencode_api):
        """Test get_health handles request exceptions and logs error."""
        mock_get.side_effect = Exception("Connection error")

        result = opencode_api.get_health()

        assert mock_get.called
        assert result is None

    @patch("utils.opencode_api.requests.get")
    def test_get_health_http_error(self, mock_get, opencode_api):
        """Test get_health handles HTTP errors and logs error."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(side_effect=Exception("404 Not Found"))
        mock_get.return_value = mock_response

        result = opencode_api.get_health()

        assert mock_get.called
        assert result is None

    @patch("utils.opencode_api.requests.get")
    def test_get_health_url(self, mock_get, opencode_api):
        """Test get_health uses correct URL."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        opencode_api.get_health()

        assert mock_get.called
        call_args = mock_get.call_args
        assert call_args[1]["url"] == "http://localhost:8080/api/health"

    @patch("utils.opencode_api.requests.get")
    def test_get_health_uses_headers(self, mock_get, opencode_api):
        """Test get_health passes headers to requests."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        opencode_api.get_health()

        assert mock_get.called
        call_args = mock_get.call_args
        assert "headers" in call_args[1]

    @patch("utils.opencode_api.requests.get")
    def test_get_health_uses_data_payload(self, mock_get, opencode_api):
        """Test get_health passes empty data payload."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        opencode_api.get_health()

        assert mock_get.called
        call_args = mock_get.call_args
        assert call_args[1]["data"] == {}
