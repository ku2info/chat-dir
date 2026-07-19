import json

from chat_dir.models import ChatLink
from chat_dir.output import format_json, format_urls, render
from chat_dir.providers.chatgpt import dedupe_chats, links_from_dom_payload, normalize_chat_url, normalize_title


def test_relative_url_becomes_absolute_and_chat_id_extracted():
    assert normalize_chat_url("/c/abc123?x=1#frag") == ("https://chatgpt.com/c/abc123", "abc123")


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

from datetime import timezone

from chat_dir.csv_output import build_csv_rows, extract_response_datetimes, format_csv_rows, latest_response_datetime, parse_response_datetime


def test_response_datetime_formats_to_tokyo_without_seconds():
    dt = parse_response_datetime("2026-07-10T10:35:22+09:00")
    row = build_csv_rows([ChatLink("u")], {"u": dt}).rows[0]
    assert row.formatted_datetime == "202607101035"


def test_latest_response_datetime_selects_max_and_ignores_unknown_and_invalid():
    text = """response_datetime: 2026-07-10T10:35:22+09:00
response_datetime: unknown
response_datetime: 2026-99-99T99:99:99+09:00
response_datetime: 2026-07-11T12:30:58+09:00
"""
    assert latest_response_datetime(text).isoformat() == "2026-07-11T12:30:58+09:00"
    assert len(extract_response_datetimes(text)) == 2


def test_undated_chat_excluded_by_default():
    result = build_csv_rows([ChatLink("u")], {"u": None})
    assert result.rows == []
    assert result.undated_count == 1


def test_include_undated_outputs_blank_datetime():
    result = build_csv_rows([ChatLink("u")], {"u": None}, include_undated=True)
    assert format_csv_rows(result.rows) == ",u\r\n"


def test_project_chat_url_is_preserved_when_normalizing():
    assert normalize_chat_url("https://chatgpt.com/g/g-p-xxxx/c/yyyy?x=1#frag") == (
        "https://chatgpt.com/g/g-p-xxxx/c/yyyy",
        "yyyy",
    )


def test_normal_chat_url_is_preserved_when_normalizing():
    assert normalize_chat_url("https://chatgpt.com/c/yyyy?x=1") == ("https://chatgpt.com/c/yyyy", "yyyy")


def test_csv_sorted_oldest_first_no_header():
    old = parse_response_datetime("2026-07-10T10:35:22+09:00")
    new = parse_response_datetime("2026-07-11T12:30:58+09:00")
    result = build_csv_rows([ChatLink("https://new"), ChatLink("https://old")], {"https://new": new, "https://old": old})
    assert format_csv_rows(result.rows) == "202607101035,https://old\r\n202607111230,https://new\r\n"


def test_csv_generation_does_not_log_to_stdout(capsys):
    result = build_csv_rows([ChatLink("u")], {"u": parse_response_datetime("2026-07-10T10:35:22Z")})
    output = format_csv_rows(result.rows)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert output == "202607101935,u\r\n"

from chat_dir.csv_output import collect_latest_by_url


def test_one_scan_failure_does_not_stop_overall_processing():
    chats = [ChatLink("ok1"), ChatLink("bad"), ChatLink("ok2")]

    def loader(chat):
        if chat.url == "bad":
            raise RuntimeError("boom")
        return parse_response_datetime("2026-07-10T10:35:22+09:00")

    latest_by_url, errors = collect_latest_by_url(chats, loader)
    assert errors == 1
    assert sorted(latest_by_url) == ["ok1", "ok2"]
