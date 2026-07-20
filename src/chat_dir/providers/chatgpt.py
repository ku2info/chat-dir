from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from chat_dir.browser import user_data_dir
from chat_dir.csv_output import ChatCsvRow, latest_response_datetime
from chat_dir.errors import NoChatsFoundError, NotLoggedInError, TimeoutError
from chat_dir.models import ChatLink
from chat_dir.providers.base import ChatProvider

CHATGPT_URL = "https://chatgpt.com/"
CHAT_RE = re.compile(r"^(?:/g/([^/?#]+))?/c/([^/?#]+)")


def normalize_title(value: str | None) -> str | None:
    if not value:
        return None
    normalized = " ".join(value.split())
    return normalized or None


def normalize_chat_url(href: str | None, base_url: str = CHATGPT_URL) -> tuple[str, str] | None:
    if not href:
        return None
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.netloc not in {"chatgpt.com", "www.chatgpt.com"}:
        return None
    match = CHAT_RE.match(parsed.path)
    if not match:
        return None
    project_id = match.group(1)
    chat_id = match.group(2)
    path = f"/g/{project_id}/c/{chat_id}" if project_id else f"/c/{chat_id}"
    normalized = urlunparse(("https", "chatgpt.com", path, "", "", ""))
    return normalized, chat_id


def dedupe_chats(items: list[ChatLink]) -> list[ChatLink]:
    seen: set[str] = set()
    result: list[ChatLink] = []
    for item in items:
        if item.url in seen:
            continue
        seen.add(item.url)
        result.append(item)
    return result


def links_from_dom_payload(payload: list[dict[str, Any]], base_url: str = CHATGPT_URL) -> list[ChatLink]:
    chats: list[ChatLink] = []
    for row in payload:
        normalized = normalize_chat_url(row.get("href"), base_url)
        if not normalized:
            continue
        url, chat_id = normalized
        title = normalize_title(row.get("ariaLabel") or row.get("title") or row.get("text"))
        chats.append(ChatLink(url=url, chat_id=chat_id, title=title))
    return dedupe_chats(chats)


@dataclass
class ChatGptProvider(ChatProvider):
    headed: bool = False
    debug: bool = False
    max_scrolls: int = 60
    stable_rounds: int = 4
    timeout_ms: int = 60_000
    browser_channel: str | None = None

    def _launch_options(self, *, headless: bool) -> dict[str, Any]:
        options: dict[str, Any] = {"headless": headless}
        if self.browser_channel:
            options["channel"] = self.browser_channel
        return options

    def collect(self) -> list[ChatLink]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is not installed. Run: pip install -e . && playwright install chromium") from exc

        start = time.monotonic()
        try:
            with sync_playwright() as pw:
                context = pw.chromium.launch_persistent_context(
                    str(user_data_dir()),
                    **self._launch_options(headless=not self.headed),
                    viewport={"width": 1280, "height": 900},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
                page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 15_000))
                self._check_login(page)
                chats = self._scroll_and_collect(page, start)
                context.close()
        except PlaywrightTimeoutError as exc:
            raise TimeoutError("Timed out while loading or scanning ChatGPT.") from exc
        if not chats:
            raise NoChatsFoundError("No ChatGPT chat links were found in the current page.")
        return chats

    def login(self) -> None:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                str(user_data_dir()),
                **self._launch_options(headless=False),
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
            print("Log in to ChatGPT in the opened browser. Close the browser window when finished.")
            page.wait_for_event("close", timeout=0)
            context.close()

    def collect_csv_rows(self, include_undated: bool = False) -> tuple[list[ChatCsvRow], dict[str, int]]:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is not installed. Run: pip install -e . && playwright install chromium") from exc

        stats = {"detected": 0, "written": 0, "undated": 0, "errors": 0}
        rows: list[ChatCsvRow] = []
        start = time.monotonic()
        try:
            with sync_playwright() as pw:
                context = pw.chromium.launch_persistent_context(
                    str(user_data_dir()),
                    **self._launch_options(headless=not self.headed),
                    viewport={"width": 1280, "height": 900},
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
                page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 15_000))
                self._check_login(page)
                chats = self._scroll_and_collect(page, start)
                stats["detected"] = len(chats)
                for index, chat in enumerate(chats, 1):
                    print(f"[{index}/{len(chats)}] Scanning {chat.url}", file=__import__("sys").stderr)
                    try:
                        latest = self._scan_chat_response_datetime(page, chat.url)
                    except Exception:
                        stats["errors"] += 1
                        print(f"[ERROR] Failed to load chat: {chat.url}", file=__import__("sys").stderr)
                        continue
                    if latest is None:
                        stats["undated"] += 1
                        print(f"[SKIP] response_datetime not found: {chat.url}", file=__import__("sys").stderr)
                        if not include_undated:
                            continue
                    rows.append(ChatCsvRow(url=chat.url, latest_datetime=latest))
                context.close()
        except PlaywrightTimeoutError as exc:
            raise TimeoutError("Timed out while loading or scanning ChatGPT.") from exc
        stats["written"] = len(rows)
        return rows, stats

    def _check_login(self, page: Any) -> None:
        if re.search(r"/(auth|login|signin)", page.url):
            raise NotLoggedInError("ChatGPT appears to require login.")

    def _extract(self, page: Any) -> list[ChatLink]:
        payload = page.eval_on_selector_all(
            'a[href*="/c/"]',
            """els => els.map(a => ({href: a.getAttribute('href'), ariaLabel: a.getAttribute('aria-label'), title: a.getAttribute('title'), text: a.innerText || a.textContent || ''}))""",
        )
        return links_from_dom_payload(payload, page.url)

    def _scan_chat_response_datetime(self, page: Any, url: str) -> Any:
        page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 15_000))
        self._scroll_chat_to_bottom(page)
        assistant_texts = page.eval_on_selector_all(
            '[data-message-author-role="assistant"], article, [role="article"]',
            "els => els.map(el => el.innerText || el.textContent || '').filter(Boolean)",
        )
        latest = latest_response_datetime(assistant_texts)
        if latest is not None:
            return latest
        body_text = page.locator("body").inner_text(timeout=min(self.timeout_ms, 15_000))
        return latest_response_datetime([body_text])

    def _scroll_chat_to_bottom(self, page: Any) -> None:
        last_height = -1
        stable = 0
        for _ in range(12):
            height = page.evaluate("""() => {
                const el = document.scrollingElement || document.documentElement;
                el.scrollTop = el.scrollHeight;
                return el.scrollHeight;
            }""")
            stable = stable + 1 if height == last_height else 0
            if stable >= 2:
                break
            last_height = height
            page.wait_for_timeout(700)

    def _scroll_and_collect(self, page: Any, start: float) -> list[ChatLink]:
        known: list[ChatLink] = []
        stable = 0
        for scroll in range(self.max_scrolls + 1):
            if (time.monotonic() - start) * 1000 > self.timeout_ms:
                raise TimeoutError("Timed out while scrolling ChatGPT chat list.")
            before = len(known)
            known = dedupe_chats(known + self._extract(page))
            added = len(known) - before
            if self.debug:
                print(f"debug: url={page.url} links={len(known)} scroll={scroll} added={added}", file=__import__('sys').stderr)
            stable = stable + 1 if added == 0 else 0
            if stable >= self.stable_rounds:
                if self.debug:
                    print(f"debug: stop=stable_rounds({self.stable_rounds})", file=__import__('sys').stderr)
                break
            page.evaluate("""() => {
                const candidates = [document.scrollingElement, ...document.querySelectorAll('[role="navigation"], nav, aside, main, [style*="overflow"]')].filter(Boolean);
                let best = candidates[0];
                for (const el of candidates) if (el.scrollHeight - el.clientHeight > (best.scrollHeight - best.clientHeight)) best = el;
                best.scrollTop = best.scrollHeight;
            }""")
            page.wait_for_timeout(800)
        return known
