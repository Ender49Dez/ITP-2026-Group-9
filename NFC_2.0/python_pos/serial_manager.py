from __future__ import annotations

import json
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


class SerialManager:
    """Wraps pyserial operations for the POS application."""

    def __init__(self) -> None:
        self.connection = None
        self._port_lookup: dict[str, str] = {}

    def list_available_ports(self) -> list[str]:
        if list_ports is None:
            return []

        self._port_lookup.clear()
        port_labels: list[str] = []
        for port in list_ports.comports():
            label = f"{port.device} - {port.description}"
            self._port_lookup[label] = port.device
            port_labels.append(label)
        return port_labels

    def connect(self, port_selection: str, baudrate: int = 115200, timeout: float = 3.0) -> tuple[bool, str]:
        if serial is None:
            return False, "pyserial is not installed. Please install the Python requirements first."

        if not port_selection.strip():
            return False, "Select a serial port before connecting."

        port_name = self._resolve_port_name(port_selection)

        try:
            if self.connection and self.connection.is_open:
                self.connection.close()

            self.connection = serial.Serial(port=port_name, baudrate=baudrate, timeout=timeout)
            time.sleep(2)
            return True, f"Connected to {port_name} at {baudrate} baud."
        except serial.SerialException as error:
            self.connection = None
            return False, f"Unable to connect to {port_name}: {error}"

    def disconnect(self) -> tuple[bool, str]:
        if self.connection and self.connection.is_open:
            port_name = self.connection.port
            self.connection.close()
            self.connection = None
            return True, f"Disconnected from {port_name}."
        return True, "No serial device was connected."

    def is_connected(self) -> bool:
        return bool(self.connection and self.connection.is_open)

    def send_receipt_reference(self, payload: dict, timeout_seconds: float = 2.0) -> tuple[bool, str]:
        if not self.is_connected():
            return False, "Connect to the ESP32 before sending receipt data."

        message = json.dumps(payload, separators=(",", ":")) + "\n"

        try:
            self.connection.reset_input_buffer()
            self.connection.write(message.encode("utf-8"))
            self.connection.flush()
            # The FireBeetle/Arduino code doesn't send a JSON response back. 
            # We assume success if the serial write succeeds.
            return True, "Receipt data instantly beamed to the FireBeetle!"
        except serial.SerialException as error:
            return False, f"Serial send failed: {error}"

    def _resolve_port_name(self, port_selection: str) -> str:
        if port_selection in self._port_lookup:
            return self._port_lookup[port_selection]
        return port_selection.split(" - ", maxsplit=1)[0].strip()

    def _interpret_response(self, response: str) -> tuple[bool, str] | None:
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            lowered = response.lower()
            if "error" in lowered or "failed" in lowered:
                return False, response
            return None

        status = str(parsed.get("status", "")).lower()
        message = str(parsed.get("message", response))
        if status in {"ok", "success"}:
            return True, message
        if status in {"error", "failed"}:
            return False, message
        return None
