"""Bounded retrieval of public MLB metadata and media inspection without bulk downloads."""

import html
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def validate_mlb_url(url):
    """Restrict this source adapter to HTTPS resources on MLB-owned hostnames."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or not (host == "mlb.com" or host.endswith(".mlb.com"))
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Expected an HTTPS mlb.com source URL")
    return url


def fetch_source(url, destination, limit_bytes=20_000_000):
    """Fetch a bounded metadata snapshot and preserve the exact source bytes."""
    validate_mlb_url(url)
    with urlopen(Request(url, headers={"User-Agent": "SmartPitch-P0/1.0"}), timeout=45) as response:
        validate_mlb_url(response.url)
        data = response.read(limit_bytes + 1)
    if len(data) > limit_bytes:
        raise ValueError("Metadata response exceeds size limit")
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def media_urls(page):
    """Extract observed public MP4 URLs; no inferred URL patterns or stream bypasses."""
    values = re.findall(r'https://[^\s<>"\\]+\.mp4(?:\?[^\s<>"\\]*)?', page)
    result = []
    for value in values:
        value = html.unescape(value)
        try:
            validate_mlb_url(value)
        except ValueError:
            continue
        if value not in result:
            result.append(value)
    return result


def probe_media(url):
    """Inspect a remote input through ffprobe; do not save the full video locally."""
    validate_mlb_url(url)
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,size:stream=codec_type,width,height,r_frame_rate",
                "-of",
                "json",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffprobe is required for --probe; install FFmpeg or omit --probe"
        ) from exc
    return {
        "url": url,
        "checked_at": datetime.now(UTC).isoformat(),
        "probe": json.loads(result.stdout),
        "full_video_downloaded": False,
    }
