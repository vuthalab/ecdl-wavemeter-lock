import threading
import time

from wm_lock import WMLock, WMLockConfig


class WMLockConfig422(WMLockConfig):
    def __init__(self):
        super().__init__()
        self.add_wm_config(
            wm_port=3,
            freq_setpoint_GHz=710962.7,
            mode_hop_range_GHz=3,
        )
        self.add_current_config(
            channel=1,
            max_controller_range_mA=100,
            max_tuning_range_mA=10,
            attenuation_factor=1,
            bias_slope_mA_per_V=-0.2,  # tested to maximize the mode hop free tuning range (~3.4 GHz now).
        )
        self.add_piezo_config(
            axis="y",
            min_voltage=0,
            max_voltage=75,
        )
        self.add_feedback_config(
            p_gain=-0.5,
            i_time=1,
            max_integral_time_step=1,
        )


if __name__ == "__main__":
    try:
        with WMLock(WMLockConfig422(), "wm_lock_422") as obj:
            while True:
                time.sleep(1e-3)
    except KeyboardInterrupt:
        pass
