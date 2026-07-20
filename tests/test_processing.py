import json
from datetime import datetime, timezone

from chat_dir.csv_output import ChatCsvRow, extract_response_datetimes, format_csv_datetime, latest_response_datetime, render_csv
from chat_dir.models import ChatLink
from chat_dir.output import format_json, format_urls, render
from chat_dir.providers.chatgpt import dedupe_chats, links_from_dom_payload, normalize_chat_url, normalize_title


def test_relative_url_becomes_absolute_and_chat_id_extracted():
    assert normalize_chat_url("/c/abc123?x=1#frag") == ("https://chatgpt.com/c/abc123", "abc123")


def test_project_url_keeps_project_path():
    assert normalize_chat_url("https://chatgpt.com/g/g-p-123/c/abc?x=1#frag") == (
        "https://chatgpt.com/g/g-p-123/c/abc",
        "abc",
    )


def test_non_chat_url_excluded():
    assert normalize_chat_url("https://chatgpt.com/g/g-123") is None


def test_duplicates_removed_and_order_preserved():
    chats = [ChatLink("u1"), ChatLink("u2"), ChatLink("u1")]
    assert [c.url for c in dedupe_chats(chats)] == ["u1", "u2"]


def test_title_whitespace_normalized():
    assert normalize_title("  hello\n\t world  ") == "hello world"


def test_missing_title_keeps_url():
    rows = [{"href": "/c/abc", "ariaLabel": "", "title": None, "text": "  "}]
    chats = links_from_dom_payload(rows)
    assert chats == [ChatLink(url="https://chatgpt.com/c/abc", title=None, chat_id="abc")]


def test_title_priority_and_filtering():
    rows = [
        {"href": "/c/one", "ariaLabel": " Aria\nTitle ", "title": "bad", "text": "bad"},
        {"href": "/not-chat", "text": "skip"},
    ]
    chats = links_from_dom_payload(rows)
    assert chats[0].title == "Aria Title"


def test_json_output_is_valid():
    text = format_json([ChatLink(url="https://chatgpt.com/c/a", title="A", chat_id="a")])
    assert json.loads(text) == [{"chat_id": "a", "title": "A", "url": "https://chatgpt.com/c/a"}]


def test_urls_only_one_per_line():
    assert format_urls([ChatLink("u1"), ChatLink("u2")]) == "u1\nu2\n"


def test_render_json_does_not_include_logs(capsys):
    output = render([ChatLink("u", chat_id="id")], json_mode=True)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(output)[0]["url"] == "u"


def test_response_datetime_formats_to_tokyo_without_seconds():
    value = datetime.fromisoformat("2026-07-10T10:35:22+09:00")
    assert format_csv_datetime(value) == "202607101035"


def test_latest_response_datetime_ignores_unknown_and_invalid():
    latest = latest_response_datetime(
        [
            "response_datetime: 2026-07-10T10:35:22+09:00\nbody",
            "response_datetime: unknown\nresponse_datetime: 2026-07-11T12:30:59+09:00",
            "response_datetime: 2026-99-99T00:00:00+09:00",
        ]
    )
    assert latest == datetime.fromisoformat("2026-07-11T12:30:59+09:00")


def test_extract_requires_line_prefix():
    assert extract_response_datetimes("quoted response_datetime: 2026-07-10T10:35:22+09:00") == []


def test_csv_excludes_undated_when_not_rendered():
    csv_text = render_csv([ChatCsvRow("https://chatgpt.com/c/a", datetime.fromisoformat("2026-07-10T10:35:22+09:00"))])
    assert csv_text == "202607101035,https://chatgpt.com/c/a\r\n"


def test_csv_include_undated_blank_date_and_no_header():
    csv_text = render_csv([ChatCsvRow("https://chatgpt.com/c/a", None)])
    assert csv_text == ",https://chatgpt.com/c/a\r\n"


def test_csv_sorts_oldest_first_then_url():
    rows = [
        ChatCsvRow("https://chatgpt.com/c/b", datetime.fromisoformat("2026-07-11T10:00:00+09:00")),
        ChatCsvRow("https://chatgpt.com/c/a", datetime.fromisoformat("2026-07-10T10:00:59+09:00")),
        ChatCsvRow("https://chatgpt.com/c/c", datetime(2026, 7, 10, 1, 0, tzinfo=timezone.utc)),
    ]
    assert render_csv(rows).splitlines() == [
        "202607101000,https://chatgpt.com/c/c",
        "202607101000,https://chatgpt.com/c/a",
        "202607111000,https://chatgpt.com/c/b",
    ]
