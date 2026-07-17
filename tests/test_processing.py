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
