"""Small ASCII protocol shared by the daemon, simulator, and AVR firmware.

Frame format (maximum 256 bytes including newline)::

    MENDO/1|KIND|REQUEST_ID|COMMAND|key=value;key=value|CRC16\n
Values are percent-escaped ASCII. CRC16-CCITT is calculated over everything
before the final ``|CRC16`` field. The bounded frame and parser are deliberate:
the Uno never has to allocate a JSON document or use ``String``.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, Mapping
from urllib.parse import quote, unquote


PROTOCOL_VERSION = "1"
MAX_FRAME_BYTES = 256
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
FIELD_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")


class ProtocolError(ValueError):
    pass


def crc16_ccitt(data: bytes, initial: int = 0xFFFF) -> int:
    crc = initial
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _validate_request_id(request_id: str) -> None:
    if not REQUEST_ID_RE.fullmatch(str(request_id)):
        raise ProtocolError("Invalid request id")


def _payload(fields: Mapping[str, object]) -> str:
    pairs = []
    for key in sorted(fields):
        key = str(key)
        if not FIELD_KEY_RE.fullmatch(key):
            raise ProtocolError(f"Invalid field key: {key}")
        value = quote(str(fields[key]), safe="-_.:/")
        pairs.append(f"{key}={value}")
    return ";".join(pairs)


def _parse_payload(payload: str) -> Dict[str, str]:
    if not payload:
        return {}
    result: Dict[str, str] = {}
    for pair in payload.split(";"):
        if "=" not in pair:
            raise ProtocolError("Malformed payload field")
        key, value = pair.split("=", 1)
        if not FIELD_KEY_RE.fullmatch(key) or key in result:
            raise ProtocolError("Invalid or duplicate payload field")
        result[key] = unquote(value)
    return result


@dataclass(frozen=True)
class Frame:
    kind: str
    request_id: str
    command: str
    fields: Dict[str, str]

    def encode(self) -> bytes:
        _validate_request_id(self.request_id)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", self.kind):
            raise ProtocolError("Invalid frame kind")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", self.command):
            raise ProtocolError("Invalid command")
        body = "|".join((f"MENDO/{PROTOCOL_VERSION}", self.kind, self.request_id, self.command, _payload(self.fields)))
        line = f"{body}|{crc16_ccitt(body.encode('ascii')):04X}\n".encode("ascii")
        if len(line) > MAX_FRAME_BYTES:
            raise ProtocolError(f"Frame exceeds {MAX_FRAME_BYTES} bytes")
        return line


def encode_frame(kind: str, request_id: str, command: str, fields: Mapping[str, object] | None = None) -> bytes:
    return Frame(kind, request_id, command, {str(k): str(v) for k, v in (fields or {}).items()}).encode()


def decode_frame(raw: bytes | str) -> Frame:
    if isinstance(raw, str):
        raw = raw.encode("ascii")
    if len(raw) > MAX_FRAME_BYTES:
        raise ProtocolError("Frame too large")
    if not raw.endswith(b"\n"):
        raise ProtocolError("Frame must be newline terminated")
    try:
        text = raw[:-1].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ProtocolError("Frame is not ASCII") from exc
    parts = text.split("|")
    if len(parts) != 6 or parts[0] != f"MENDO/{PROTOCOL_VERSION}":
        raise ProtocolError("Invalid frame envelope")
    body = "|".join(parts[:5])
    try:
        expected_crc = int(parts[5], 16)
    except ValueError as exc:
        raise ProtocolError("Invalid CRC field") from exc
    actual_crc = crc16_ccitt(body.encode("ascii"))
    if actual_crc != expected_crc:
        raise ProtocolError("CRC mismatch")
    _validate_request_id(parts[2])
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", parts[1]) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", parts[3]):
        raise ProtocolError("Invalid frame command fields")
    return Frame(parts[1], parts[2], parts[3], _parse_payload(parts[4]))


def command(request_id: str, name: str, **fields: object) -> bytes:
    return encode_frame("CMD", request_id, name, fields)


def response(request_id: str, name: str, **fields: object) -> bytes:
    return encode_frame("RSP", request_id, name, fields)


def event(request_id: str, name: str, **fields: object) -> bytes:
    return encode_frame("EVT", request_id, name, fields)
