#!/usr/bin/env python3
from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Final

GUID_RE: Final = re.compile(r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b")
EMAIL_RE: Final = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
IPV4_RE: Final = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
AZURE_HOST_RE: Final = re.compile(r"\b[a-z0-9-]+\.(?:scm\.)?azurewebsites\.net\b", re.IGNORECASE)
RESOURCE_ID_RE: Final = re.compile(
    r"/subscriptions/[^/]+/resourceGroups/[^/]+/providers/[^\s\"']+", re.IGNORECASE
)
RESOURCE_ID_PLACEHOLDER: Final = (
    "/subscriptions/00000000-0000-0000-0000-000000000000/"
    "resourceGroups/rg-golden-e2e/providers/Microsoft.Web/sites/app-golden-e2e"
)
RESOURCE_ID_SENTINEL: Final = "__GOLDEN_RESOURCE_ID_PLACEHOLDER__"
IPV6_CANDIDATE_RE: Final = re.compile(r"(?<![0-9A-Fa-f:])[0-9A-Fa-f:]*:[0-9A-Fa-f:]+(?![0-9A-Fa-f:])")
BEARER_RE: Final = re.compile(r"(?i)(Authorization\s*[:=]\s*Bearer\s+)[A-Za-z0-9._~+/=-]+")
JWT_RE: Final = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![A-Za-z0-9_-])")
BASE64_TOKEN_RE: Final = re.compile(
    r"(?<![A-Za-z0-9+/=_-])(?=[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-]))"
    r"(?=[A-Za-z0-9+/=_-]*[A-Z])(?=[A-Za-z0-9+/=_-]*[a-z])(?=[A-Za-z0-9+/=_-]*\d)"
    r"[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-])"
)
SECRET_ASSIGNMENT_RE: Final = re.compile(
    r"(?i)(?P<key_quote>[\"']?)(?P<key>\b(?:[A-Z][A-Z0-9_]*_)?(?:password|passwd|secret|token|"
    r"api[_-]?key|account[_-]?key|client[_-]?secret|access[_-]?key|credential|"
    r"connection[_-]?string)\b)(?P=key_quote)(?P<separator>\s*[:=]\s*)"
    r"(?P<value>\"(?=[^\"\r\n]*[^\"\s\r\n])[^\"\r\n]+\"|"
    r"'(?=[^'\r\n]*[^'\s\r\n])[^'\r\n]+'|[^\s,;}]+)"
)
SAS_RE: Final = re.compile(r"(?i)((?:^|[?&;])(?:sig|sv|se)=)([^&;\s]+)")
CONNECTION_STRING_RE: Final = re.compile(r"(?i)DefaultEndpointsProtocol=[^;\s]+(?:;[^;\s=]+=[^;\s]*)+")
LONG_HEX_RE: Final = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32,}(?![0-9a-fA-F])")
SECRET_NAME_RE: Final = re.compile(r"(?i)(^id_(?:rsa|dsa|ecdsa|ed25519)$|\.(?:pem|pfx|p12|key)$|credential|secret)")


class SanitizationError(Exception):
    pass


def _replace_ipv4(match: re.Match[str]) -> str:
    octets = tuple(int(part) for part in match.group(0).split("."))
    if any(part > 255 for part in octets):
        return match.group(0)
    first, second, _, _ = octets
    private = first == 10 or (first == 172 and 16 <= second <= 31) or (first == 192 and second == 168)
    return "10.0.0.0" if private else "192.0.2.1"


def _replace_ipv6(match: re.Match[str]) -> str:
    candidate = match.group(0)
    if candidate in {"2001:db8::1", "fd00::1"}:
        return candidate
    try:
        parsed = ipaddress.IPv6Address(candidate)
    except ipaddress.AddressValueError:
        return candidate
    return "fd00::1" if parsed.is_private else "2001:db8::1"


def _replace_secret_assignment(match: re.Match[str]) -> str:
    value = match.group("value")
    quote = value[0] if value[0] in {"'", '"'} else ""
    return f"{match.group('key_quote')}{match.group('key')}{match.group('key_quote')}" \
        f"{match.group('separator')}{quote}<REDACTED>{quote}"


def sanitize_text(value: str) -> str:
    sanitized = CONNECTION_STRING_RE.sub("DefaultEndpointsProtocol=<REDACTED>;AccountKey=<REDACTED>", value)
    sanitized = SAS_RE.sub(r"\1<REDACTED>", sanitized)
    sanitized = GUID_RE.sub("00000000-0000-0000-0000-000000000000", sanitized)
    sanitized = EMAIL_RE.sub("user@example.com", sanitized)
    sanitized = RESOURCE_ID_RE.sub(RESOURCE_ID_SENTINEL, sanitized)
    sanitized = AZURE_HOST_RE.sub("app-golden-e2e.azurewebsites.net", sanitized)
    sanitized = BEARER_RE.sub(r"\1<REDACTED>", sanitized)
    sanitized = JWT_RE.sub("<REDACTED>", sanitized)
    sanitized = BASE64_TOKEN_RE.sub("<REDACTED>", sanitized)
    sanitized = SECRET_ASSIGNMENT_RE.sub(_replace_secret_assignment, sanitized)
    sanitized = LONG_HEX_RE.sub("<REDACTED_HEX_TOKEN>", sanitized)
    sanitized = IPV4_RE.sub(_replace_ipv4, sanitized)
    sanitized = IPV6_CANDIDATE_RE.sub(_replace_ipv6, sanitized)
    return sanitized.replace(RESOURCE_ID_SENTINEL, RESOURCE_ID_PLACEHOLDER)


def sanitize_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_dir():
            target.mkdir(exist_ok=True)
        elif path.is_file():
            if SECRET_NAME_RE.search(path.name):
                raise SanitizationError(f"refusing secret-like artifact name: {relative}")
            data = path.read_bytes()
            if b"\x00" in data:
                raise SanitizationError(f"refusing binary artifact: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SanitizationError(f"refusing non-UTF-8 artifact: {relative}") from exc
            target.write_text(sanitize_text(text), encoding="utf-8")


def scan_sanitized_tree(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        scrubbed = re.sub(
            r"([\"']?)<REDACTED>(?:_HEX_TOKEN)?\1",
            "",
            text,
        )
        token_scrubbed = scrubbed.replace(RESOURCE_ID_PLACEHOLDER, "")
        unsafe_guid = any(match.group(0) != "00000000-0000-0000-0000-000000000000" for match in GUID_RE.finditer(text))
        unsafe_email = any(match.group(0) != "user@example.com" for match in EMAIL_RE.finditer(text))
        unsafe_ip = any(match.group(0) not in {"10.0.0.0", "192.0.2.1"} for match in IPV4_RE.finditer(text))
        unsafe_resource = any(
            "00000000-0000-0000-0000-000000000000" not in match.group(0)
            or "resourceGroups/rg-golden-e2e/" not in match.group(0)
            for match in RESOURCE_ID_RE.finditer(text)
        )
        unsafe_ipv6 = any(
            match.group(0) not in {"2001:db8::1", "fd00::1"} and _replace_ipv6(match) != match.group(0)
            for match in IPV6_CANDIDATE_RE.finditer(text)
        )
        if (
            BEARER_RE.search(scrubbed) or JWT_RE.search(scrubbed) or BASE64_TOKEN_RE.search(token_scrubbed)
            or SECRET_ASSIGNMENT_RE.search(scrubbed) or SAS_RE.search(scrubbed)
            or CONNECTION_STRING_RE.search(scrubbed) or LONG_HEX_RE.search(scrubbed)
            or unsafe_guid or unsafe_email or unsafe_ip or unsafe_ipv6 or unsafe_resource
        ):
            raise SanitizationError(f"sanitized artifact still contains a secret-like value: {path.relative_to(root)}")
