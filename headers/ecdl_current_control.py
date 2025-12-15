import time
from typing import Literal

from heros import LocalHERO

from rigol_dg1000z import RigolDG1000z


NAME = "ecdl_current_control"
CHANNELS = [1]


class ECDLCurrentControl(LocalHERO, RigolDG1000z):
    """Laser diode current control using DG1000z.
    
    Connect its outputs to Thorlabs LDC laser controllers analog mod ports
    to realize controlling the output current.
    """
    def __init__(self, address: str, protocol: Literal["Ethernet", "USB"] = "Ethernet"):
        RigolDG1000z.__init__(self, address, protocol)
        self._active_channels = CHANNELS
        self._setup()
        LocalHERO.__init__(self, name=NAME)
        print(f"{NAME} server is running now...")

    def _setup(self):
        for channel in self._active_channels:
            if self.get_function(channel) != "DC":
                self.set_offset_voltage(channel, 0)
                self.set_function(channel, "DC")
            self.set_state(channel, True)

    def set_output(self, channel: int, voltage: float):
        if channel in self._active_channels:
            if voltage > 10:
                voltage = 10
            elif voltage < -10:
                voltage = -10
            self.set_offset_voltage(channel, voltage)
        else:
            raise ValueError(f"Channel {channel} is not allowed.")

    def get_output(self, channel: int) -> float:
        if channel in self._active_channels:
            return self.get_offset_voltage(channel)
        else:
            raise ValueError(f"Channel {channel} is not allowed.")

    def change_output(self, channel: int, voltage_change: float) -> float:
        current_output = self.get_output(channel)
        self.set_output(channel, current_output + voltage_change)
        return self.get_output(channel)


if __name__ == "__main__":
    address = "USB0::0x1AB1::0x0642::DG1ZA175203648::INSTR"

    try:
        with ECDLCurrentControl(address, protocol="USB") as obj:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
