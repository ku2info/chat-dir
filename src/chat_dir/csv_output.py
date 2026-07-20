from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

TOKYO = timezone(timedelta(hours=9), "Asia/Tokyo")
RESPONSE_DATETIME_RE = re.compile(
    r"(?m)^response_datetime:\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2}))\s*$"
)


@dataclass(frozen=True)
class ChatCsvRow:
    url: str
    latest_datetime: datetime | None


def parse_response_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def extract_response_datetimes(text: str) -> list[datetime]:
    values: list[datetime] = []
    for match in RESPONSE_DATETIME_RE.finditer(text):
        parsed = parse_response_datetime(match.group(1))
        if parsed is not None:
            values.append(parsed)
    return values


def latest_response_datetime(texts: list[str]) -> datetime | None:
    values: list[datetime] = []
    for text in texts:
        values.extend(extract_response_datetimes(text))
    if not values:
        return None
    return max(values)


def format_csv_datetime(value: datetime) -> str:
    return value.astimezone(TOKYO).strftime("%Y%m%d%H%M")


def sort_csv_rows(rows: list[ChatCsvRow]) -> list[ChatCsvRow]:
    return sorted(rows, key=lambda row: (row.latest_datetime is None, row.latest_datetime or datetime.max.replace(tzinfo=TOKYO), row.url))


def render_csv(rows: list[ChatCsvRow]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    for row in sort_csv_rows(rows):
        writer.writerow([format_csv_datetime(row.latest_datetime) if row.latest_datetime else "", row.url])
    return output.getvalue()
