from dataclasses import dataclass

from app.services.streaming.exceptions import StreamRangeError


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int
    total: int
    partial: bool

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_byte_range(header: str | None, total_size: int) -> ByteRange:
    if total_size <= 0:
        raise StreamRangeError(total_size)
    if header is None:
        return ByteRange(start=0, end=total_size - 1, total=total_size, partial=False)
    if not header.startswith("bytes=") or "," in header:
        raise StreamRangeError(total_size)
    value = header.removeprefix("bytes=").strip()
    if "-" not in value:
        raise StreamRangeError(total_size)
    start_text, end_text = value.split("-", 1)
    try:
        if not start_text:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise StreamRangeError(total_size)
            start = max(total_size - suffix_length, 0)
            end = total_size - 1
        else:
            start = int(start_text)
            end = total_size - 1 if not end_text else int(end_text)
    except ValueError as exc:
        raise StreamRangeError(total_size) from exc
    if start < 0 or start >= total_size or end < start:
        raise StreamRangeError(total_size)
    return ByteRange(
        start=start,
        end=min(end, total_size - 1),
        total=total_size,
        partial=True,
    )
