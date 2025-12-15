import time
import threading
from typing import Literal

from heros import LocalHERO, event, RemoteHERO
import numpy as np

from wavemeter.wavemeter import WM


class WMLockConfig:
    def __init__(self):
        self._config = {}

    def add_wm_config(self, wm_port: int, freq_setpoint_GHz: float, mode_hop_range_GHz: float):
        self._config["wm"] = {"wm_port": wm_port, "freq_setpoint_GHz": freq_setpoint_GHz, "mode_hop_range_GHz": mode_hop_range_GHz}

    def add_current_config(
        self,
        channel: Literal[1, 2],
        max_controller_range_mA: float,
        max_tuning_range_mA: float,
        attenuation_factor: float = 1,
        bias_slope_mA_per_V: float = 0,
    ):
        """
        Args:
            channel: function generator channel modulating the current control.
            max_controller_range_mA: max current range of the diode controller.
            max_tuning_range_mA: max current tuning range. If the range is 5 mA, and the front
                panel setpoint is 100 mA. Then the tuning range is 95 to 105 mA.
            attenuation_factor: attenuation from the function generator to the modulation port.
                For example, if a 10:1 voltage divider is used, this factor should be set to 10.
                Default 1 (no attenuation).
            bias_slope_mA_per_V: current bias given piezo voltage applied.
        """
        self._config["current"] = {
            "channel": channel,
            "max_controller_range_mA": max_controller_range_mA,
            "max_tuning_range_mA": max_tuning_range_mA,
            "attenuation_factor": attenuation_factor,
            "bias_slope_mA_per_V": bias_slope_mA_per_V,
        }

    def add_piezo_config(self, axis: Literal["x", "y", "z"], min_voltage: float = 0, max_voltage: float = 150):
        self._config["piezo"] = {"axis": axis, "min_voltage": min_voltage, "max_voltage": max_voltage}

    def add_feedback_config(self, p_gain: float, i_time: float, max_integral_time_step: float = 1):
        """
        Args:
            p_gain: unit is V / GHz. Conversion from frequency offset to piezo voltage change.
            i_time: integral term time constant in s.
        """
        self._config["feedback"] = {"p_gain": p_gain, "i_time": i_time, "max_integral_time_step": max_integral_time_step}

    @property
    def data(self):
        if "wm" not in self._config or "current" not in self._config or "piezo" not in self._config or "feedback" not in self._config:
            raise Exception("Must define all components first.")
        return self._config


class WMLock(LocalHERO):
    """Wavemeter lock using ECDLCurrentControl and PiezoControl.
    
    It does not use the build-in PID of the HighFinesse wavemeter.
    """

    def __init__(self, config: WMLockConfig, name: str):
        self.wm = WM()
        self.config = config.data
        self._t1 = None
        self._stop = threading.Event()
        self._t2 = None
        LocalHERO.__init__(self, name)
        print(f"{name} server is running now...")

    def __enter__(self):
        super().__enter__()
        self.current = RemoteHERO("ecdl_current_control").__enter__()
        self.piezo = RemoteHERO("piezo_control").__enter__()
        self._setup_wm()
        self._setup_piezo_controller()
        self._setup_current_controller()
        self._setup_feedback_params()
        self._t1 = threading.Thread(target=self._feedback_loop, daemon=True)
        self._t1.start()
        self._t2 = threading.Thread(target=self._update_loop, daemon=True)
        self._t2.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._stop.set()
            if self._t1 is not None:
                self._t1.join(timeout=2)
            if self._t2 is not None:
                self._t2.join(timeout=2)
            self.current.__exit__(exc_type, exc, tb)
            self.piezo.__exit__(exc_type, exc, tb)
        finally:
            return super().__exit__(exc_type, exc, tb)

    # device setup
    def _setup_piezo_controller(self):
        channel = self.config["piezo"]["axis"]
        self.piezo.set_min_voltage(channel, self.config["piezo"]["min_voltage"])
        self.piezo.set_max_voltage(channel, self.config["piezo"]["max_voltage"])
        self._piezo_range = self.piezo.channel_ranges[channel]
        self._piezo_offset = self.piezo.get_voltage(channel)
        self._piezo_railed = False
        self._piezo_output = self._piezo_offset

    def _voltage_offset_to_current_offset(self, voltage: float) -> float:
        """Function generator voltage to laser diode current."""
        current_config = self.config["current"]
        return current_config["max_controller_range_mA"] * (voltage / current_config["attenuation_factor"] / 10)

    def _current_offset_to_voltage_offset(self, current: float) -> float:
        """Laser diode current to function generator voltage."""
        current_config = self.config["current"]
        return (current / current_config["max_controller_range_mA"]) * (10 * current_config["attenuation_factor"])

    def _setup_current_controller(self):
        channel = self.config["current"]["channel"]
        self._current_max_tuning_range = self.config["current"]["max_tuning_range_mA"]
        self._current_bias_slope = self.config["current"]["bias_slope_mA_per_V"]
        self._current_offset = self._voltage_offset_to_current_offset(self.current.get_output(channel))
        self._current_railed = False
        self._current_output = self._current_offset

    def _setup_wm(self):
        self._wm_port = self.config["wm"]["wm_port"]
        self._freq_setpoint_GHz = self.config["wm"]["freq_setpoint_GHz"]
        self._mode_hop_range_GHz = self.config["wm"]["mode_hop_range_GHz"]
        self._last_freq_GHz = None
        self._mode_hopped = False
        self._error_GHz = None

    def _setup_feedback_params(self):
        self._p_gain = self.config["feedback"]["p_gain"]
        self._i_time = self.config["feedback"]["i_time"]
        self._max_integral_time_step = self.config["feedback"]["max_integral_time_step"]
        self._feedback_output = 0
        self._integral = 0
        self._last_integral_time = None
        self._lock_on = False
        self._wm_good = False

    # feedback
    def _get_frequency_GHz(self):
        freq_GHz = self.wm.read_frequency(self._wm_port)
        if isinstance(freq_GHz, (float, int)) and freq_GHz > 0:
            return (freq_GHz, None)
        else:
            return (0, freq_GHz)

    def _get_feedback_output(self, error_GHz):
        time_now = time.time()
        if self._last_integral_time is None:
            integral_time_step = 0
        else:
            integral_time_step = time_now - self._last_integral_time
        if integral_time_step > self._max_integral_time_step:
            integral_time_step = self._max_integral_time_step
        self._last_integral_time = time_now

        p_term = error_GHz * self._p_gain
        i_term_change = error_GHz * self._p_gain * integral_time_step / self._i_time
        self._integral += i_term_change
        return p_term + self._integral

    def _set_piezo_output(self, output):
        if output < self._piezo_range[0]:
            self._piezo_railed = True
            output = self._piezo_range[0]
            min_integral = output - self._piezo_offset
            if self._lock_on and self._integral < min_integral:
                self._integral = min_integral
        elif output > self._piezo_range[1]:
            self._piezo_railed = True
            output = self._piezo_range[1]
            max_integral = output - self._piezo_offset
            if self._lock_on and self._integral > max_integral:
                self._integral = max_integral
        else:
            self._piezo_railed = False
        self.piezo.set_voltage(self.config["piezo"]["axis"], output)
        return output

    def _update_piezo(self, feedback_output):
        desired_output = feedback_output + self._piezo_offset
        return self._set_piezo_output(desired_output)

    def _set_current_output(self, output):
        if output < -self._current_max_tuning_range:
            self._current_railed = True
            output = -self._current_max_tuning_range
        elif output > self._current_max_tuning_range:
            self._current_railed = True
            output = self._current_max_tuning_range
        else:
            self._current_railed = False
        func_gen_voltage = self._current_offset_to_voltage_offset(output)
        self.current.set_output(self.config["current"]["channel"], func_gen_voltage)
        return output

    def _update_current(self, feedback_output):
        desired_current = feedback_output * self._current_bias_slope + self._current_offset
        return self._set_current_output(desired_current)

    def _get_next_frequency(self):
        distinct_output = False
        while not distinct_output:
            self._stop.wait(0.01)
            freq_GHz, self._error = self._get_frequency_GHz()
            if freq_GHz > 0:
                self._wm_good = True
            else:
                self._wm_good = False
            distinct_output = freq_GHz != self._last_freq_GHz
            self._last_freq_GHz = freq_GHz
        return self._last_freq_GHz

    def _feedback_loop(self):
        while not self._stop.is_set():
            self._get_next_frequency()

            if not self._wm_good:
                print(f"Wavemeter error: {self._error}")
                continue
            if self._lock_on:
                self._error_GHz = self._last_freq_GHz - self._freq_setpoint_GHz
                if np.abs(self._error_GHz) < self._mode_hop_range_GHz:
                    self._mode_hopped = False
                    self._feedback_output = self._get_feedback_output(self._error_GHz)
                    self._piezo_output = self._update_piezo(self._feedback_output)
                    if self._current_bias_slope != 0:
                        self._current_output = self._update_current(self._feedback_output)
                else:
                    self._mode_hopped = True
                    currents_to_test = np.arange(0.1, 1, 0.05)
                    currents_to_test = np.array([currents_to_test, -currents_to_test]).flatten(order="F")
                    voltages_to_test = np.arange(0, 5, 0.5)
                    voltages_to_test = np.array([voltages_to_test, -voltages_to_test]).flatten(order="F")
                    voltage_index = 0
                    current_index = 0
                    self._update_piezo_and_current_offsets(skip_lock_on=True)
                    relocked = np.abs(self._error_GHz) < self._mode_hop_range_GHz
                    while not relocked and self._lock_on and not self._stop.is_set():
                        if current_index == len(currents_to_test):
                            current_index = 0
                            voltage_index += 1
                            if voltage_index == len(voltages_to_test):
                                voltage_index = 0
                            self.set_piezo_output(
                                self._piezo_offset + voltages_to_test[voltage_index],
                                update_current_bias=False,
                                skip_lock_on=True,
                            )
                        self.set_current_output(
                            self._current_offset + currents_to_test[current_index],
                            skip_lock_on=True,
                        )
                        self._get_next_frequency()  # throw a previously collected frequency.
                        self._get_next_frequency()
                        while not self._wm_good and self._lock_on and not self._stop.is_set():
                            self._get_next_frequency()
                        self._error_GHz = self._last_freq_GHz - self._freq_setpoint_GHz
                        relocked = np.abs(self._error_GHz) < self._mode_hop_range_GHz
                        current_index += 1
                    if relocked:
                        self._last_integral_time = None
                        self._integral = 0
                        self._feedback_output = 0
                        self._mode_hopped = False
                        self._update_piezo_and_current_offsets(skip_lock_on=True)
                    else:
                        self.set_piezo_output(self._piezo_offset, update_current_bias=False)
                        self.set_current_output(self._current_offset)
                        self._update_piezo_and_current_offsets()
                    # TODO: relock routine

    def get_lock_state(self):
        return self._lock_on

    def set_lock_state(self, state):
        if state:
            self._update_piezo_and_current_offsets()
            self._lock_on = True
        else:
            self._lock_on = False
            self._last_integral_time = None
            self._integral = 0
            self._feedback_output = 0
            self._error_GHz = None

    def _update_piezo_and_current_offsets(self, skip_lock_on = False):
        if self._lock_on and not skip_lock_on:
            return
        self._current_offset = self._voltage_offset_to_current_offset(
            self.current.get_output(self.config["current"]["channel"])
        )
        self._current_output = self._current_offset
        self._piezo_offset = self.piezo.get_voltage(self.config["piezo"]["axis"])
        self._piezo_output = self._piezo_offset

    def get_piezo_output(self):
        return self._piezo_output

    def set_piezo_output(self, output, update_current_bias = True, skip_lock_on = False):
        if self._lock_on and not skip_lock_on:
            return
        self._piezo_output = self._set_piezo_output(output)
        if update_current_bias:
            offset = output - self._piezo_offset
            self._current_output = self._update_current(offset)

    def get_current_output(self):
        return self._current_output

    def set_current_output(self, output, skip_lock_on = False):
        if self._lock_on and not skip_lock_on:
            return
        self._current_output = self._set_current_output(output)

    def get_p_gain(self):
        return self._p_gain

    def set_p_gain(self, value):
        self._p_gain = value

    def get_i_time(self):
        return self._i_time

    def set_i_time(self, value):
        self._i_time = value

    def get_frequency_setpoint(self):
        return self._freq_setpoint_GHz

    def set_frequency_setpoint(self, value):
        self._freq_setpoint_GHz = value

    # update / streaming
    @event
    def wm_freq_changed(self, value):
        return value
    
    @event
    def lock_updated(self, value):
        return value
    
    @event
    def output_updated(self, value):
        return value
    
    def _update_loop(self):
        previous_freq_GHz = None
        previous_error_GHz = None
        previous_piezo_output = None
        previous_current_output = None
        while not self._stop.is_set():
            self._stop.wait(0.1)
            if self._last_freq_GHz != previous_freq_GHz:
                self.wm_freq_changed(
                    {
                        "freq_GHz": self._last_freq_GHz,
                        "wm_good": self._wm_good,
                    }
                )
                previous_freq_GHz = self._last_freq_GHz

            if self._error_GHz != previous_error_GHz:
                self.lock_updated(
                    {
                        "error_GHz": self._error_GHz,
                        "feedback_output": self._feedback_output,
                        "mode_hopped": self._mode_hopped,
                    }
                )
                previous_error_GHz = self._error_GHz
            elif (
                self._piezo_output != previous_piezo_output
                or self._current_output != previous_current_output
            ):
                self.output_updated(
                    {
                        "piezo_output": self._piezo_output,
                        "current_output": self._current_output,
                        "piezo_railed": self._piezo_railed,
                        "current_railed": self._current_railed,
                    }
                )
                previous_piezo_output = self._piezo_output
                previous_current_output = self._current_output
