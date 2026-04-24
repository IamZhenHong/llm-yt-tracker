from unittest.mock import MagicMock
from src.resolve_channels import resolve_handle_to_id


def test_resolve_handle_queries_youtube_api_and_returns_channel_id():
    youtube = MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "UCxxx"}]
    }

    result = resolve_handle_to_id(youtube, "@AndrejKarpathy")

    assert result == "UCxxx"
    youtube.channels.return_value.list.assert_called_once_with(
        part="id", forHandle="@AndrejKarpathy"
    )


def test_resolve_handle_returns_none_when_not_found():
    youtube = MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = {"items": []}

    result = resolve_handle_to_id(youtube, "@missing")

    assert result is None
