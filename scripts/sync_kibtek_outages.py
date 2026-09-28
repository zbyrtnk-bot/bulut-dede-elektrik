"""Build the public outage JSON from KIB-TEK's official Meta posts.

Run only with approved Meta Graph API access. No credentials are written to disk.
An unavailable source fails the run and leaves the previously published file alone.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "kesintiler.json"
NICOSIA = ZoneInfo("Asia/Nicosia")
MONTHS = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6,
    "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
}
MONTH_PATTERN = "|".join(MONTHS)
DATE_PATTERN = re.compile(rf"\b(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\b", re.I)
NUMERIC_DATE_PATTERN = re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b")
TIME_RANGE = re.compile(r"\b(\d{1,2})[:.](\d{2})\s*(?:ile|[-–])\s*(\d{1,2})[:.](\d{2})\s+saatleri?\s+arasında", re.I)
START_TIME = re.compile(r"\bsaat\s+(\d{1,2})[:.](\d{2})(?:'?[dt][ae]n)?", re.I)
AREA = re.compile(r"saatleri?\s+arasında\s*[;:,]\s*(.*?)\s+(?:elektrik\s+enerjisi|enerji)\s+verilemeyecektir", re.I | re.S)
FAULT_AREA = re.compile(r"(?:etkilenen|kalan)\s+(?:bölgeler|yerler|bölge)\s*[:;]\s*(.+?)(?:\.|$)", re.I | re.S)


def graph_get(path, params, token):
    url = "https://graph.facebook.com/v25.0/" + path.lstrip("/")
    url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(request, timeout=25) as response:
        data = json.load(response)
    if not isinstance(data, dict) or "error" in data:
        raise RuntimeError("Meta returned an invalid response")
    return data


def parse_date(text):
    match = DATE_PATTERN.search(text)
    if match:
        day, month, year = match.groups()
        return datetime(int(year), MONTHS[month.lower()], int(day), tzinfo=NICOSIA)
    match = NUMERIC_DATE_PATTERN.search(text)
    if match:
        day, month, year = map(int, match.groups())
        return datetime(year, month, day, tzinfo=NICOSIA)
    return None


def hour_minute(hour, minute):
    hour, minute = int(hour), int(minute)
    if hour > 23 or minute > 59:
        raise ValueError("Invalid time")
    return hour, minute


def clean(value):
    return re.sub(r"\s+", " ", value).strip(" \n\t;:,.-")


def parse_post(post, now=None, facebook_page_id=None):
    """Only convert notices with explicit status, date, time and area.

    Scheduled times are estimates, never proof that service actually stopped or returned.
    """
    now = now or datetime.now(timezone.utc)
    message = post.get("message") or post.get("caption") or ""
    if not isinstance(message, str) or not re.search(r"\bkesinti(?:si)?\b", message, re.I):
        return None
    if re.search(r"\b(?:iptal\s+edildi|iptal\s+oldu|kesinti\s+iptal)\b", message, re.I):
        return None
    heading = message[:100].upper()
    if "PLANLI KESİNTİ" in heading or "PLANLI ELEKTRİK KESİNTİSİ" in heading:
        status = "planned"
    elif "ARIZALI KESİNTİ" in heading or "ARIZA KAYNAKLI KESİNTİ" in heading:
        status = "active"
    else:
        return None
    try:
        day = parse_date(message)
        if day is None:
            return None
        range_match = TIME_RANGE.search(message)
        if range_match:
            sh, sm = hour_minute(*range_match.groups()[:2])
            eh, em = hour_minute(*range_match.groups()[2:])
            start = day.replace(hour=sh, minute=sm)
            end = day.replace(hour=eh, minute=em)
            if end <= start:
                end += timedelta(days=1)
        else:
            start_match = START_TIME.search(message)
            if not start_match or status != "active":
                return None
            sh, sm = hour_minute(*start_match.groups())
            start = day.replace(hour=sh, minute=sm)
            end = None
        area_match = AREA.search(message) or FAULT_AREA.search(message)
        if not area_match:
            return None
        area = clean(area_match.group(1))
        if not 3 <= len(area) <= 500:
            return None
        reason_match = re.search(r"(?:günü|şebekesinde|bölgesinde)\s+(.{5,180}?)\s+nedeniyle", message, re.I | re.S)
        reason = clean(reason_match.group(1)) if reason_match else "KIB-TEK duyurusunda belirtilmedi"
        if reason.startswith("saat ") or "elektrik enerjisi" in reason.lower():
            reason = "KIB-TEK duyurusunda belirtilmedi"
        published = datetime.fromisoformat(post.get("created_time", post.get("timestamp", "")).replace("Z", "+00:00"))
        if published.tzinfo is None:
            return None
        if published > now + timedelta(minutes=5) or published < now - timedelta(days=7):
            return None
        expires = (end + timedelta(hours=1)) if status == "planned" else (published + timedelta(hours=12))
        if start > now + timedelta(days=7) or expires <= now or (status == "active" and start > now):
            return None
        source = post.get("permalink_url") or post.get("permalink") or ""
        parsed = urllib.parse.urlparse(source)
        facebook_path = parsed.path.lower()
        facebook_allowed = facebook_path.startswith("/elektrikkurumu/") or (facebook_page_id and facebook_path.startswith("/" + facebook_page_id + "/posts/"))
        allowed = (parsed.hostname in ("facebook.com", "www.facebook.com") and facebook_allowed) or (parsed.hostname in ("instagram.com", "www.instagram.com") and parsed.path.startswith(("/p/", "/reel/")))
        if parsed.scheme != "https" or not allowed:
            return None
        return {
            "status": status, "area": area, "reason": reason,
            "startsAt": start.isoformat(),
            "estimatedEndAt": end.isoformat() if end else None,
            "updatedAt": published.isoformat(), "expiresAt": expires.isoformat(),
            "sourceUrl": source,
        }
    except (ValueError, TypeError, OverflowError):
        return None


def collect():
    token = os.environ["META_FACEBOOK_TOKEN"]
    page_id = os.environ["KIBTEK_FACEBOOK_PAGE_ID"]
    response = graph_get(page_id + "/posts", {
        "fields": "message,created_time,permalink_url", "limit": "50",
    }, token)
    posts = response.get("data")
    if not isinstance(posts, list):
        raise RuntimeError("Facebook posts are unavailable")
    instagram_user = os.environ.get("KIBTEK_INSTAGRAM_USERNAME", "").strip().lstrip("@")
    if instagram_user:
        ig_id = os.environ["OWN_INSTAGRAM_BUSINESS_ID"]
        ig_token = os.environ["META_INSTAGRAM_TOKEN"]
        fields = "business_discovery.username(" + instagram_user + "){media.limit(50){caption,timestamp,permalink}}"
        ig = graph_get(ig_id, {"fields": fields}, ig_token)
        media = ig.get("business_discovery", {}).get("media", {}).get("data")
        if not isinstance(media, list):
            raise RuntimeError("Instagram posts are unavailable")
        posts += media
    return posts


def main():
    now = datetime.now(timezone.utc)
    posts = collect()  # Failure keeps the existing JSON untouched.
    page_id = os.environ["KIBTEK_FACEBOOK_PAGE_ID"]
    notices = [notice for post in posts if (notice := parse_post(post, now, page_id))]
    notices = list({notice["sourceUrl"]: notice for notice in notices}.values())
    notices.sort(key=lambda notice: notice["startsAt"])
    payload = {"checkedAt": now.isoformat(), "notices": notices}
    temp = OUTPUT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(OUTPUT)
    print(f"Checked {len(posts)} posts; published {len(notices)} complete notices")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, RuntimeError, urllib.error.URLError) as exc:
        print(f"Outage sync failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
