"""Bounded ISO-BMFF metadata validation for administrator-uploaded MP4/H.264.

This validates container structure and codec metadata, not every decoded frame.
No remote fetching, external processes, or client filenames are used.
"""
import struct
import uuid

from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError

from cms.models import BannerVideo

MAX_BYTES = 30 * 1024 * 1024


def boxes(data, start=0, end=None):
    end = len(data) if end is None else end
    count = 0
    while start < end:
        count += 1
        if count > 10000 or end - start < 8:
            raise ValueError("Invalid MP4 boxes")
        size, kind = struct.unpack_from(">I4s", data, start)
        header = 8
        if size == 1:
            if end - start < 16:
                raise ValueError("Invalid extended box")
            size = struct.unpack_from(">Q", data, start + 8)[0]
            header = 16
        elif size == 0:
            size = end - start
        if size < header or start + size > end:
            raise ValueError("Invalid box length")
        yield kind, start + header, start + size
        start += size


def only(data, entries, name):
    matches = [(start, end) for kind, start, end in entries if kind == name]
    if len(matches) != 1:
        raise ValueError("Missing or duplicate MP4 box")
    start, end = matches[0]
    return data[start:end]


def inspect_mp4(data):
    top = list(boxes(data))
    ftyp = only(data, top, b"ftyp")
    if len(ftyp) < 8 or not any(brand in {b"isom", b"iso2", b"mp41", b"mp42", b"avc1"} for brand in [ftyp[:4], *[ftyp[i:i+4] for i in range(8, len(ftyp), 4)]]):
        raise ValueError("Unsupported MP4 brand")
    if not any(kind == b"mdat" and end > start for kind, start, end in top):
        raise ValueError("Missing video data")
    moov = only(data, top, b"moov")
    entries = list(boxes(moov))
    mvhd = only(moov, entries, b"mvhd")
    version = mvhd[0]
    offset = 20 if version == 1 else 12
    if version not in {0, 1} or len(mvhd) < offset + (12 if version == 1 else 8):
        raise ValueError("Invalid movie header")
    scale = struct.unpack_from(">I", mvhd, offset)[0]
    duration = struct.unpack_from(">Q" if version == 1 else ">I", mvhd, offset+4)[0]
    if not scale or not 0 < duration / scale <= 90:
        raise ValueError("Video duration must be 1–90 seconds")
    videos = []
    for kind, start, end in entries:
        if kind != b"trak":
            continue
        track = moov[start:end]
        mdia = only(track, list(boxes(track)), b"mdia")
        media = list(boxes(mdia))
        handler = only(mdia, media, b"hdlr")
        if len(handler) < 12 or handler[8:12] not in {b"vide", b"soun"}:
            raise ValueError("Unsupported track")
        minf = only(mdia, media, b"minf")
        stbl = only(minf, list(boxes(minf)), b"stbl")
        stsd = only(stbl, list(boxes(stbl)), b"stsd")
        if len(stsd) < 8 or struct.unpack_from(">I", stsd, 4)[0] != 1:
            raise ValueError("Unsupported sample descriptions")
        samples = list(boxes(stsd, 8))
        if len(samples) != 1:
            raise ValueError("Invalid sample descriptions")
        codec, begin, finish = samples[0]
        sample = stsd[begin:finish]
        if handler[8:12] == b"soun":
            if codec != b"mp4a":
                raise ValueError("Audio must be AAC")
            continue
        if codec not in {b"avc1", b"avc3"} or len(sample) < 78:
            raise ValueError("Video must be H.264")
        width, height = struct.unpack_from(">HH", sample, 24)
        if not 0 < width <= 3840 or not 0 < height <= 2160:
            raise ValueError("Video resolution too large")
        avcc = only(sample, list(boxes(sample, 78)), b"avcC")
        if len(avcc) < 7 or avcc[0] != 1:
            raise ValueError("Invalid AVC configuration")
        videos.append((width, height))
    if len(videos) != 1:
        raise ValueError("Exactly one video track required")
    return (*videos[0], duration / scale)


def upload_video(actor, upload):
    if upload is None or not 0 < upload.size <= MAX_BYTES:
        raise ValidationError({"video": "ویدیوی MP4 حداکثر ۳۰ مگابایت انتخاب کنید."})
    data = upload.read(MAX_BYTES + 1)
    try:
        if len(data) > MAX_BYTES:
            raise ValueError("Too large")
        width, height, duration = inspect_mp4(data)
    except (ValueError, IndexError, struct.error) as exc:
        raise ValidationError({"video": "فایل MP4 معتبر با کدک H.264، حداکثر ۹۰ ثانیه و ابعاد ۳۸۴۰×۲۱۶۰ لازم است؛ صدای اختیاری AAC باشد."}) from exc
    asset = BannerVideo(width=width, height=height, duration=duration, size=len(data), uploaded_by=actor)
    try:
        asset.file.save(f"{uuid.uuid4().hex}.mp4", ContentFile(data), save=False)
        asset.save()
    except Exception:
        if asset.file.name:
            asset.file.delete(save=False)
        raise
    return asset
