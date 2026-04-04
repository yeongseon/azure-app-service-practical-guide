#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import shutil
from collections import Counter
from pathlib import Path


UUID_PATTERN = re.compile(
    r"\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b", re.IGNORECASE
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
RESOURCE_SUB_PATTERN = re.compile(r"(/subscriptions/)([a-f0-9-]{36})(/)", re.IGNORECASE)
BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._\-+/=]+", re.IGNORECASE)
SAS_PATTERN = re.compile(r"([?&](?:sig|se|sp|spr|sv|sr|srt|ss)=[^&\s]+)", re.IGNORECASE)
AZURE_WEBSITE_PATTERN = re.compile(
    r"\b([a-z0-9-]+)\.azurewebsites\.net\b", re.IGNORECASE
)

MASKED_UUID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sanitize lab artifact files")
    parser.add_argument("--input-dir", required=True, help="Input artifacts directory")
    parser.add_argument(
        "--output-dir", required=True, help="Sanitized output directory"
    )
    return parser.parse_args()


def should_mask_ip(ip_text: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return False

    if ip_text in {"0.0.0.0", "127.0.0.1"}:
        return False
    if ip.is_private:
        return False
    return True


def replace_ip(match: re.Match[str], counters: Counter) -> str:
    candidate = match.group(0)
    if should_mask_ip(candidate):
        counters["ip_addresses"] += 1
        return "<ip-redacted>"
    return candidate


def sanitize_text(content: str, counters: Counter) -> str:
    content, count = RESOURCE_SUB_PATTERN.subn(r"\1" + MASKED_UUID + r"\3", content)
    counters["resource_subscription_ids"] += count

    content, count = BEARER_PATTERN.subn("Bearer <token-redacted>", content)
    counters["bearer_tokens"] += count

    content, count = SAS_PATTERN.subn(
        lambda m: f"{m.group(0).split('=')[0]}=<token-redacted>", content
    )
    counters["sas_tokens"] += count

    content, count = EMAIL_PATTERN.subn("<email-redacted>", content)
    counters["emails"] += count

    content, count = AZURE_WEBSITE_PATTERN.subn(
        r"\1.<azurewebsites-domain-redacted>", content
    )
    counters["azurewebsites_hostnames"] += count

    content, count = UUID_PATTERN.subn(MASKED_UUID, content)
    counters["subscription_or_uuid"] += count

    content = IP_PATTERN.sub(lambda m: replace_ip(m, counters), content)
    return content


def process_file(src: Path, dst: Path, counters: Counter) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    data = src.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        shutil.copy2(src, dst)
        counters["binary_files_copied"] += 1
        return

    sanitized = sanitize_text(text, counters)
    dst.write_text(sanitized, encoding="utf-8")
    counters["text_files_processed"] += 1


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input directory not found: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    counters: Counter = Counter()

    for root, _, files in os.walk(input_dir):
        for name in files:
            src = Path(root) / name
            rel = src.relative_to(input_dir)
            dst = output_dir / rel
            process_file(src, dst, counters)
            counters["files_processed"] += 1

    print("[sanitize-artifacts] completed")
    print(f"files processed: {counters['files_processed']}")
    print("replacements:")
    for key in [
        "resource_subscription_ids",
        "subscription_or_uuid",
        "emails",
        "ip_addresses",
        "bearer_tokens",
        "sas_tokens",
        "azurewebsites_hostnames",
    ]:
        print(f"  {key}: {counters[key]}")
    print(f"text files processed: {counters['text_files_processed']}")
    print(f"binary files copied: {counters['binary_files_copied']}")


if __name__ == "__main__":
    main()
