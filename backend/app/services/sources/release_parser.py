from __future__ import annotations

import re

from app.schemas.sources import ReleaseCharacteristics

MAX_SEASON_NUMBER = 100


def _matches(title: str, *patterns: str) -> bool:
    return any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in patterns)


def parse_release_seasons(title: str) -> list[int]:
    range_patterns = (
        r"(?:^|[^a-z0-9])s(\d{1,2})e\d{1,3}\s*[-–—]\s*s(\d{1,2})e\d{1,3}(?:[^a-z0-9]|$)",
        r"(?:^|[^a-z0-9])s(\d{1,2})\s*[-–—]\s*s?(\d{1,2})e\d{1,3}\s*[-–—]\s*\d{1,3}(?:[^a-z0-9]|$)",
        r"(?:^|[^a-z0-9])s(\d{1,2})\s*[-–—]\s*s?(\d{1,2})(?:[^a-z0-9]|$)",
        r"(?:seasons?|сезоны?)\s*(\d{1,2})\s*[-–—]\s*(\d{1,2})",
        r"(?:^|[^0-9])(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*(?:seasons?|сезоны?)(?:[^a-zа-яё0-9]|$)",
    )
    for pattern in range_patterns:
        match = re.search(pattern, title, flags=re.IGNORECASE)
        if match:
            first, last = sorted((int(match.group(1)), int(match.group(2))))
            if first >= 1 and last <= MAX_SEASON_NUMBER:
                return list(range(first, last + 1))

    season_markers = {
        int(value)
        for value in re.findall(r"(?:^|[^a-z0-9])s(\d{1,2})(?:e\d{1,3})?", title, re.IGNORECASE)
    }
    word_markers = {
        int(value)
        for match in re.findall(
            r"(?:seasons?|сезоны?)\s*(\d{1,2})|(?:^|[^0-9])(\d{1,2})\s*(?:season|сезон)",
            title,
            re.IGNORECASE,
        )
        for value in match
        if value
    }
    return sorted(
        number
        for number in season_markers | word_markers
        if 1 <= number <= MAX_SEASON_NUMBER
    )


def parse_release_title(title: str) -> ReleaseCharacteristics:
    resolution: str | None = None
    if _matches(title, r"\b(?:2160p|4k|uhd)\b"):
        resolution = "2160p"
    elif _matches(title, r"\b1080[pi]\b"):
        resolution = "1080p"
    elif _matches(title, r"\b720p\b"):
        resolution = "720p"
    elif _matches(title, r"\b(?:576|480)[pi]\b"):
        resolution = "480p"

    source: str | None = None
    if _matches(title, r"\bweb[ ._-]?dl\b"):
        source = "WEB-DL"
    elif _matches(title, r"\bweb[ ._-]?rip\b"):
        source = "WEBRip"
    elif _matches(title, r"\b(?:blu[ ._-]?ray|bdrip|brrip)\b"):
        source = "BluRay"
    elif _matches(title, r"\bhdtv\b"):
        source = "HDTV"
    elif _matches(title, r"\bdvd[ ._-]?rip\b"):
        source = "DVDRip"
    elif _matches(title, r"\b(?:camrip|hdcam|cam|telesync|ts)\b"):
        source = "CAM"

    codec: str | None = None
    if _matches(title, r"\b(?:h[ ._-]?265|x265|hevc)\b"):
        codec = "HEVC"
    elif _matches(title, r"\b(?:h[ ._-]?264|x264|avc)\b"):
        codec = "H264"
    elif _matches(title, r"\bav1\b"):
        codec = "AV1"
    elif _matches(title, r"\bxvid\b"):
        codec = "XviD"

    hdr_format: str | None = None
    if _matches(title, r"\b(?:dolby[ ._-]?vision|dovi|dv)\b"):
        hdr_format = "Dolby Vision"
    elif _matches(title, r"\bhdr10\+(?=$|[ ._-])"):
        hdr_format = "HDR10+"
    elif _matches(title, r"\bhdr10\b"):
        hdr_format = "HDR10"
    elif _matches(title, r"\bhlg\b"):
        hdr_format = "HLG"
    elif _matches(title, r"\bhdr\b"):
        hdr_format = "HDR"

    audio: str | None = None
    if _matches(title, r"\btruehd(?:[ ._-]?atmos)?\b"):
        audio = "TrueHD Atmos" if _matches(title, r"\batmos\b") else "TrueHD"
    elif _matches(title, r"\bdts[ ._-]?hd(?:[ ._-]?ma)?\b"):
        audio = "DTS-HD MA"
    elif _matches(title, r"\bdts[ ._-]?x\b"):
        audio = "DTS:X"
    elif _matches(title, r"\b(?:eac3|e-ac-3|ddp)\b"):
        audio = "E-AC-3"
    elif _matches(title, r"\b(?:ac3|ac-3|dd)\b"):
        audio = "AC-3"
    elif _matches(title, r"\baac\b"):
        audio = "AAC"
    elif _matches(title, r"\bflac\b"):
        audio = "FLAC"

    language: str | None = None
    if _matches(title, r"\bmulti\b"):
        language = "MULTI"
    elif _matches(title, r"\b(?:rus|russian|ru)\b"):
        language = "RU"
    elif _matches(title, r"\b(?:ukr|ukrainian|ua)\b"):
        language = "UK"
    elif _matches(title, r"\b(?:eng|english|en)\b"):
        language = "EN"

    release_type: str | None = None
    if _matches(title, r"\bremux\b"):
        release_type = "REMUX"
    elif source == "BluRay":
        release_type = "encode"
    elif source in {"WEB-DL", "WEBRip"}:
        release_type = "web"
    elif source == "CAM":
        release_type = "cam"

    return ReleaseCharacteristics(
        resolution=resolution,
        source=source,
        codec=codec,
        hdr=hdr_format is not None,
        hdr_format=hdr_format,
        audio=audio,
        language=language,
        release_type=release_type,
    )
