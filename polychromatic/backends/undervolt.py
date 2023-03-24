#!/usr/bin/python3
#
# Polychromatic is licensed under the GPLv3.
# Copyright (C) 2017-2023 Luke Horwell <code@horwell.me>
#
"""
This module abstracts data from the OpenRazer Python library (and daemon)
and parses this for Polychromatic to use.

Project URL: https://github.com/openrazer/openrazer
"""
import glob
import os

import cpuinfo
from .. import common
from ._backend import Backend as Backend


class UndervoltBackend(Backend):
    """
    Integration with the OpenRazer 3.x Python library.

    Thoughout the module:
    - 'rdevice' refers to an openrazer.client.devices.RazerDevice object.
    - 'rzone' refers to an openrazer.client.fx.RazerFX (main) or
                           openrazer.client.fx.SingleLed object (e.g. logo)
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.backend_id = "undervolt"
        self.name = "UndervoltBackend"
        self.logo = "openrazer.svg"
        self.version = '0.0.0'
        self.project_url = "https://openrazer.github.io"
        self.bug_url = "https://github.com/openrazer/openrazer/issues"
        self.releases_url = "https://github.com/openrazer/openrazer/releases"
        self.license = "GPLv2"

        #print(cpuinfo.get_cpu_info()['brand'])
        self.load_client_overrides()

    def init(self):
        """
        Summons the OpenRazer DeviceManager() daemon.
        """
        #print(cpuinfo.get_cpu_info()['brand'])
        #print(cpuinfo.get_cpu_info()['vendor_id'])

        return True

    def load_client_overrides(self):
        """
        Load any user-defined client settings that Polychromatic should use
        interfacing with the daemon. These are stored as individual files inside
        ~/.config/polychromatic/backends/openrazer/
        """

    def get_unsupported_devices(self):
        """
        See Backend.get_unsupported_devices() and Backend.UnknownDeviceItem()

        Returns a list of PIDs of Razer hardware that is physically plugged in,
        but inaccessible by the daemon. Usually indicating the installation is
        incomplete or the device is not supported by the driver.
        """
        unreg_pids = []
        return unreg_pids

    def get_devices(self):
        """
        See Backend.get_devices() and Backend.DeviceItem()
        """
        devices = []

        # Device details
        class CpuDeviceItem(Backend.DeviceItem):
            def refresh(self):
                for zone in self.zones:
                    for option in zone.options:
                        option.refresh()

        device = CpuDeviceItem()
        device.name = str(cpuinfo.get_cpu_info()['brand'])
        device.form_factor = "cpu"
        device.real_image = ""
        device.serial = ""
        # devices.append(device)

        return devices

    def get_device_by_name(self, name):
        """
        See Backend.get_device_by_name()
        """

    def get_device_by_serial(self, serial):
        """
        See Backend.get_device_by_serial()
        """

    def apply(self):
        """
        Apply the settings.
        """
        self.debug("Apply undervolting settings.")

    def save(self):
        """
        Save the settings.
        """
        self.debug("Save undervolting settings.")
