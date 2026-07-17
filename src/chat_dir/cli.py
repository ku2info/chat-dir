from __future__ import annotations

import argparse
import sys
from chat_dir.errors import ChatDirError
from chat_dir.output import render, write_output
from chat_dir.providers.chatgpt import ChatGptProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chat-dir", description="List ChatGPT chat titles and URLs.")
    parser.add_argument("command", nargs="?", choices=["login"], help="Open a persistent browser for manual ChatGPT login.")
    parser.add_argument("--json", action="store_true", help="Print a JSON array.")
    parser.add_argument("--urls-only", action="store_true", help="Print one URL per line.")
    parser.add_argument("--output", help="Write output to a UTF-8 file.")
    parser.add_argument("--headed", action="store_true", help="Show the browser while collecting.")
    parser.add_argument("--debug", action="store_true", help="Write debug logs to stderr.")
    parser.add_argument("--max-scrolls", type=int, default=60, help="Maximum list scroll attempts.")
    parser.add_argument("--timeout-ms", type=int, default=60_000, help="Overall browser timeout in milliseconds.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    provider = ChatGptProvider(headed=args.headed, debug=args.debug, max_scrolls=args.max_scrolls, timeout_ms=args.timeout_ms)
    try:
        if args.command == "login":
            provider.login()
            return 0
        chats = provider.collect()
        content = render(chats, json_mode=args.json, urls_only=args.urls_only)
        if args.output:
            write_output(args.output, content)
        else:
            sys.stdout.write(content)
        return 0
    except ChatDirError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(f"hint: {exc.hint}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        print("hint: Check Playwright installation and run `chat-dir login` if needed.", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
