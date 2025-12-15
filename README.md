# ecdl-wavemeter-lock
Resilient wavemeter lock for ECDLs

This repo contains code for a low-speed (slower than 100 Hz) feedback loop running on a computer to stabilize optical frequency of a ECDL to a wavemeter. 
It features current biasing to extend the mode hop free tuning range, and it can auto-relock if the laser mode hops.
It does not use the servo included in the wavemeter.
A GUI client is included to quickly change lock parameters.

The code uses [`heros`](https://gitlab.com/atomiq-project/heros) for async communication between different devices and the client. Use `pip install heros` to install it.
If you need to control this wavemeter lock through Python (not through the included GUI), you may want to look into `heros`.
I selected to use `heros` for its simplicity and async capability. `heros` is still in currently beta (0.8.6 as I write this post), so it is possible that code needs to be changed to be compatible with future releases.

### The hardware setup is:
* An ECDL with wavemeter connection (High Finesse WS8 used here).
* ECDL current is controlled by a Thorlabs LDC201CU. This device does not have digital control. Therefore, its modulation channel is connected to a Rigol DG1032z function generator, which is controlled by a computer.
* ECDL piezo voltage is controlled by a Thorlabs MTB693B. This device is controlled by a computer.
* In general, the wavemeter, the current controller, and the piezo controller can be replaced by other models, with corresponding change in the code.

## How to use it:
* Make the hardware connections as mentioned above.
* Download the code to your computer.
* Copy `headers/wm_lock_422.py` and name it as you like. This is the "server" of your wavemeter lock.
* Copy `headers/wm_lock_422.py` and name it as you like. This is the "server" of your wavemeter lock.
* Edit the `WMLockConfig422` class in the copied file (see the `How to edit config` section below)
* In `if __name__ == "__main__":` block of the copied file, set `"wm_lock_422"` to the server name that you like.
* Copy `clients/wm_lock_422.py` and name it as you like. This is the "client" of your wavemeter lock.
* In the copied client file, edit `"wm_lock_422"` to match your server name.
* Run the following commands (each command in a separate terminal):
```bash
python headers/ecdl_current_control.py  # it should show "ecdl_current_control server is running now..." if succeeded. The device address need to be updated.
python headers/piezo_control.py  # it should show "piezo_control server is running now..." if succeeded. The device address need to be updated.
python headers/wm_lock_422.py  # replace it with the server file that you copied. It should show "wm_lock_422 server is running now..." if succeeded.
python clients/wm_lock_422.py  # replace it with the client file that you copied. It should show a PyQt GUI.
```
* In the GUI, you can adjust the PI parameters to optimize the lock.

### How to edit config:
The config class sets up all (default) information of the lock.

`add_wm_config` includes the wavemeter port number, frequency setpoint, and mode hop free range. If the laser is outside of the mode hop free tuning range when locked, it will attempt to adjust current / piezo to relock.

`add_current_config` includes the current controller config. It includes the function generator channel that is connected to the controller modulation port, the Thorlabs controller maximum range (used to convert voltage to diode current), maximum tuning range that is allowed, attenuation factor between the function generator to the current controller (allows adding a voltage divider if precise control of current is needed), and current bias slope (set it to zero if you do not know what this should be).

`add_piezo_config` includes the piezo controller port, min and max voltage allowed.

`add_feedback_config` includes the default gain, integral time, and a maximum time step for integrating. The maximum time step prevents large changes to the piezo if the wavemeter value cannot be read for a long time (e.g. due to under/over exposure).

### Determine the current bias slope
Before locking, I recommend to determine the current bias slope first. This usually helps with lock stablity. First, use the piezo and current controls in the GUI to adjust the laser to near the desired lockpoint.
Then measure the mode hop free tuning range (adjust piezo only, see the maximum wavemeter frequency range before the laser mode hops).
Repeat this measurement for different current bias slope (`bias_slope_mA_per_V` in the config). Note that the server and client should be restarted after each config change.
Finally, find the slope with the largest mode hop free tuning range, and set it in the config.

