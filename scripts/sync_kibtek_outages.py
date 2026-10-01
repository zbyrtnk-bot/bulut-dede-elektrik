"""Build the public outage JSON from KIB-TEK's official Meta posts.

Run only with approved Meta Graph API access. No credentials are written to disk.
An unavailable source fails the run and leaves the previously published file alone.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
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
DISTRICT_NAMES = {
    "LEFKOŞA": "Lefkoşa", "GİRNE": "Girne", "GAZİMAĞUSA": "Gazimağusa",
    "İSKELE": "İskele", "GÜZELYURT": "Güzelyurt", "LEFKE": "Lefke",
}
DATE_PATTERN = re.compile(rf"\b(\d{{1,2}})\s+({MONTH_PATTERN})(?:\s+(20\d{{2}}))?\b", re.I)
NUMERIC_DATE_PATTERN = re.compile(r"\b(\d{1,2})[./](\d{1,2})(?:[./](20\d{2}))?\b")
TIME_RANGE = re.compile(
    r"\b(\d{1,2})[:.](\d{2})\s*(?:ile|[-–])\s*(\d{1,2})[:.](\d{2})\s+saatleri?\s+arasında\b",
    re.I,
)
START_TIME = re.compile(r"\bsaat\s+(\d{1,2})[:.](\d{2})(?:'?[dt][ae]n)?", re.I)
AREA_END = re.compile(
    r"\b(?:elektrik(?:\s+enerjisi)?|enerji)\s+(?:kesintisi\s+yapılacaktır|kesinti\s+olacaktır|kesilecektir|kesilecek(?:tir)?|verilemeyecektir)\b",
    re.I,
)
AREA_INTRO = re.compile(r"^.{0,240}?\benerji\s+kesilerek\b\s*", re.I | re.S)


def graph_get(path, params, token):
    url = "https://graph.facebook.com/v25.0/" + path.lstrip("/")
    url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
    with urllib.request.urlopen(request, timeout=25) as response:
        data = json.load(response)
    if not isinstance(data, dict) or "error" in data:
        raise RuntimeError("Meta returned an invalid response")
    return data


def parse_date(text, reference=None):
    reference_year = reference.year if reference else datetime.now(NICOSIA).year
    match = DATE_PATTERN.search(text)
    if match:
        day, month, year = match.groups()
        month_number = MONTHS[month.lower()]
    else:
        match = NUMERIC_DATE_PATTERN.search(text)
        if not match:
            return None
        day, month, year = match.groups()
        month_number = int(month)
    day = int(day)
    if year:
        return datetime(int(year), month_number, day, tzinfo=NICOSIA)
    candidates = []
    for candidate_year in (reference_year - 1, reference_year, reference_year + 1):
        try:
            candidates.append(datetime(candidate_year, month_number, day, tzinfo=NICOSIA))
        except ValueError:
            pass
    if not candidates:
        return None
    reference_date = reference.astimezone(NICOSIA) if reference and reference.tzinfo else datetime(reference_year, 1, 1, tzinfo=NICOSIA)
    return min(candidates, key=lambda candidate: abs((candidate.date() - reference_date.date()).days))


def hour_minute(hour, minute):
    hour, minute = int(hour), int(minute)
    if hour > 23 or minute > 59:
        raise ValueError("Invalid time")
    return hour, minute


def clean(value):
    value = re.sub(r"\s+", " ", value)
    return value.strip(" \n\t;:,.-–—")


def get_published(post):
    value = post.get("created_time", post.get("timestamp", ""))
    if not value:
        return None
    published = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if published.tzinfo is None:
        return None
    return published


def parse_post(post, now=None, facebook_page_id=None):
    """Parse captions plus OCR text; never infer status from scheduled clock times."""
    now = now or datetime.now(timezone.utc)
    message = "\n".join(
        value for value in (post.get("message"), post.get("caption"), post.get("image_text"))
        if isinstance(value, str) and value.strip()
    )
    if not re.search(r"\bkesinti(?:si)?\b", message, re.I):
        return None
    if re.search(r"\b(?:iptal\s+edildi|iptal\s+oldu|kesinti\s+iptal)\b", message, re.I):
        return None
    heading = message[:180].upper()
    if re.search(r"PLANLI\s+(?:ELEKTRİK\s+)?KESİNTİ", heading):
        status = "planned"
    elif re.search(r"(?:ARIZALI|ARIZA\s+KAYNAKLI)\s+(?:ELEKTRİK\s+)?KESİNTİ", heading):
        status = "active"
    else:
        return None
    try:
        published = get_published(post)
        if not published or published > now + timedelta(minutes=5) or published < now - timedelta(days=7):
            return None
        day = parse_date(message, published)
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

        area_text = ""
        if range_match:
            after_time = message[range_match.end():]
            area_end = AREA_END.search(after_time)
            if area_end:
                area_text = after_time[:area_end.start()]
                area_text = AREA_INTRO.sub("", area_text)
        if not area_text:
            area_match = re.search(r"(?:etkilenen|kalan)\s+(?:bölgeler|yerler|bölge)\s*[:;]\s*(.+?)(?:\.|$)", message, re.I | re.S)
            if area_match:
                area_text = area_match.group(1)
        area = clean(area_text)
        if not 3 <= len(area) <= 650:
            return None

        reason_match = re.search(
            r"(?:günü|tarihinde)(?:\s*[,;:]\s*|\s+)(.{5,220}?)\s+(?:neden(?:i\s+ile|iyle|yle)|sebebi(?:\s+ile|yle))",
            message, re.I | re.S,
        )
        reason = clean(reason_match.group(1)) if reason_match else "KIB-TEK duyurusunda belirtilmedi"
        if reason.lower().startswith("saat ") or "enerji kesintisi" in reason.lower():
            reason = "KIB-TEK duyurusunda belirtilmedi"

        if start > now + timedelta(days=7):
            return None
        if status == "planned" and end:
            # Once the official estimate passes, show it as unconfirmed for a short
            # period; never turn a planned notice into a red active outage by inference.
            if end + timedelta(hours=6) <= now:
                return None
            if end <= now:
                status = "unconfirmed"
            expires = end + timedelta(hours=6)
        else:
            if status == "active" and start > now:
                return None
            expires = published + timedelta(hours=12)
            if expires <= now:
                return None

        district_match = re.search(r"([A-ZÇĞİÖŞÜ]{3,})\s+İLÇESİ", message[:200].upper())
        district = DISTRICT_NAMES.get(district_match.group(1), district_match.group(1)) if district_match else ""
        source = post.get("permalink_url") or post.get("permalink") or ""
        parsed = urllib.parse.urlparse(source)
        facebook_path = parsed.path.lower()
        facebook_allowed = facebook_path.startswith("/elektrikkurumu/") or (facebook_page_id and facebook_path.startswith("/" + facebook_page_id + "/posts/"))
        allowed = (parsed.hostname in ("facebook.com", "www.facebook.com") and facebook_allowed) or (parsed.hostname in ("instagram.com", "www.instagram.com") and parsed.path.startswith(("/p/", "/reel/")))
        if parsed.scheme != "https" or not allowed:
            return None
        return {
            "status": status,
            "district": district,
            "area": area,
            "reason": reason,
            "startsAt": start.isoformat(),
            "estimatedEndAt": end.isoformat() if end else None,
            "updatedAt": published.isoformat(),
            "expiresAt": expires.isoformat(),
            "sourceUrl": source,
        }
    except (ValueError, TypeError, OverflowError):
        return None


def image_url(post):
    candidates = [post.get("full_picture"), post.get("media_url")]
    attachments = (post.get("attachments") or {}).get("data", [])
    pending = list(attachments) if isinstance(attachments, list) else []
    while pending:
        attachment = pending.pop(0)
        media = attachment.get("media") or {}
        image = media.get("image") or {}
        candidates.extend((image.get("src"), media.get("source"), attachment.get("media_url")))
        children = (attachment.get("subattachments") or {}).get("data", [])
        if isinstance(children, list):
            pending.extend(children)
    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.startswith("https://"):
            continue
        host = urllib.parse.urlparse(candidate).hostname or ""
        if host.endswith(".fbcdn.net") or host.endswith(".facebook.com") or host.endswith(".cdninstagram.com"):
            return candidate
    return None


def ocr_image(url):
    """Read a KIB-TEK post image locally with Tesseract; do not keep downloaded media."""
    request = urllib.request.Request(url, headers={"User-Agent": "BulutDedeKibtekNoticeSync/1.0"})
    with urllib.request.urlopen(request, timeout=25) as response:
        content_type = response.headers.get_content_type()
        if not content_type.startswith("image/"):
            return ""
        image = response.read(6 * 1024 * 1024 + 1)
    if len(image) > 6 * 1024 * 1024:
        return ""
    with tempfile.NamedTemporaryFile(suffix=".img") as image_file:
        image_file.write(image)
        image_file.flush()
        result = subprocess.run(
            ["tesseract", image_file.name, "stdout", "-l", "tur+eng", "--psm", "6"],
            capture_output=True, text=True, timeout=35, check=False,
        )
    if result.returncode != 0:
        return ""
    return result.stdout


def collect():
    token = os.environ["META_FACEBOOK_TOKEN"]
    page_id = os.environ.get("KIBTEK_FACEBOOK_PAGE_ID", "").strip()
    if not page_id:
        page = graph_get("elektrikkurumu", {"fields": "id"}, token)
        page_id = str(page.get("id", ""))
    if not re.fullmatch(r"\d+", page_id):
        raise RuntimeError("KIB-TEK Facebook Page ID could not be resolved")
    response = graph_get(page_id + "/posts", {
        "fields": "message,created_time,permalink_url,full_picture,attachments{media,subattachments}", "limit": "30",
    }, token)
    posts = response.get("data")
    if not isinstance(posts, list):
        raise RuntimeError("Facebook posts are unavailable")

    instagram_user = os.environ.get("KIBTEK_INSTAGRAM_USERNAME", "").strip().lstrip("@")
    if instagram_user:
        ig_id = os.environ["OWN_INSTAGRAM_BUSINESS_ID"]
        ig_token = os.environ["META_INSTAGRAM_TOKEN"]
        fields = "business_discovery.username(" + instagram_user + "){media.limit(30){caption,timestamp,permalink,media_url}}"
        ig = graph_get(ig_id, {"fields": fields}, ig_token)
        media = ig.get("business_discovery", {}).get("media", {}).get("data")
        if not isinstance(media, list):
            raise RuntimeError("Instagram posts are unavailable")
        posts += media

    ocr_count = 0
    now = datetime.now(timezone.utc)
    for post in posts:
        message = post.get("message") or post.get("caption") or ""
        if ocr_count >= 20 or not image_url(post):
            continue
        if message.strip() and not re.search(r"kesinti|enerji\s+kes|kesilecek", message, re.I):
            continue
        if parse_post(post, now, page_id) is not None:
            continue
        try:
            post["image_text"] = ocr_image(image_url(post)) or ""
        except (urllib.error.URLError, TimeoutError, subprocess.TimeoutExpired):
            post["image_text"] = ""
        ocr_count += 1
    return posts, page_id


def main():
    now = datetime.now(timezone.utc)
    posts, page_id = collect()  # Failure keeps the existing JSON untouched.
    notices = [notice for post in posts if (notice := parse_post(post, now, page_id))]
    notices = list({notice["sourceUrl"]: notice for notice in notices}.values())
    notices.sort(key=lambda notice: notice["startsAt"])
    payload = {"checkedAt": now.isoformat(), "notices": notices}
    temp = OUTPUT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(OUTPUT)
    print(f"Checked {len(posts)} official posts; published {len(notices)} outage notices")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, RuntimeError, urllib.error.URLError, subprocess.TimeoutExpired) as exc:
        print(f"Outage sync failed: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)
