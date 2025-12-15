import time
import threading

from heros import RemoteHERO
import numpy as np
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QGridLayout,
    QLabel,
    QPushButton,
    QDoubleSpinBox,
)
from PyQt5.QtGui import QFont


class WMLockClient(QMainWindow):
    def __init__(self, server):
        super().__init__()
        self._info = {
            "freq_GHz": None,
            "wm_good": None,
            "error_GHz": None,
            "feedback_output": None,
            "mode_hopped": False,
        }
        self._setup_gui()
        
        self.server = server
        self.server.wm_freq_changed.connect(self._update_info_and_label)
        self.server.lock_updated.connect(self._update_info_and_label)
        self.server.output_updated.connect(self._update_piezo_and_current)
        
        freq_setpoint = self.server.get_frequency_setpoint()
        self._lock_point_box.blockSignals(True)
        self._lock_point_box.setValue(freq_setpoint)
        self._lock_point_box.blockSignals(False)
        
        p_gain = self.server.get_p_gain()
        self._p_gain_box.blockSignals(True)
        self._p_gain_box.setValue(p_gain)
        self._p_gain_box.blockSignals(False)
        
        i_time = self.server.get_i_time()
        self._i_time_box.blockSignals(True)
        self._i_time_box.setValue(i_time)
        self._i_time_box.blockSignals(False)
        
        piezo_output = self.server.get_piezo_output()
        self._piezo_output_box.blockSignals(True)
        self._piezo_output_box.setValue(piezo_output)
        self._piezo_output_box.blockSignals(False)
        
        current_output = self.server.get_current_output()
        self._current_offset_box.blockSignals(True)
        self._current_offset_box.setValue(current_output)
        self._current_offset_box.blockSignals(False)
        
        lock_state = self.server.get_lock_state()
        if lock_state:
            self._lock_button.blockSignals(True)
            self._lock_button.setChecked(True)
            self._lock_button.blockSignals(False)
            self._lock_button.setStyleSheet("QPushButton {color: red;}")
            self._lock_button.setText("Locked")
            self._piezo_output_box.setEnabled(False)
            self._current_offset_box.setEnabled(False)

    def _setup_gui(self):
        self.setWindowTitle("Wavemeter lock")
        widget = QWidget(self)
        self.setCentralWidget(widget)
        layout = QGridLayout(widget)
        
        self._label_font = QFont("Helvetica", 11)
        
        self._lock_button = QPushButton("Unlocked")
        self._lock_button.setCheckable(True)
        self._lock_button.toggled.connect(self._lock_button_toggled)
        layout.addWidget(self._lock_button, 0, 0, 1, 2)
        
        label = QLabel("WM lock point (GHz)")
        layout.addWidget(label, 1, 0)
        self._lock_point_box = QDoubleSpinBox()
        self._lock_point_box.setDecimals(3)
        self._lock_point_box.setMinimum(100000)
        self._lock_point_box.setMaximum(1000000)
        self._lock_point_box.setSingleStep(0.1)
        self._lock_point_box.valueChanged.connect(self._lock_point_box_valueChanged)
        layout.addWidget(self._lock_point_box, 1, 1)
        
        label = QLabel("P Gain (V / GHz)")
        layout.addWidget(label, 2, 0)
        self._p_gain_box = QDoubleSpinBox()
        self._p_gain_box.setMaximum(10)
        self._p_gain_box.setMinimum(-10)
        self._p_gain_box.setDecimals(3)
        self._p_gain_box.setSingleStep(0.1)
        self._p_gain_box.valueChanged.connect(self._p_gain_box_valueChanged)
        layout.addWidget(self._p_gain_box, 2, 1)
        
        label = QLabel("I Time (s)")
        layout.addWidget(label, 3, 0)
        self._i_time_box = QDoubleSpinBox()
        self._i_time_box.setDecimals(2)
        self._i_time_box.setMinimum(0)
        self._i_time_box.valueChanged.connect(self._i_time_box_valueChanged)
        layout.addWidget(self._i_time_box, 3, 1)
        
        label = QLabel("Piezo output (V)")
        layout.addWidget(label, 4, 0)
        self._piezo_output_box = QDoubleSpinBox()
        self._piezo_output_box.setMaximum(150)
        self._piezo_output_box.setSingleStep(0.1)
        self._piezo_output_box.setMinimum(0)
        self._piezo_output_box.setDecimals(3)
        self._piezo_output_box.valueChanged.connect(self._piezo_output_box_valueChanged)
        layout.addWidget(self._piezo_output_box, 4, 1)
        
        label = QLabel("Current offset (mA)")
        layout.addWidget(label, 5, 0)
        self._current_offset_box = QDoubleSpinBox()
        self._current_offset_box.setDecimals(3)
        self._current_offset_box.setSingleStep(0.01)
        self._current_offset_box.setMinimum(-10)
        self._current_offset_box.setMaximum(10)
        self._current_offset_box.valueChanged.connect(self._current_offset_box_valueChanged)
        layout.addWidget(self._current_offset_box, 5, 1)
        
        self._info_label = QLabel()
        self._info_label.setFont(self._label_font)
        layout.addWidget(self._info_label, 0, 2, 4, 1)

    def _lock_button_toggled(self, state):
        if state:
            self._lock_button.setStyleSheet("QPushButton {color: red;}")
            self._lock_button.setText("Locked")
            self._piezo_output_box.setEnabled(False)
            self._current_offset_box.setEnabled(False)
        else:
            self._lock_button.setStyleSheet("QPushButton {}")
            self._lock_button.setText("Unlocked")
            self._piezo_output_box.setEnabled(True)
            self._current_offset_box.setEnabled(True)
        self.server.set_lock_state(state)

    def _lock_point_box_valueChanged(self, value):
        self.server.set_frequency_setpoint(value)

    def _p_gain_box_valueChanged(self, value):
        self.server.set_p_gain(value)

    def _i_time_box_valueChanged(self, value):
        self.server.set_i_time(value)

    def _piezo_output_box_valueChanged(self, value):
        self.server.set_piezo_output(value)

    def _current_offset_box_valueChanged(self, value):
        self.server.set_current_output(value)

    def _update_info_and_label(self, value):
        self._info.update(value)
        self._update_label()

    def _update_label(self):
        text = ""
        if self._info['wm_good']:
            text += f"WM frequency: {self._info['freq_GHz']:.3f} GHz\n"
        else:
            text += f"Wavemeter has an error.\n"
        text += "Lock parameters:\n"
        text += f"  Mode hopped: {self._info['mode_hopped']}\n"
        if self._info['error_GHz'] is not None:
            text += f"  Error: {self._info['error_GHz']:.3f} GHz\n"
        if self._info['feedback_output'] is not None:
            text += f"  Control: {self._info['feedback_output']:.3f} V\n"
        self._info_label.setText(text)

    def _update_piezo_and_current(self, value):        
        piezo_output = value["piezo_output"]
        self._piezo_output_box.blockSignals(True)
        self._piezo_output_box.setValue(piezo_output)
        self._piezo_output_box.blockSignals(False)
              
        current_output = value["current_output"]
        self._current_offset_box.blockSignals(True)
        self._current_offset_box.setValue(current_output)
        self._current_offset_box.blockSignals(False)
