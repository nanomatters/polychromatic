# Polychromatic is licensed under the GPLv3.
# Copyright (C) 2020-2023 Luke Horwell <code@horwell.me>
"""
This module controls the 'Laptop' tab of the Controller GUI.
"""

from polychromatic.procpid import DeviceSoftwareState
from .. import bulkapply
from .. import common
from .. import effects
from .. import locales
from .. import preferences as pref
from .. import middleman
from . import shared
from ..backends._backend import Backend as Backend
from ..qt.flowlayout import FlowLayout as QFlowLayout

import os
import subprocess
import time
import shutil
import webbrowser
import cpuinfo

from PyQt5.QtCore import Qt, QSize, QMargins, QThread
from PyQt5.QtGui import QIcon, QPixmap, QFont
from PyQt5.QtWidgets import QWidget, QDialogButtonBox, QGroupBox, QGridLayout, \
                            QPushButton, QToolButton, QMessageBox, QListWidget, \
                            QTreeWidget, QTreeWidgetItem, QLabel, QComboBox, \
                            QSpacerItem, QSizePolicy, QSlider, QCheckBox, \
                            QButtonGroup, QRadioButton, QDialog, QTableWidget, \
                            QTableWidgetItem, QAction, QHBoxLayout

# Error codes
ERROR_NO_DEVICE = 0
ERROR_BACKEND_IMPORT = 1
ERROR_NO_BACKEND = 2


class LaptopTab(shared.TabData):
    """
    Allows the user to quickly change the existing state of the device right now.
    """
    def __init__(self, appdata):
        super().__init__(appdata)

        # Session
        self.current_device = None
        self.load_thread = None

        # Useful complimentary software
        self.input_remapper = shutil.which("input-remapper-gtk")

        self.has_silent = True
        self.has_balanced = True
        self.has_custom = True

        self.performance_state = "silent"
        self.cpu_state = "low"
        self.gpu_state = "low"

        # UI Elements
        self.UndervoltContents = self.main_window.findChild(QWidget, "UndervoltContents")
        self.SystemContents = self.main_window.findChild(QWidget, "SystemContents")
        self.UndervoltingGroup = self.widgets.create_group_widget("CPU Undervolting (" + cpuinfo.get_cpu_info()['brand'] + ")")
        self.PowerLimitGroup = self.widgets.create_group_widget("System Power Limit Control")
        self.PowerProfileGroup = self.widgets.create_group_widget("Power Profile Control")
        self.FanGroup = self.widgets.create_group_widget("Fan Control")
        self.BatteryGroup = self.widgets.create_group_widget("Battery Control")

        # Avoid garbage collection cleaning up invisible controls
        self.btn_grps = {}

        self._create_voltage_slider("Core Offset")
        self._create_voltage_slider("Cache Offset")
        self._create_voltage_slider("iGPU Offset")
        self._create_voltage_slider("System Agent Offset")
        self._create_voltage_slider("Analog I/O Offset")

        self._create_pl_slider("PL1")
        self._create_pl_slider("PL2")

        self.BtnContainer = QWidget()
        self.BtnContainer.setLayout(QHBoxLayout())
        self.BtnContainer.layout().setContentsMargins(0, 0, 0, 0)

        btn = QPushButton(objectName="ApplyButton")
        btn.setText("Apply")
        self.BtnContainer.layout().addWidget(btn)
        btn = QPushButton(objectName="LoadButton")
        btn.setText("Load")
        self.BtnContainer.layout().addWidget(btn)
        btn = QPushButton(objectName="SaveButton")
        btn.setText("Save")
        self.BtnContainer.layout().addWidget(btn)
        btn = QPushButton(objectName="ResetButton")
        btn.setText("Reset")
        self.BtnContainer.layout().addWidget(btn)

        self.UndervoltContents.layout().addWidget(self.UndervoltingGroup)
        self.UndervoltContents.layout().addWidget(self.PowerLimitGroup)
        self.UndervoltContents.layout().addWidget(self.BtnContainer)
        self.SystemContents.layout().addWidget(self.PowerProfileGroup)
        self.SystemContents.layout().addWidget(self.FanGroup)
        self.SystemContents.layout().addWidget(self.BatteryGroup)

        self._create_button_control_group(self._get_system_performance_options(self), "System Mode", self.PowerProfileGroup)
        self._create_button_control_group(self._get_cpu_performance_options(self), "CPU Mode", self.PowerProfileGroup)
        self._create_button_control_group(self._get_gpu_performance_options(self), "GPU Mode", self.PowerProfileGroup)

        self._create_fan_controls();
        self._create_battery_controls();

    def apply_performance(self):
        return True;

    def _get_system_performance_options(self, parent):
        options = []

        if self.has_silent:
            class Option(Backend.EffectOption):
                def __init__(self, parent):
                    super().__init__()
                    self.uid = "silent"
                    self._parent = parent

                def refresh(self):
                    self.active = True if self._parent.performance_state == "silent" else False

                def apply(self, param=None):
                    self._parent.performance_state = "silent"

            option = Option(self)
            option.label = self._("Silent")
            # option.icon = self.get_icon("options", "none")
            options.append(option)

        if self.has_balanced:
            class Option(Backend.EffectOption):
                def __init__(self, parent):
                    super().__init__()
                    self.uid = "balanced"
                    self._parent = parent

                def refresh(self):
                    self.active = True if self._parent.performance_state == "balanced" else False

                def apply(self, param=None):
                    self._parent.performance_state = "balanced"

            option = Option(self)
            option.label = self._("Balanced")
            # option.icon = self.get_icon("options", "none")
            options.append(option)

        if self.has_custom:
            class Option(Backend.EffectOption):
                def __init__(self, parent):
                    super().__init__()
                    self.uid = "boost"
                    self._parent = parent

                def refresh(self):
                    self.active = True if self._parent.performance_state == "custom" else False

                def apply(self, param=None):
                    self._parent.performance_state = "custom"

            option = Option(self)
            option.label = self._("Custom")
            # option.icon = self.get_icon("options", "none")
            options.append(option)

            return options

    def _get_cpu_performance_options(self, parent):
        options = []

        class Option(Backend.EffectOption):
            def __init__(self, parent, uid):
                super().__init__()
                self.uid = uid
                self.label = parent._(uid)
                self._parent = parent

            def refresh(self):
                self.active = True if self._parent.performance_state == self.uid else False

            def apply(self, param=None):
                self._parent.performance_state = self.uid

        options.append(Option(self, "Low"))
        options.append(Option(self, "Mid"))
        options.append(Option(self, "High"))
        options.append(Option(self, "Boost"))

        return options

    def _get_gpu_performance_options(self, parent):
        options = []

        class Option(Backend.EffectOption):
            def __init__(self, parent, uid):
                super().__init__()
                self.uid = uid
                self.label = parent._(uid)
                self._parent = parent

            def refresh(self):
                self.active = True if self._parent.performance_state == self.uid else False

            def apply(self, param=None):
                self._parent.performance_state = self.uid

        options.append(Option(self, "Low"))
        options.append(Option(self, "Mid"))
        options.append(Option(self, "High"))

        return options

    def _create_button_control_group(self, options, name, group):
        """
        Return a row widget containing the specified options. These are grouped
        together and will be presented as larger buttons.
        """
        self.btn_grps[name] = QButtonGroup()
        widgets = []

        for option in options:
            button = QToolButton()
            button.setText(option.label)
            button.setCheckable(True)
            button.setIconSize(QSize(40, 40))
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            if option.icon:
                button.setIcon(QIcon(option.icon))
            button.setMinimumHeight(50)
            button.setMinimumWidth(85)
            button.option = option
            self.btn_grps[name].addButton(button)

            if option.active:
                button.setChecked(True)

            widgets.append(button)

        widget = self.widgets.create_row_widget(self._(name), widgets, labelOffset=50)
        return group.layout().addWidget(widget)

    def set_tab(self):
        """
        Device tab opened. Populate the device and task lists, and open the
        properties for the first device (if applicable)
        """
        self.set_title(self._("Blade Performance"))

    def _create_control_slider(self, option):
        """
        Returns a list of controls that make up a slider for changing a variable option.
        """
        slider = QSlider(Qt.Horizontal)
        slider.setValue(option.value)
        slider.setMinimum(option.min)
        slider.setMaximum(option.max)
        slider.setSingleStep(option.step)
        slider.setPageStep(option.step * 2)
        slider.setMaximumWidth(150)

        # BUG: Qt: Ticks don't appear with stylesheet
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(int(option.max / 10))

        label = QLabel()
        suffix = option.suffix if option.value == 1 else option.suffix_plural
        label.setText(str(option.value) + suffix)

        # Change label while sliding
        def _slider_moved(value):
            suffix = option.suffix if value == 1 else option.suffix_plural
            label.setText(str(value) + suffix)
        slider.sliderMoved.connect(_slider_moved)
        slider.valueChanged.connect(_slider_moved)

        # Send request once dropped
        def _slider_dropped():
            self.dbg.stdout(f"{self.current_device.name}: Applying option {option.uid} with value: {str(slider.value())}", self.dbg.action, 1)
            try:
                option.apply(slider.value())
            except Exception as e:
                self._catch_command_error(self.current_device, e)

        slider.sliderReleased.connect(_slider_dropped)
        slider.valueChanged.connect(_slider_dropped)

        return [slider, label]

    def _create_voltage_slider(self, tag):
        """
        Returns a Backend.Option derivative object based on the type of
        brightness for the specified zone and device.
        """
        class VoltageSlider(Backend.SliderOption):
            def __init__(self):
                super().__init__()
                self.uid = tag
                self.min = -200
                self.max = 0
                self.step = 1
                self.suffix = "mV"
                self.suffix_plural = "mV"
                self.voltage = 0;

            def refresh(self):
                self.value = int(round(self.voltage))

            def apply(self, new_value):
                self.voltage = float(new_value)

        slider = VoltageSlider()
        slider.label = self._(tag)
        # slider.icon = self.get_icon("options", "brightness")
        # [widget, label] = self._create_control_slider(slider)
        widget = self.widgets.create_row_widget(slider.label, self._create_control_slider(slider));
        return self.UndervoltingGroup.layout().addWidget(widget)

    def _create_pl_slider(self, tag):
        """
        Returns a Backend.Option derivative object based on the type of
        brightness for the specified zone and device.
        """
        class PowerSlider(Backend.SliderOption):
            def __init__(self):
                super().__init__()
                self.uid = tag
                self.min = 10
                self.max = 160
                self.step = 1
                self.suffix = "W"
                self.suffix_plural = "W"
                self._power = 130;

            def refresh(self):
                self.value = int(round(self._power))

            def apply(self, new_value):
                self._power = float(new_value)

        slider = PowerSlider()
        slider.label = self._(tag)
        widget = self.widgets.create_row_widget(slider.label, self._create_control_slider(slider));
        return self.PowerLimitGroup.layout().addWidget(widget)

    def _get_fan_control_options(self, parent):
        options = []

        class Option(Backend.EffectOption):
            def __init__(self, parent, uid):
                super().__init__()
                self.uid = uid
                self.label = parent._(uid)
                self._parent = parent

            def refresh(self):
                self.active = True if self._parent.fan_state == self.uid else False

            def apply(self, param=None):
                self._parent.fan_state = self.uid

        options.append(Option(self, "Auto"))
        options.append(Option(self, "Manual"))
        options.append(Option(self, "Max"))

        return options

    def _create_fan_controls(self):
        """
        Returns a Backend.Option derivative object based on the type of
        brightness for the specified zone and device.
        """
        self._create_button_control_group(self._get_fan_control_options(self), "Fan Mode", self.FanGroup)

        class FanSlider(Backend.SliderOption):
            def __init__(self):
                super().__init__()
                self.uid = "fanspeed"
                self.min = 1200
                self.max = 3800
                self.step = 1
                self.suffix = "RPM"
                self.suffix_plural = "RPMs"
                self._rpms = 1200;

            def refresh(self):
                self.value = int(round(self._rpms))

            def apply(self, new_value):
                self._rpms = float(new_value)

        slider = FanSlider()
        slider.label = self._("Fan Speed")
        # slider.icon = self.get_icon("options", "brightness")
        # [widget, label] = self._create_control_slider(slider)
        widget = self.widgets.create_row_widget(slider.label, self._create_control_slider(slider));
        self.FanGroup.layout().addWidget(widget)

    def _create_battery_controls(self):
        """
        Returns a Backend.Option derivative object based on the type of
        brightness for the specified zone and device.
        """
        class BatterySlider(Backend.SliderOption):
            def __init__(self):
                super().__init__()
                self.uid = "battery_charge_limit"
                self.min = 50
                self.max = 100
                self.step = 1
                self.suffix = "%"
                self.suffix_plural = "%"
                self._limit = 50;

            def refresh(self):
                self.value = int(round(self._limit))

            def apply(self, new_value):
                self._limit = float(new_value)

        slider = BatterySlider()
        slider.label = self._("Battery Charge Limit")
        # slider.icon = self.get_icon("options", "brightness")
        # [widget, label] = self._create_control_slider(slider)
        widget = self.widgets.create_row_widget(slider.label, self._create_control_slider(slider));
        self.BatteryGroup.layout().addWidget(widget)
