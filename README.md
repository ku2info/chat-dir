# ChatDir

ChatDir is a read-only Python CLI that opens ChatGPT with Playwright and lists chat titles and URLs visible to the logged-in user. It is intended as the first step before passing URLs to a separate tool such as `ob-save`.

## Requirements

- Python 3.10 or newer
- Playwright Chromium
- Windows 11 is the primary target; macOS and Linux use standard user data locations too.

## Install

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
playwright install chromium
chat-dir login
chat-dir --json
```

### Command Prompt

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -e .
playwright install chromium
chat-dir login
chat-dir --json
```

## Commands

```bash
chat-dir
chat-dir --json
chat-dir --urls-only
chat-dir --csv
chat-dir --csv --output ob-save-list.csv
chat-dir --csv --include-undated
chat-dir --json --output chats.json
chat-dir --headed
chat-dir --debug
chat-dir login
chat-dir --chrome login
```

`chat-dir login` opens a visible Chromium browser. Log in to ChatGPT manually, then close the browser window. The login state is reused on later runs.

If Google sign-in blocks Playwright Chromium with an unsafe browser warning, use `chat-dir --chrome login` to open the installed Google Chrome browser instead. Use `--chrome` on later collection commands too, for example `chat-dir --chrome --csv --output ob-save-list.csv`.

## Browser profile location

ChatDir uses a dedicated persistent Playwright profile and does not store it inside the repository by default.

- Windows: `%LOCALAPPDATA%\ChatDir\browser-profile`
- macOS: `~/Library/Application Support/ChatDir/browser-profile`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/chat-dir/browser-profile`

Set `CHAT_DIR_HOME` to override the base location for testing.

## Output examples

Human-readable output:

```text
1. チャット自動保存処理
   https://chatgpt.com/c/xxxxxxxx
```

JSON output:

```json
[
  {
    "chat_id": "xxxxxxxx",
    "title": "チャット自動保存処理",
    "url": "https://chatgpt.com/c/xxxxxxxx"
  }
]
```

URL-only output:

```text
https://chatgpt.com/c/xxxxxxxx
```

CSV output:

```text
202607101035,https://chatgpt.com/g/g-p-xxxx/c/yyyy
202607111230,https://chatgpt.com/c/zzzz
```

CSV output has no header and is written as UTF-8. The first column is the latest valid `response_datetime` found in the chat body, converted to `YYYYMMDDHHmm` in Asia/Tokyo with seconds truncated. It is not the ChatDir execution time or the date shown in the chat list. Chats without `response_datetime` are excluded by default and logged to stderr; `--include-undated` includes them with an empty first column. Rows are sorted from oldest final response datetime to newest, then by URL for deterministic ties.

## How collection works

The ChatGPT provider opens `https://chatgpt.com/`, searches DOM anchors whose `href` contains `/c/`, normalizes relative links to `https://chatgpt.com/c/{chat_id}` or `https://chatgpt.com/g/{project_id}/c/{chat_id}`, removes query strings and fragments, deduplicates by URL, and preserves discovery order. Titles are read from `aria-label`, then `title`, then visible link text, with whitespace normalized.

The provider scrolls the largest scrollable page/sidebar candidate and repeats extraction. It stops after several consecutive rounds with no new URLs, after `--max-scrolls`, or after `--timeout-ms`.

`--csv` is slower than list-only modes because it opens each chat URL, scrolls to the conversation bottom, and scans assistant message text for valid `response_datetime` lines. It reports progress, skipped undated chats, load errors, and a final summary to stderr so CSV data on stdout stays clean.

## Authentication and safety

ChatDir never prints cookies, access tokens, passwords, Authorization headers, or browser storage. It does not call private ChatGPT APIs and does not modify ChatGPT data. The MVP does not delete chats, rename chats, move projects, send messages, or save to Obsidian.

## Exit codes

- `0`: success
- `1`: general error
- `2`: not logged in
- `3`: no chats found
- `4`: timeout
- `5`: output error

Errors are printed to stderr. JSON output mode never mixes errors or debug logs into stdout.

## Current limitations

- The MVP collects links from the currently loaded ChatGPT UI and depends on ChatGPT's URL structure and accessible DOM links.
- ChatGPT UI changes may break link discovery or scrolling.
- Automated tests do not require a real ChatGPT account; live collection should be validated manually with `chat-dir --headed --debug`.
- If no sidebar/list links are loaded in the current UI state, no chats may be found.

## Before publishing to GitHub

Review `.gitignore`, confirm no browser profile or screenshots are staged, run tests, and avoid committing credentials or session data.
