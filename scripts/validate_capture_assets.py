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

Image metadata is checked too. Docs reference a manifest screenshot only through
``shot("id")``; a direct image path is allowed only for an entry of the frozen
legacy registry ``scripts/capture/legacy-assets.yaml`` and must use its canonical
alt. Every image file under ``docs/assets`` must be registered, and every
registered image must be referenced. With ``--base-ref``, an image reference
added or changed in the diff must be followed by ``Purpose:``, ``Look for:``, and
``Expected result:`` lines; existing gaps are reported as advisory only.

Usage:
    python3 scripts/validate_capture_assets.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
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


def git_show(ref: str, rel: str) -> bytes | None:
    """Return a file's bytes at ``ref``, or None when it does not exist there."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel}"], cwd=ROOT, capture_output=True, check=False
    )
    return result.stdout if result.returncode == 0 else None


def new_exceptions(current: list[dict], base: list[dict] | None) -> list[str]:
    """Exceptions present now that were absent at the base revision.

    The file may only shrink, so any addition is a violation. A base without
    the file is the bootstrap commit that introduces it, which is allowed.

    >>> new_exceptions([{"asset": "a"}, {"asset": "b"}], [{"asset": "a"}])
    ['b']
    >>> new_exceptions([{"asset": "a"}], None)
    []
    """
    if base is None:
        return []
    known = {e["asset"] for e in base}
    return sorted(e["asset"] for e in current if e["asset"] not in known)


def provenance_record_problems(key: str, record: dict, rel: str, profile_id: str, profile_sha: str) -> list[str]:
    """Validate one provenance record against the asset it describes.

    >>> ok = {"file": "x.webp", "final_sha256": "h",
    ...       "produced": {"profile": "p1", "profile_sha256": "s"}}
    >>> provenance_record_problems("k", ok, "x.webp", "p1", "s")
    []
    >>> provenance_record_problems("k", {"file": "y.webp"}, "x.webp", "p1", "s")
    ['provenance k: file y.webp does not match the asset x.webp', 'provenance k: produced.profile must be p1, got None', 'provenance k: produced.profile_sha256 does not match p1']
    """
    found = []
    if record.get("file") != rel:
        found.append(f"provenance {key}: file {record.get('file')} does not match the asset {rel}")
    produced = record.get("produced") or {}
    if produced.get("profile") != profile_id:
        found.append(f"provenance {key}: produced.profile must be {profile_id}, got {produced.get('profile')}")
    if produced.get("profile_sha256") != profile_sha:
        found.append(f"provenance {key}: produced.profile_sha256 does not match {profile_id}")
    return found


def referenced_legacy_pngs() -> list[Path]:
    """Legacy PNGs under docs/assets that some Markdown page still references."""
    text = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "docs").rglob("*.md"))
    return [p for p in sorted(ASSETS.rglob("*.png")) if p.name in text]


def problems(base_ref: str | None = None) -> list[str]:
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

    manifest_ids = {e["file"]: e["id"] for e in manifest.get("screenshots") or []}
    records = provenance.get("assets") or {}
    if base_ref:
        base_raw = git_show(base_ref, "scripts/capture/dimension-exceptions.yaml")
        base_list = None if base_raw is None else (yaml.safe_load(base_raw) or {}).get("exceptions") or []
        for rel in new_exceptions(exceptions.get("exceptions") or [], base_list):
            found.append(f"{rel}: new dimension exception; the list may only shrink, recapture instead")
        # Every screenshot added or re-encoded in this change must say which
        # profile produced it, so a new image cannot skip the standard.
        for rel in sorted(measured):
            current = (ASSETS / rel).read_bytes()
            if git_show(base_ref, f"docs/assets/{rel}") == current:
                continue
            key = manifest_ids.get(rel, rel)
            record = records.get(key)
            if record is None:
                found.append(f"{rel}: added or changed without a provenance record ({key})")
                continue
            if record.get("kind") == "legacy_reencode":
                continue  # validated by legacy_reencode_problems()
            found += provenance_record_problems(key, record, rel, profile["id"], profile_sha)

    for key, record in records.items():
        produced = record.get("produced", {})
        path = ASSETS / record.get("file", "")
        if not path.is_file():
            found.append(f"provenance {key}: {record.get('file')} does not exist")
            continue
        if produced.get("profile") == profile["id"] and produced.get("profile_sha256") != profile_sha:
            found.append(f"provenance {key}: recorded profile hash does not match {profile['id']}")
        if record.get("final_sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            found.append(f"provenance {key}: asset bytes changed since provenance was recorded")
    if base_ref:
        base_prov = git_show(base_ref, "scripts/capture/provenance.yaml")
        base_records = ((yaml.safe_load(base_prov) or {}).get("assets") or {}) if base_prov else {}
        found += legacy_reencode_problems(records, base_records, base_ref, raw_size, final_size)
    found += image_metadata_problems(manifest, base_ref)
    return found


SOURCE_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
UNREGISTERED_OK = {"favicon.svg", "logo.svg"}
IMAGE_SUFFIXES = {".png", ".webp", ".jpg", ".jpeg", ".gif"}


def legacy_reencode_problems(records: dict, base_records: dict, base_ref: str,
                             raw_size: tuple[int, int], final_size: tuple[int, int]) -> list[str]:
    """A legacy_reencode record never claims a capture profile.

    A new record must name a profile-size source PNG whose bytes exist at the
    base revision and are deleted in the same change; an existing record is
    immutable, so later changes must go through a real capture.
    """
    found: list[str] = []
    sources: dict[str, str] = {}
    for key, record in records.items():
        if record.get("kind") != "legacy_reencode":
            continue
        if "produced" in record:
            found.append(f"provenance {key}: legacy_reencode must not carry a produced profile")
        if key in base_records:
            if base_records[key] != record:
                found.append(f"provenance {key}: legacy_reencode records are immutable; recapture instead")
            continue
        src = (record.get("derived_from") or {}).get("path", "")
        base_bytes = git_show(base_ref, src) if src else None
        if base_bytes is None:
            found.append(f"provenance {key}: source {src} does not exist at {base_ref}")
            continue
        if hashlib.sha256(base_bytes).hexdigest() != record["derived_from"].get("sha256"):
            found.append(f"provenance {key}: source sha256 does not match {src} at {base_ref}")
        if not base_bytes.startswith(SOURCE_PNG_SIGNATURE) or png_size(base_bytes) != raw_size:
            found.append(f"provenance {key}: source must be a {raw_size[0]}x{raw_size[1]} PNG")
        if (ROOT / src).exists():
            found.append(f"provenance {key}: source {src} must be deleted in the same change")
        if src in sources:
            found.append(f"provenance {key}: source {src} already produced {sources[src]}")
        sources[src] = key
        out = ASSETS / record.get("file", "")
        if out.is_file() and webp_size(out.read_bytes()) != final_size:
            found.append(f"provenance {key}: output must be {final_size[0]}x{final_size[1]}")
    return found


def image_references(text: str) -> list[tuple[int, str, str, str]]:
    """Image references outside code fences: (line, kind, target, alt).

    >>> image_references('a\\n[[[ shot("x") ]]]\\n![Alt](../assets/a.png)\\n```\\n![n](b.png)\\n```')
    [(2, 'shot', 'x', ''), (3, 'path', '../assets/a.png', 'Alt')]
    """
    refs, fence = [], False
    for number, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence:
            continue
        for m in re.finditer(r'shot\(\s*["\']([^"\']+)["\']\s*\)', line):
            refs.append((number, "shot", m.group(1), ""))
        for m in re.finditer(r"!\[((?:[^\]\\]|\\.)*)\]\(([^)\s]+)\)", line):
            if not m.group(2).startswith(("http://", "https://")):
                refs.append((number, "path", m.group(2), m.group(1)))
    return refs


def caption_missing(lines: list[str], index: int) -> bool:
    """True unless Purpose / Look for / Expected result follow, in order, before
    the next image or heading.

    >>> caption_missing(["![a](x)", "", "Purpose: p", "Look for: l", "Expected result: e"], 0)
    False
    >>> caption_missing(["![a](x)", "Look for: l", "Purpose: p", "Expected result: e"], 0)
    True
    >>> caption_missing(["![a](x)", "## Next", "Purpose: p"], 0)
    True
    """
    wanted = ["Purpose:", "Look for:", "Expected result:"]
    for line in lines[index + 1:]:
        text = line.strip()
        if text.startswith("#") or "shot(" in text or text.startswith("!["):
            break
        if wanted and text.startswith(wanted[0]):
            wanted.pop(0)
            if not wanted:
                return False
    return True


def changed_lines(base_ref: str, rel: str) -> set[int] | None:
    """Line numbers added or modified in ``rel`` since ``base_ref`` (None = new file)."""
    if git_show(base_ref, rel) is None:
        return None
    diff = subprocess.run(["git", "diff", "--unified=0", base_ref, "--", rel],
                          cwd=ROOT, capture_output=True, text=True, check=False).stdout
    lines: set[int] = set()
    for m in re.finditer(r"^@@ -\S+ \+(\d+)(?:,(\d+))? @@", diff, re.M):
        start, count = int(m.group(1)), int(m.group(2) or 1)
        lines.update(range(start, start + count))
    return lines


def image_metadata_problems(manifest: dict, base_ref: str | None) -> list[str]:
    found: list[str] = []
    shots = {e["id"]: e for e in manifest.get("screenshots") or []}
    legacy_raw = (CAPTURE / "legacy-assets.yaml").read_text(encoding="utf-8")
    legacy = {e["file"]: e for e in (yaml.safe_load(legacy_raw) or {}).get("assets") or []}
    used_shots: set[str] = set()
    used_legacy: set[str] = set()
    advisory = 0
    for page in sorted((ROOT / "docs").rglob("*.md")):
        rel_page = str(page.relative_to(ROOT))
        text = page.read_text(encoding="utf-8")
        lines = text.split("\n")
        fresh = changed_lines(base_ref, rel_page) if base_ref else set()
        for number, kind, target, alt in image_references(text):
            where = f"{rel_page}:{number}"
            if kind == "shot":
                if target not in shots:
                    found.append(f"{where}: shot(\"{target}\") is not in manifest.yaml")
                used_shots.add(target)
            else:
                resolved = (page.parent / target).resolve()
                try:
                    asset = str(resolved.relative_to(ASSETS.resolve()))
                except ValueError:
                    found.append(f"{where}: image {target} is outside docs/assets")
                    continue
                entry = legacy.get(asset)
                if entry is None:
                    found.append(f"{where}: direct image path {asset}; use shot(\"<id>\") from manifest.yaml")
                    continue
                used_legacy.add(asset)
                if alt.replace("\\", "") != entry["alt"]:
                    found.append(f"{where}: alt for {asset} must be the canonical legacy-assets.yaml alt")
            if caption_missing(lines, number - 1):
                if base_ref and (fresh is None or number in fresh):
                    found.append(f"{where}: image needs Purpose / Look for / Expected result lines")
                else:
                    advisory += 1
    for shot_id in sorted(set(shots) - used_shots):
        found.append(f"manifest.yaml: {shot_id} is not referenced from docs; delete it with its file")
    for asset in sorted(set(legacy) - used_legacy):
        found.append(f"legacy-assets.yaml: {asset} is not referenced; delete it with its file")
    registered = {e["file"] for e in shots.values()} | set(legacy)
    for path in sorted(ASSETS.rglob("*")):
        if path.suffix.lower() in IMAGE_SUFFIXES | {".svg"} and path.name not in UNREGISTERED_OK:
            if str(path.relative_to(ASSETS)) not in registered:
                found.append(f"{path.relative_to(ASSETS)}: image file is not in manifest.yaml or legacy-assets.yaml")
    for asset, entry in legacy.items():
        path = ASSETS / asset
        if not path.is_file():
            found.append(f"legacy-assets.yaml: {asset} does not exist")
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry.get("sha256") or list(png_size(data)) != [entry.get("width"), entry.get("height")]:
            found.append(f"legacy-assets.yaml: {asset} bytes or size changed; recapture into manifest.yaml instead")
    if base_ref:
        base_raw = git_show(base_ref, "scripts/capture/legacy-assets.yaml")
        if base_raw is not None:
            base_files = {e["file"] for e in (yaml.safe_load(base_raw) or {}).get("assets") or []}
            for asset in sorted(set(legacy) - base_files):
                found.append(f"legacy-assets.yaml: {asset} is new; the registry may only shrink")
    if advisory:
        print(f"Advisory: {advisory} existing image reference(s) without Purpose / Look for / Expected result.")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--base-ref",
        help="Git ref of the PR base; enables shrink-only exceptions and provenance for changed images.",
    )
    found = problems(parser.parse_args().base_ref)
    if found:
        print("Capture asset check failed:")
        for item in found:
            print(f"  - {item}")
        return 1
    print("Capture assets conform to the capture profile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
