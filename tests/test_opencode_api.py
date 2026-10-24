from unittest.mock import MagicMock, patch

import pytest

from utils.opencode_api import OpencodeAPI


@pytest.fixture
def opencode_api(logger):
    return OpencodeAPI(
        logger=logger,
        base_url="http://localhost:8080",
        username="test_user",
        password="test_password"
    )


def build_response(status_code=200, json_data=None, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.text = text
    return response


def test_get_basic_auth_uses_configured_credentials(opencode_api):
    auth = opencode_api.get_basic_auth()

    assert auth.username == "test_user"
    assert auth.password == "test_password"


@patch("utils.opencode_api.requests.get")
def test_get_info_returns_json_on_success(mock_get, opencode_api):
    mock_get.return_value = build_response(json_data={"version": "2.1.3"})

    assert opencode_api.get_info() == {"version": "2.1.3"}
    assert mock_get.call_args.args[0] == "http://localhost:8080/api/info"


@patch("utils.opencode_api.requests.get")
def test_get_info_returns_none_on_error(mock_get, opencode_api):
    mock_get.return_value = build_response(status_code=500, text="failure")

    assert opencode_api.get_info() is None


@patch("utils.opencode_api.requests.get")
def test_get_health_returns_true_when_info_is_available(mock_get, opencode_api):
    mock_get.return_value = build_response(json_data={"version": "2.1.3"})

    assert opencode_api.get_health() is True


@patch("utils.opencode_api.requests.get")
def test_get_health_returns_false_when_info_fails(mock_get, opencode_api):
    mock_get.return_value = build_response(status_code=500, text="failure")

    assert opencode_api.get_health() is False


@patch("utils.opencode_api.requests.get")
def test_get_config_returns_json_on_success(mock_get, opencode_api):
    mock_get.return_value = build_response(json_data=[{"type": "document"}])

    assert opencode_api.get_config() == [{"type": "document"}]


@patch("utils.opencode_api.requests.get")
def test_get_config_returns_none_on_error(mock_get, opencode_api):
    mock_get.return_value = build_response(status_code=500, text="failure")

    assert opencode_api.get_config() is None


@patch("utils.opencode_api.requests.post")
def test_get_session_posts_agent_model_and_directory(mock_post, opencode_api):
    mock_post.return_value = build_response(json_data={"data": {"id": "session-1"}})

    session = opencode_api.get_session(
        "product-manager",
        {"id": "model", "providerID": "provider"},
        "/project"
    )

    assert session == {"data": {"id": "session-1"}}
    payload = mock_post.call_args.kwargs["json"]
    assert payload == {
        "agent": "product-manager",
        "model": {"id": "model", "providerID": "provider"},
        "location": {"directory": "/project"},
    }


@patch("utils.opencode_api.requests.post")
def test_send_prompt_builds_file_uris(mock_post, opencode_api):
    mock_post.return_value = build_response(json_data={"ok": True})

    result = opencode_api.send_prompt(
        {"data": {"id": "session-1"}},
        "prompt",
        ["/tmp/file.md"]
    )

    assert result == {"ok": True}
    payload = mock_post.call_args.kwargs["json"]
    assert payload == {
        "text": "prompt",
        "files": [{"uri": "file:///tmp/file.md"}],
    }


@patch("utils.opencode_api.requests.post")
def test_send_prompt_returns_none_on_error(mock_post, opencode_api):
    mock_post.return_value = build_response(status_code=400, text="invalid request")

    assert opencode_api.send_prompt({"data": {"id": "session-1"}}, "prompt") is None


@patch("utils.opencode_api.requests.post")
def test_wait_session_returns_true_on_no_content(mock_post, opencode_api):
    mock_post.return_value = build_response(status_code=204)

    assert opencode_api.wait_session({"data": {"id": "session-1"}}) is True


@patch("utils.opencode_api.requests.post")
def test_wait_session_returns_false_on_unexpected_status(mock_post, opencode_api):
    mock_post.return_value = build_response(status_code=500, text="failure")

    assert opencode_api.wait_session({"data": {"id": "session-1"}}) is False


@patch("utils.opencode_api.requests.get")
def test_get_session_messages_returns_json_on_success(mock_get, opencode_api):
    mock_get.return_value = build_response(json_data={"data": []})

    assert opencode_api.get_session_messages({"data": {"id": "session-1"}}) == {"data": []}
    assert mock_get.call_args.kwargs["params"] == {"order": "asc"}


@patch("utils.opencode_api.requests.get")
def test_get_session_messages_returns_none_on_error(mock_get, opencode_api):
    mock_get.return_value = build_response(status_code=500, text="failure")

    assert opencode_api.get_session_messages({"data": {"id": "session-1"}}) is None
