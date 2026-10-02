#!/usr/bin/env python3
"""Fail if any committed Portal screenshot deviates from the capture profile.

Every manifest WebP must be exactly ``target_width`` wide and
``round(target_width * height / width)`` tall, derived from
``scripts/capture/capture-profile.json``. Every legacy Portal PNG still
referenced from ``docs/`` must match the profile's raw pixel size. Provenance
records must point at real assets whose bytes still match.

Known historical violations live in ``scripts/capture/dimension-exceptions.yaml``
until they are recaptured; each one must carry a reason and a tracking issue, and
an exception for an asset that already conforms is itself an error so the list
can only shrink.

Usage:
    python3 scripts/validate_capture_assets.py
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"
CAPTURE = ROOT / "scripts" / "capture"


def png_size(data: bytes) -> tuple[int, int]:
    """Read width and height from a PNG IHDR chunk.

    >>> png_size(b"\\x89PNG\\r\\n\\x1a\\n" + b"\\x00\\x00\\x00\\rIHDR" + struct.pack(">II", 1600, 1000))
    (1600, 1000)
    """
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", data[16:24])


def webp_size(data: bytes) -> tuple[int, int]:
    """Read width and height from a lossy, lossless, or extended WebP.

    >>> vp8x = b"RIFF\\x00\\x00\\x00\\x00WEBPVP8X" + b"\\x00" * 8 + (1439).to_bytes(3, "little") + (899).to_bytes(3, "little")
    >>> webp_size(vp8x)
    (1440, 900)
    >>> lossy = b"RIFF\\x00\\x00\\x00\\x00WEBPVP8 " + b"\\x00" * 10 + struct.pack("<HH", 1440, 900)
    >>> webp_size(lossy)
    (1440, 900)
    >>> bits = (1440 - 1) | ((900 - 1) << 14)
    >>> lossless = b"RIFF\\x00\\x00\\x00\\x00WEBPVP8L" + b"\\x00" * 4 + b"\\x2f" + struct.pack("<I", bits)
    >>> webp_size(lossless)
    (1440, 900)
    """
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP")
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 ":
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L":
        bits = struct.unpack("<I", data[21:25])[0]
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ValueError(f"unsupported WebP chunk {chunk!r}")


def expected_sizes(profile: dict, target_width: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return (raw PNG size, final WebP size) implied by the profile.

    >>> p = {"capture": {"expectedPixelWidth": 1600, "expectedPixelHeight": 1000}}
    >>> expected_sizes(p, 1440)
    ((1600, 1000), (1440, 900))
    """
    raw_w = profile["capture"]["expectedPixelWidth"]
    raw_h = profile["capture"]["expectedPixelHeight"]
    return (raw_w, raw_h), (target_width, round(target_width * raw_h / raw_w))


def referenced_legacy_pngs() -> list[Path]:
    """Legacy PNGs under docs/assets that some Markdown page still references."""
    text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "docs").rglob("*.md"))
    return [p for p in sorted(ASSETS.rglob("*.png")) if p.name in text]


def problems() -> list[str]:
    profile_bytes = (CAPTURE / "capture-profile.json").read_bytes()
    profile = json.loads(profile_bytes)
    profile_sha = hashlib.sha256(profile_bytes).hexdigest()
    manifest = yaml.safe_load((CAPTURE / "manifest.yaml").read_text(encoding="utf-8"))
    exceptions = yaml.safe_load((CAPTURE / "dimension-exceptions.yaml").read_text(encoding="utf-8"))
    provenance = yaml.safe_load((CAPTURE / "provenance.yaml").read_text(encoding="utf-8"))

    raw_size, final_size = expected_sizes(profile, manifest["meta"]["target_width"])
    allowed = {e["asset"]: e for e in (exceptions.get("exceptions") or [])}
    found: list[str] = []
    measured: dict[str, tuple[int, int]] = {}

    for entry in manifest.get("shots") or manifest.get("screenshots") or []:
        rel = entry["file"]
        path = ASSETS / rel
        if not path.exists():
            found.append(f"{rel}: manifest entry {entry['id']} has no file")
            continue
        measured[rel] = webp_size(path.read_bytes())
    for path in referenced_legacy_pngs():
        measured[str(path.relative_to(ASSETS))] = png_size(path.read_bytes())

    for rel, size in sorted(measured.items()):
        want = final_size if rel.endswith(".webp") else raw_size
        exception = allowed.get(rel)
        if size == want:
            if exception:
                found.append(f"{rel}: conforms now, remove its dimension exception")
            continue
        if not exception:
            found.append(f"{rel}: {size[0]}x{size[1]}, expected {want[0]}x{want[1]} ({profile['id']})")
            continue
        if not exception.get("reason") or not exception.get("issue"):
            found.append(f"{rel}: dimension exception needs a reason and an issue")
        if tuple(exception.get("observed", ())) != size:
            found.append(f"{rel}: exception records {exception.get('observed')}, file is now {list(size)}")

    for rel in sorted(set(allowed) - set(measured)):
        found.append(f"{rel}: dimension exception for an asset that is not checked")

    for key, record in (provenance.get("assets") or {}).items():
        produced = record.get("produced", {})
        path = ASSETS / record.get("file", "")
        if not path.is_file():
            found.append(f"provenance {key}: {record.get('file')} does not exist")
            continue
        if produced.get("profile") == profile["id"] and produced.get("profile_sha256") != profile_sha:
            found.append(f"provenance {key}: recorded profile hash does not match {profile['id']}")
        if record.get("final_sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            found.append(f"provenance {key}: asset bytes changed since provenance was recorded")
    return found


def main() -> int:
    found = problems()
    if found:
        print("Capture asset check failed:")
        for item in found:
            print(f"  - {item}")
        return 1
    print("Capture assets conform to the capture profile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
