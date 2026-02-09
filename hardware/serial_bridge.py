"""Mendo Vendo — Serial Bridge between Flask and Arduino.

Communicates with the Arduino Uno over USB serial to send DISPENSE
commands and receive acknowledgments.

Usage from Flask:
    from hardware.serial_bridge import VendoBridge
    bridge = VendoBridge()          # auto-detects port or reads config
    bridge.connect()                # opens serial connection
    bridge.dispense_by_brand("Bioflu")  # maps brand → slot → DISPENSE:N
    bridge.close()
"""

from __future__ import annotations

import json
import os
import time
import threading
from typing import Optional, Dict

# Serial library (optional at import time)
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_DIR, "config.json")


class VendoBridge:
    """Python ↔ Arduino serial bridge for the Mendo vending machine."""

    def __init__(self, config_path: str = _CONFIG_PATH):
        self._ser: Optional[serial.Serial] = None  # type: ignore[name-defined]
        self._lock = threading.Lock()
        self._config: Dict = {}
        self._slots: Dict[str, int] = {}  # brand → slot number (1-indexed)
        self._port: Optional[str] = None
        self._baud: int = 9600
        self._timeout: float = 3.0
        self._load_config(config_path)

    # ── Configuration ─────────────────────────────────

    def _load_config(self, path: str) -> None:
        """Load slot mapping and serial settings from config.json."""
        if os.path.exists(path):
            with open(path) as f:
                self._config = json.load(f)
            self._slots = self._config.get("slots", {})
            self._port = self._config.get("port")  # None = auto-detect
            self._baud = self._config.get("baud", 9600)
            self._timeout = self._config.get("timeout", 3.0)
        else:
            print(f"[VendoBridge] Config not found at {path}, using defaults")
            self._slots = {}

    def get_slot(self, brand: str) -> Optional[int]:
        """Get the slot number (1-indexed) for a medicine brand."""
        # Exact match first
        if brand in self._slots:
            return self._slots[brand]
        # Case-insensitive search
        for key, slot in self._slots.items():
            if key.lower() == brand.lower():
                return slot
        return None

    # ── Connection ────────────────────────────────────

    def _auto_detect_port(self) -> Optional[str]:
        """Auto-detect Arduino Uno serial port."""
        if not SERIAL_AVAILABLE:
            return None
        ports = serial.tools.list_ports.comports()
        for p in ports:
            desc = (p.description or "").lower()
            mfg = (p.manufacturer or "").lower()
            # Common Arduino identifiers
            if "arduino" in desc or "arduino" in mfg:
                return p.device
            if "ch340" in desc or "ch341" in desc:  # Common cheap Uno clones
                return p.device
            if "usb" in desc and ("serial" in desc or "uart" in desc):
                return p.device
        # Fallback: try common Linux/Mac paths
        for candidate in ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyUSB1", "/dev/ttyACM1"]:
            if os.path.exists(candidate):
                return candidate
        return None

    def connect(self, port: Optional[str] = None) -> bool:
        """Open serial connection to Arduino.
        
        Args:
            port: Serial port path. If None, uses config or auto-detect.
        
        Returns:
            True if connected successfully.
        """
        if not SERIAL_AVAILABLE:
            print("[VendoBridge] pyserial not installed. Run: pip install pyserial")
            return False

        target_port = port or self._port or self._auto_detect_port()
        if not target_port:
            print("[VendoBridge] No Arduino port found")
            return False

        try:
            with self._lock:
                if self._ser and self._ser.is_open:
                    self._ser.close()
                self._ser = serial.Serial(
                    port=target_port,
                    baudrate=self._baud,
                    timeout=self._timeout,
                )
                # Wait for Arduino to reset after serial connection
                time.sleep(2.0)
                # Flush any startup messages
                self._ser.reset_input_buffer()
                self._port = target_port
                print(f"[VendoBridge] Connected to {target_port} @ {self._baud} baud")
                return True
        except Exception as e:
            print(f"[VendoBridge] Connection failed: {e}")
            return False

    def close(self) -> None:
        """Close serial connection."""
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
                print("[VendoBridge] Connection closed")

    def is_connected(self) -> bool:
        """Check if serial port is open."""
        return bool(self._ser and self._ser.is_open)

    # ── Commands ──────────────────────────────────────

    def _send_command(self, cmd: str, timeout: float = 5.0) -> str:
        """Send a command and wait for response.
        
        Args:
            cmd: Command string (e.g. "DISPENSE:1")
            timeout: Max seconds to wait for response
            
        Returns:
            Response string from Arduino
            
        Raises:
            RuntimeError: If not connected or timeout
        """
        if not self.is_connected():
            raise RuntimeError("Not connected to Arduino")

        # Known response prefixes for valid Arduino responses
        _RESPONSE_PREFIXES = (
            "PONG", "READY:", "OK:", "ERR:", "TEST_OK:", "BATCH_OK:",
            "RESET_OK", "DISPENSING:",
        )

        with self._lock:
            # Clear input buffer
            self._ser.reset_input_buffer()
            # Send command with newline
            self._ser.write((cmd.strip() + "\n").encode("ascii"))
            self._ser.flush()

            # Wait for response — skip startup/info lines
            start = time.time()
            while time.time() - start < timeout:
                if self._ser.in_waiting > 0:
                    line = self._ser.readline().decode("ascii", errors="replace").strip()
                    if line:
                        # Skip known startup/info messages that aren't real responses
                        if line.startswith("MENDO_VENDO") or line.startswith("SLOTS:"):
                            continue
                        return line
                time.sleep(0.05)

            raise RuntimeError(f"Timeout waiting for response to '{cmd}'")

    def ping(self) -> bool:
        """Check if Arduino is responsive."""
        try:
            resp = self._send_command("PING", timeout=2.0)
            return resp == "PONG"
        except Exception:
            return False

    def status(self) -> str:
        """Get Arduino status."""
        return self._send_command("STATUS")

    def dispense(self, slot: int) -> bool:
        """Dispense medicine from a slot number (1-indexed).
        
        Args:
            slot: Slot number (1, 2, or 3)
            
        Returns:
            True if Arduino acknowledged successfully
        """
        max_slot = max(self._slots.values()) if self._slots else 2
        if slot < 1 or slot > max_slot:
            raise ValueError(f"Invalid slot number: {slot}. Must be 1-{max_slot}.")
        
        resp = self._send_command(f"DISPENSE:{slot}", timeout=10.0)
        return resp == f"OK:{slot}"

    def dispense_by_brand(self, brand: str) -> bool:
        """Dispense medicine by brand name (looks up slot from config).
        
        Args:
            brand: Medicine brand name (e.g. "Bioflu")
            
        Returns:
            True if dispensed successfully
            
        Raises:
            ValueError: If brand not mapped to any slot
        """
        slot = self.get_slot(brand)
        if slot is None:
            raise ValueError(
                f"Brand '{brand}' not mapped to any vending slot. "
                f"Update hardware/config.json to add mapping."
            )
        return self.dispense(slot)

    def dispense_batch(self, slot_qty_map: Dict[int, int]) -> Dict[int, int]:
        """Dispense multiple slots simultaneously with quantity-based duration.

        The Arduino runs all actuators at once. Each slot spins for
        qty × SPIN_PER_QTY_MS (5 sec per unit on the Arduino).

        Args:
            slot_qty_map: {slot_number: quantity} e.g. {1: 2, 2: 3}

        Returns:
            Dict of {slot: qty_dispensed} on success

        Raises:
            ValueError: If a slot number is invalid
            RuntimeError: If not connected or timeout
        """
        if not slot_qty_map:
            raise ValueError("Empty batch")

        max_slot = max(self._slots.values()) if self._slots else 2
        for slot, qty in slot_qty_map.items():
            if slot < 1 or slot > max_slot:
                raise ValueError(f"Invalid slot number: {slot}. Must be 1-{max_slot}.")
            if qty < 1 or qty > 10:
                raise ValueError(f"Invalid quantity: {qty}. Must be 1-10.")

        # Build command: "BATCH:1=2,2=3"
        pairs = ",".join(f"{s}={q}" for s, q in slot_qty_map.items())
        cmd = f"BATCH:{pairs}"

        # Timeout = max_qty × 5 sec + generous buffer
        max_qty = max(slot_qty_map.values())
        timeout = max_qty * 6.0 + 5.0

        resp = self._send_command(cmd, timeout=timeout)

        # Parse response: "BATCH_OK:1=2,2=3"
        if resp.startswith("BATCH_OK:"):
            result = {}
            for pair in resp[9:].split(","):
                parts = pair.split("=")
                if len(parts) == 2:
                    result[int(parts[0])] = int(parts[1])
            return result

        # Firmware fallback: if BATCH isn't supported, try sequential DISPENSE
        if resp.startswith("ERR:UNKNOWN_CMD"):
            result = {}
            for slot, qty in slot_qty_map.items():
                qty_done = 0
                for _ in range(qty):
                    try:
                        if self.dispense(slot):
                            qty_done += 1
                    except Exception:
                        break
                result[slot] = qty_done
            return result

        raise RuntimeError(f"Batch dispense failed: {resp}")

    def dispense_batch_by_brands(self, brand_qty_map: Dict[str, int]) -> Dict[str, Dict]:
        """Dispense multiple brands simultaneously with quantities.

        Args:
            brand_qty_map: {"Decolgen": 2, "Biogesic": 3}

        Returns:
            Dict per brand: {"Decolgen": {"dispensed": True, "qty": 2, "slot": 1}, ...}
        """
        slot_qty = {}
        brand_to_slot = {}
        unmapped = []

        for brand, qty in brand_qty_map.items():
            slot = self.get_slot(brand)
            if slot is None:
                unmapped.append(brand)
            else:
                slot_qty[slot] = qty
                brand_to_slot[brand] = slot

        results = {}

        # Dispense mapped brands in one batch
        if slot_qty:
            batch_result = self.dispense_batch(slot_qty)
            for brand, slot in brand_to_slot.items():
                qty_done = batch_result.get(slot, 0)
                results[brand] = {
                    "dispensed": qty_done == brand_qty_map[brand],
                    "qty": qty_done,
                    "slot": slot,
                }

        # Report unmapped brands
        for brand in unmapped:
            results[brand] = {
                "dispensed": False,
                "qty": 0,
                "slot": None,
                "error": "No vending slot mapped",
            }

        return results

    def test_slot(self, slot: int) -> bool:
        """Test a servo without full dispense (small movement)."""
        resp = self._send_command(f"TEST:{slot}", timeout=3.0)
        return resp == f"TEST_OK:{slot}"

    def reset(self) -> bool:
        """Reset all servos to rest position."""
        resp = self._send_command("RESET", timeout=3.0)
        return resp == "RESET_OK"

    # ── Context manager ───────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()


# ─── CLI for testing ──────────────────────────────────
if __name__ == "__main__":
    import sys

    bridge = VendoBridge()
    print("Mendo Vendo — Serial Bridge Test")
    print(f"Config slots: {bridge._slots}")
    print(f"Serial available: {SERIAL_AVAILABLE}")

    if not SERIAL_AVAILABLE:
        print("Install pyserial: pip install pyserial")
        sys.exit(1)

    # Auto-detect
    port = bridge._auto_detect_port()
    print(f"Detected port: {port}")

    if not port:
        print("No Arduino detected. Check USB connection.")
        sys.exit(1)

    if bridge.connect(port):
        print("Connected! Testing...")

        # Ping
        if bridge.ping():
            print("✓ PING/PONG OK")
        else:
            print("✗ PING failed")

        # Status
        try:
            st = bridge.status()
            print(f"✓ Status: {st}")
        except Exception as e:
            print(f"✗ Status error: {e}")

        # Interactive test
        while True:
            cmd = input("\nEnter command (1/2/3 to dispense, t1/t2/t3 to test, r=reset, q=quit): ").strip()
            if cmd == "q":
                break
            elif cmd == "r":
                print("Reset:", bridge.reset())
            elif cmd.startswith("t") and len(cmd) == 2:
                slot = int(cmd[1])
                print(f"Test slot {slot}:", bridge.test_slot(slot))
            elif cmd in ("1", "2", "3"):
                print(f"Dispense slot {cmd}:", bridge.dispense(int(cmd)))
            else:
                print("Unknown. Use 1-3, t1-t3, r, or q.")

        bridge.close()
    else:
        print("Could not connect.")
