from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from chat_dir.models import ChatLink

RESPONSE_DATETIME_RE = re.compile(
    r"(?m)^response_datetime:\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2}))\s*$"
)
TOKYO = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class CsvChatRow:
    url: str
    response_datetime: datetime | None

    @property
    def formatted_datetime(self) -> str:
        if self.response_datetime is None:
            return ""
        return self.response_datetime.astimezone(TOKYO).strftime("%Y%m%d%H%M")


@dataclass(frozen=True)
class CsvBuildResult:
    rows: list[CsvChatRow]
    undated_count: int


def parse_response_datetime(value: str) -> datetime | None:
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def extract_response_datetimes(text: str) -> list[datetime]:
    datetimes: list[datetime] = []
    for match in RESPONSE_DATETIME_RE.finditer(text):
        parsed = parse_response_datetime(match.group(1))
        if parsed is not None:
            datetimes.append(parsed)
    return datetimes


def latest_response_datetime(text: str) -> datetime | None:
    datetimes = extract_response_datetimes(text)
    return max(datetimes) if datetimes else None


def build_csv_rows(chats: list[ChatLink], latest_by_url: dict[str, datetime | None], include_undated: bool = False) -> CsvBuildResult:
    rows: list[CsvChatRow] = []
    undated = 0
    for chat in chats:
        latest = latest_by_url.get(chat.url)
        if latest is None:
            undated += 1
            if not include_undated:
                continue
        rows.append(CsvChatRow(url=chat.url, response_datetime=latest))
    rows.sort(key=lambda row: (row.response_datetime is None, row.response_datetime or datetime.max.replace(tzinfo=TOKYO), row.url))
    return CsvBuildResult(rows=rows, undated_count=undated)


def format_csv_rows(rows: list[CsvChatRow]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    for row in rows:
        writer.writerow([row.formatted_datetime, row.url])
    return buffer.getvalue()


def collect_latest_by_url(chats: list[ChatLink], loader) -> tuple[dict[str, datetime | None], int]:
    latest_by_url: dict[str, datetime | None] = {}
    errors = 0
    for chat in chats:
        try:
            latest_by_url[chat.url] = loader(chat)
        except Exception:
            errors += 1
    return latest_by_url, errors
