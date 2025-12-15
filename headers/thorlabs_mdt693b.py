from typing import Literal
import serial


class ThorlabsMDT693B:
    """Piezo controller.

    The code currently does not work. Needs to figure out the device's return values.
    """
    def __init__(self, address: str):
        self.device = serial.Serial(port=address, baudrate=115200, timeout=1)
        try:
            self.device.read_until(b">")
        except Exception:
            pass
        self.set_echo(False)

    def _write(self, command: str):
        self.device.write((command + "\n").encode("ascii"))
        read = self.device.read_until(b">").decode("ascii")[:-2]
        return read.strip("[] ")

    def set_echo(self, echo_on: bool):
        if echo_on:
            self._write("ECHO=1")
        else:
            self._write("ECHO=0")

    def get_voltage_limit(self):
        return float(self._write("vlimit?"))

    def get_voltage(self, axis: Literal["x", "y", "z"]) -> float:
        return float(self._write(f"{axis}voltage?"))

    def set_voltage(self, axis: Literal["x", "y", "z"], value: float):
        self._write(f"{axis}voltage={value}")

    def get_min_voltage(self, axis: Literal["x", "y", "z"]) -> float:
        return float(self._write(f"{axis}min?"))

    def set_min_voltage(self, axis: Literal["x", "y", "z"], value: float):
        self._write(f"{axis}min={value}")

    def get_max_voltage(self, axis: Literal["x", "y", "z"]) -> float:
        return float(self._write(f"{axis}max?"))

    def set_max_voltage(self, axis: Literal["x", "y", "z"], value: float):
        self._write(f"{axis}max={value}")
