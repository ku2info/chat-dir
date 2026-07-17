from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from chat_dir.browser import user_data_dir
from chat_dir.errors import NoChatsFoundError, NotLoggedInError, TimeoutError
from chat_dir.models import ChatLink
from chat_dir.providers.base import ChatProvider

CHATGPT_URL = "https://chatgpt.com/"
CHAT_RE = re.compile(r"^/c/([^/?#]+)")


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
    chat_id = match.group(1)
    normalized = urlunparse(("https", "chatgpt.com", f"/c/{chat_id}", "", "", ""))
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
                    str(user_data_dir()), headless=not self.headed, viewport={"width": 1280, "height": 900}
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
            context = pw.chromium.launch_persistent_context(str(user_data_dir()), headless=False)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=self.timeout_ms)
            print("Log in to ChatGPT in the opened browser. Close the browser window when finished.")
            page.wait_for_event("close", timeout=0)
            context.close()

    def _check_login(self, page: Any) -> None:
        if re.search(r"/(auth|login|signin)", page.url):
            raise NotLoggedInError("ChatGPT appears to require login.")

    def _extract(self, page: Any) -> list[ChatLink]:
        payload = page.eval_on_selector_all(
            'a[href*="/c/"]',
            """els => els.map(a => ({href: a.getAttribute('href'), ariaLabel: a.getAttribute('aria-label'), title: a.getAttribute('title'), text: a.innerText || a.textContent || ''}))""",
        )
        return links_from_dom_payload(payload, page.url)

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
