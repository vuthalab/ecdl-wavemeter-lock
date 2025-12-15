import time
from typing import Literal

from heros import LocalHERO

from thorlabs_mdt693b import ThorlabsMDT693B


NAME = "piezo_control"


class PiezoControl(LocalHERO, ThorlabsMDT693B):
    """Laser piezo control."""
    def __init__(self, address: str):
        self._channels = ["x", "y", "z"]
        ThorlabsMDT693B.__init__(self, address)
        self._setup()
        LocalHERO.__init__(self, name=NAME)
        print(f"{NAME} server running now...")

    def _setup(self):
        self._global_max = self.get_voltage_limit()
        self._channel_mins = {}
        self._channel_maxs = {}
        for channel in self._channels:
            self._channel_mins[channel] = self.get_min_voltage(channel)
            self._channel_maxs[channel] = self.get_max_voltage(channel)

    @property
    def channel_ranges(self) -> dict[str, tuple[float, float]]:
        ranges = {}
        for channel in self._channels:
            min_value = self._channel_mins[channel]
            max_value = self._channel_maxs[channel]
            if max_value > self._global_max:
                max_value = self._global_max
            ranges[channel] = (min_value, max_value)
        return ranges

    def _check_in_range(self, channel: Literal["x", "y", "z"], voltage: float) -> float:
        min_value, max_value = self.channel_ranges[channel]
        if voltage < min_value:
            return min_value
        if voltage > max_value:
            return max_value
        return voltage

    def set_voltage(self, channel: Literal["x", "y", "z"], voltage: float):
        super().set_voltage(channel, self._check_in_range(channel, voltage))

    def change_voltage(self, channel: Literal["x", "y", "z"], voltage_change: float):
        current_output = self.get_voltage(channel)
        self.set_voltage(current_output + voltage_change)


if __name__ == "__main__":
    address = "COM21"

    try:
        with PiezoControl(address) as obj:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
