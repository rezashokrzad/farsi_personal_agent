# -*- coding: utf-8 -*-
"""Google Calendar agent — create and delete events via service account."""

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
CALENDAR_ID = os.getenv("CALENDAR_ID", "ai.dslanders@gmail.com")
SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT",
    r"C:\Users\rezas\Desktop\farsi_personal_agent\secrets\farsi-audio.json",
)


def _service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def create_event(
    title: str,
    start_iso: str,
    end_iso: Optional[str] = None,
    guests: Optional[list[str]] = None,
    description: str = "",
) -> str:
    """Create an event. Returns a Persian confirmation string."""
    if not end_iso:
        dt = datetime.fromisoformat(start_iso)
        end_iso = (dt + timedelta(hours=1)).isoformat()

    body = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_iso, "timeZone": "Asia/Tehran"},
        "end": {"dateTime": end_iso, "timeZone": "Asia/Tehran"},
    }
    if guests:
        body["attendees"] = [{"email": g.strip()} for g in guests if "@" in g]

    svc = _service()
    event = svc.events().insert(calendarId=CALENDAR_ID, body=body, sendUpdates="all").execute()
    link = event.get("htmlLink", "")
    return f"رویداد «{title}» با موفقیت در تقویم ثبت شد."


def delete_event(title_or_id: str, date_hint: Optional[str] = None) -> str:
    """Delete an event by title (searches upcoming events) or event id."""
    svc = _service()

    # Try direct event id first
    if re.match(r"^[a-z0-9_]+$", title_or_id):
        try:
            svc.events().delete(calendarId=CALENDAR_ID, eventId=title_or_id).execute()
            return f"رویداد با موفقیت حذف شد."
        except Exception:
            pass

    # Search by title in next 30 days
    now = datetime.now(timezone.utc).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    result = (
        svc.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            timeMax=future,
            q=title_or_id,
            maxResults=5,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    items = result.get("items", [])
    if not items:
        return f"رویدادی با عنوان «{title_or_id}» پیدا نشد."

    # Delete the first match
    event = items[0]
    svc.events().delete(calendarId=CALENDAR_ID, eventId=event["id"]).execute()
    title = event.get("summary", title_or_id)
    return f"رویداد «{title}» با موفقیت حذف شد."


def list_events(days: int = 7) -> str:
    """Return upcoming events as a Persian string."""
    svc = _service()
    now = datetime.now(timezone.utc).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    result = (
        svc.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            timeMax=future,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    items = result.get("items", [])
    if not items:
        return "رویدادی در تقویم یافت نشد."
    lines = []
    for e in items:
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        lines.append(f"• {e.get('summary','بدون عنوان')} — {start}")
    return "رویدادهای پیش‌رو:\n" + "\n".join(lines)
