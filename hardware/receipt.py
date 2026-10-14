"""ESC/POS rendering for the 58 mm KMP26 receipt printer.

Font A on 58 mm paper is 32 columns. The printer's default code page has no
peso sign or accented letters, so every string is folded to plain ASCII and
money is written as ``PHP 12.00``. The layout mirrors the on-screen receipt
in ``web/static/js/pos.js``.
"""

from __future__ import annotations

from datetime import datetime
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

WIDTH = 32

ESC_INIT = b"\x1b@"
# ESC 7 n1 n2 n3: at most 8*(n1+1) = 32 dots heated at once, 800 us heat time,
# 20 us interval. The printer shares the TB74's 12 V rail; at the default a
# solid rule browned it out (~400 ms BUSY, buffered text lost), while this
# setting printed the same rule fully dark with no BUSY (2026-09-28 bench, J3/J4).
LIMIT_PEAK_HEAT = b"\x1b7\x03\x50\x02"
ALIGN_LEFT = b"\x1ba\x00"
ALIGN_CENTER = b"\x1ba\x01"
BOLD_ON = b"\x1bE\x01"
BOLD_OFF = b"\x1bE\x00"
DOUBLE_ON = b"\x1b!\x30"      # double width + double height
DOUBLE_OFF = b"\x1b!\x00"
# The kiosk's KMP26 ignored every cut command tried on the 2026-09-28 bench
# (GS V 0, GS V 1, GS V 66 0, ESC i, ESC m), so it has no working cutter and
# the receipt is torn by hand. Feed the last lines past the tear bar. GS V 1 is
# kept for a replacement printer that has a cutter; this one ignores it.
FEED_TO_TEAR = b"\x1bd\x06"
CUT = b"\x1dV\x01"

# A solid 32-dash rule heats almost the whole head in one dot row; on the kiosk
# printer that made it hold BUSY ~400 ms, and every lost run of receipt text
# began right after one (2026-09-28 bench). Spaced dashes caused no BUSY.
RULE = "- " * (WIDTH // 2 - 1) + "-"

PAYMENT_LABELS = {
    "cash": "Cash",
    "xendit_cashless": "Cashless (Xendit)",
}


def ascii_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value if value is not None else ""))
    text = text.replace("₱", "PHP ")
    folded = text.encode("ascii", "ignore").decode("ascii")
    return "".join(ch if 32 <= ord(ch) < 127 else " " for ch in folded)


def php(centavos: int) -> str:
    centavos = int(centavos)
    sign = "-" if centavos < 0 else ""
    centavos = abs(centavos)
    return f"{sign}PHP {centavos // 100:,}.{centavos % 100:02d}"


def _pair(left: str, right: str) -> str:
    left, right = ascii_text(left), ascii_text(right)
    space = WIDTH - len(right) - 1
    if len(left) > space:
        left = left[: max(0, space)]
    return f"{left}{' ' * (WIDTH - len(left) - len(right))}{right}"


def _wrap(text: str, width: int = WIDTH) -> List[str]:
    words, lines, line = ascii_text(text).split(), [], ""
    for word in words:
        while len(word) > width:
            if line:
                lines.append(line)
                line = ""
            lines.append(word[:width])
            word = word[width:]
        candidate = f"{line} {word}".strip()
        if len(candidate) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def _lines(*rows: str) -> bytes:
    return "".join(f"{row}\n" for row in rows).encode("ascii")


def render_receipt(
    order: Dict[str, Any],
    *,
    printed_at: Optional[datetime] = None,
    copy_label: Optional[str] = None,
) -> bytes:
    """Render a completed order (``OrderService.get_order`` shape) to ESC/POS."""
    rule = RULE
    when = order.get("completed_at") or order.get("paid_at")
    if not when:
        when = (printed_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    method = PAYMENT_LABELS.get(str(order.get("payment_method", "")), ascii_text(order.get("payment_method", "")))

    out = bytearray(ESC_INIT + LIMIT_PEAK_HEAT)
    out += ALIGN_CENTER + DOUBLE_ON + _lines("MENDO VENDO") + DOUBLE_OFF
    out += _lines("OTC Medicine Vending System")
    if copy_label:
        out += BOLD_ON + _lines(f"*** {ascii_text(copy_label)} ***") + BOLD_OFF
    out += ALIGN_LEFT + _lines(
        rule,
        _pair("Receipt", str(order.get("transaction_ref") or "-")),
        _pair("Order", str(order.get("order_ref") or "-")),
        _pair("Date", str(when)[:16]),
        _pair("Payment", method),
        rule,
    )

    for item in order.get("items") or []:
        quantity = int(item.get("quantity_ordered") or item.get("quantity") or 0)
        unit = int(item.get("unit_price_centavos") or 0)
        out += _lines(*_wrap(str(item.get("brand", "")))[:2])
        out += _lines(_pair(f"  {quantity} x {php(unit)[4:]}", php(unit * quantity)[4:]))

    total = int(order.get("total_centavos") or 0)
    received = int(order.get("received_cash_centavos") or 0)
    excess = int(order.get("overpayment_centavos") or max(0, received - total))
    out += _lines(rule)
    out += BOLD_ON + _lines(_pair("TOTAL", php(total))) + BOLD_OFF
    if order.get("payment_method") == "cash":
        out += _lines(_pair("Cash received", php(received)))
        if excess:
            out += _lines(_pair("Excess (no change)", php(excess)))
    out += _lines(rule)

    out += ALIGN_CENTER
    footer: Iterable[str] = (
        "This machine does not give change.",
        "Take medicine as directed on the label.",
        "Consult a doctor if symptoms persist or get worse.",
        "This is not an official receipt.",
    )
    for sentence in footer:
        out += _lines(*_wrap(sentence))
    out += _lines("", "Salamat! Thank you!")
    out += ALIGN_LEFT + FEED_TO_TEAR + CUT
    return bytes(out)


def render_test_slip(message: str = "Printer test", *, printed_at: Optional[datetime] = None) -> bytes:
    when = (printed_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    out = bytearray(ESC_INIT + LIMIT_PEAK_HEAT)
    out += ALIGN_CENTER + DOUBLE_ON + _lines("MENDO VENDO") + DOUBLE_OFF
    out += _lines(*_wrap(message), when, RULE, "If you can read this,", "the printer works.")
    out += ALIGN_LEFT + FEED_TO_TEAR + CUT
    return bytes(out)
