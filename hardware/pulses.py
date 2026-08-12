"""Source-aware pulse grouping and calibrated denomination mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class PulseTrain:
    source: str
    pulse_count: int
    started_ms: int
    ended_ms: int
    pulse_widths_ms: Tuple[float, ...] = ()

    @property
    def duration_ms(self) -> int:
        return max(0, self.ended_ms - self.started_ms)


class PulseMapping:
    """Explicit calibration table; unknown pulse trains never get guessed."""

    # TB74-PH6 at 1 pulse / PHP 10 (10-way SW1-3 = OFF/OFF/OFF). Measured on
    # the 2026-08-03 bench: PHP 20/50/100 gave exactly 2/5/10 validated pulses
    # at 50 ms LOW and a 150 ms period. See
    # docs/architecture/tb74-pulse-protocol-analysis.md.
    #
    # PHP 200/500/1000 (20/50/100 pulses) are deliberately absent. They are
    # disabled at the acceptor's DIP bank because the kiosk gives no change,
    # so a train that long is not a payment -- leaving it unmapped routes it to
    # manual review, which is the correct outcome.
    DEFAULT_BILLS = {2: 2000, 5: 5000, 10: 10000}

    # Allan coin acceptor, MEASURED 2026-08-04 after calibration:
    #   PHP 1 -> 1 pulse, PHP 5 -> 5, PHP 20 -> 20, all at ~70 ms LOW / 170 ms.
    # Coins are LINEAR -- one pulse is one peso at every denomination -- unlike
    # bills, which carry a denomination code and must be looked up.
    #
    # Linear is required, not a convenience: coins fed in quick succession
    # merge into a single train (110 pulses in one 19 s train was observed), so
    # a lookup table would send a legitimate PHP 110 to manual review.
    COIN_CENTAVOS_PER_PULSE = 100
    COIN_MAX_PULSES = 200  # PHP 200 ceiling per train; longer trains are junk

    def __init__(
        self,
        *,
        coins: Optional[Dict[int, int]] = None,
        bills: Optional[Dict[int, int]] = None,
        coin_centavos_per_pulse: int = COIN_CENTAVOS_PER_PULSE,
        coin_max_pulses: int = COIN_MAX_PULSES,
    ):
        # An explicit coin table opts out of linear scaling and back into
        # strict lookup, where an unrecognised count credits nothing.
        self.coins = dict(coins) if coins is not None else {}
        self.coin_linear = coins is None
        self.coin_centavos_per_pulse = int(coin_centavos_per_pulse)
        self.coin_max_pulses = int(coin_max_pulses)
        self.bills = dict(bills if bills is not None else self.DEFAULT_BILLS)

    def map(self, source: str, pulse_count: int) -> Optional[int]:
        count = int(pulse_count)
        if source == "coin" and self.coin_linear:
            if count <= 0 or count > self.coin_max_pulses:
                return None
            return count * self.coin_centavos_per_pulse
        table = self.coins if source == "coin" else self.bills if source == "bill" else {}
        return table.get(count)

    def pulses_for(self, source: str, centavos: int) -> Optional[int]:
        if source == "coin" and self.coin_linear:
            value = int(centavos)
            if value <= 0 or value % self.coin_centavos_per_pulse:
                return None
            pulses = value // self.coin_centavos_per_pulse
            return pulses if pulses <= self.coin_max_pulses else None
        table = self.coins if source == "coin" else self.bills if source == "bill" else {}
        for pulses, value in table.items():
            if int(value) == int(centavos):
                return int(pulses)
        return None

    def supported_centavos(self, source: str) -> Tuple[int, ...]:
        if source == "coin" and self.coin_linear:
            # The physically issued Philippine coins, not the whole linear range.
            return tuple(
                d * self.coin_centavos_per_pulse for d in (1, 5, 10, 20)
                if d <= self.coin_max_pulses
            )
        table = self.coins if source == "coin" else self.bills if source == "bill" else {}
        return tuple(sorted(set(int(value) for value in table.values())))


class PulseTrainAssembler:
    """Group falling edges after source-specific gap and bounce filtering."""

    def __init__(self, source: str, *, gap_ms: float, debounce_ms: float = 3.0):
        self.source = source
        self.gap_ms = float(gap_ms)
        self.debounce_ms = float(debounce_ms)
        self._started: Optional[int] = None
        self._last_edge: Optional[float] = None
        self._count = 0
        self._widths: List[float] = []

    def falling_edge(self, timestamp_ms: float) -> Optional[PulseTrain]:
        completed = None
        if self._last_edge is not None:
            delta = timestamp_ms - self._last_edge
            if delta < self.debounce_ms:
                return None
            if delta >= self.gap_ms:
                completed = self.flush(self._last_edge)
        if self._started is None:
            self._started = int(timestamp_ms)
        self._count += 1
        self._last_edge = timestamp_ms
        return completed

    def flush(self, timestamp_ms: float) -> Optional[PulseTrain]:
        if not self._count or self._started is None:
            self._reset()
            return None
        ended = int(timestamp_ms if timestamp_ms >= self._started else self._last_edge or self._started)
        result = PulseTrain(self.source, self._count, self._started, ended, tuple(self._widths))
        self._reset()
        return result

    def finalize_if_quiet(self, timestamp_ms: float) -> Optional[PulseTrain]:
        if self._last_edge is None or timestamp_ms - self._last_edge < self.gap_ms:
            return None
        return self.flush(self._last_edge)

    def _reset(self) -> None:
        self._started = None
        self._last_edge = None
        self._count = 0
        self._widths.clear()


def group_edges(source: str, edges_ms: Iterable[float], *, gap_ms: float, debounce_ms: float = 3.0) -> List[PulseTrain]:
    edges = list(edges_ms)
    assembler = PulseTrainAssembler(source, gap_ms=gap_ms, debounce_ms=debounce_ms)
    result: List[PulseTrain] = []
    for edge in edges:
        complete = assembler.falling_edge(float(edge))
        if complete:
            result.append(complete)
    if edges:
        last = edges[-1]
        complete = assembler.finalize_if_quiet(float(last) + gap_ms)
        if complete:
            result.append(complete)
    return result
