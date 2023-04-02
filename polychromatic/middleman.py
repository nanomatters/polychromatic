# Polychromatic is licensed under the GPLv3.
# Copyright (C) 2020-2023 Luke Horwell <code@horwell.me>
"""
Provides the "middle ground" between each backend and Polychromatic's interfaces.

The code that provides each backend is stored in "backends" directory.

Refer to the online documentation for more details:
https://docs.polychromatic.app/
"""

from . import procpid
from . import common
from .backends._backend import Backend
from .troubleshoot import openrazer as openrazer_troubleshoot


TROUBLESHOOT_MODULES = {
    "openrazer": openrazer_troubleshoot.troubleshoot
}


class Middleman(object):
    """
    The 'middleman' that processes the data between Polychromatic's applications
    by blending all the backends together.
    """
    def __init__(self):
        """
        Stores variables for the sessions.
        """
        # The PolychromaticBase() object, passed to backends later.
        self._base = None

        # List of initialized Backend() objects.
        self.backends = []

        # List of Backend() modules that failed to init().
        self.bad_init = []

        # List of backend string IDs that are not present.
        self.not_installed = []

        # Dictionary of backend IDs referencing troubleshoot() functions, if available.
        #   e.g. "openrazer": TROUBLESHOOT_MODULES.get("openrazer")
        self.troubleshooters = {}

        # Keys containing human readable strings for modules that failed to import.
        #   e.g. "openrazer": "Exception: xyz"
        self.import_errors = {}

        # List of DeviceItem() objects.
        self.device_cache = []

    def init(self):
        """
        Initialise the backend objects. This should be called when the user interface
        is ready. Note that this thread may potentially be blocked if the backend
        hangs while it initialises.
        """
        try:
            import polychromatic.backends.openrazer as openrazer_backend
            backend = openrazer_backend.OpenRazerBackend(self._base)
            if backend.init():
                self.backends.append(backend)
            else:
                self.bad_init.append(backend)
        except (ImportError, ModuleNotFoundError):
            self.not_installed.append("openrazer")
        except Exception as e:
            self.import_errors["openrazer"] = common.get_exception_as_string(e)

        try:
            import polychromatic.backends.undervolt as undervolt_backend
            backend = undervolt_backend.UndervoltBackend(self._base)
            if backend.init():
                self.backends.append(backend)
            else:
                self.bad_init.append(backend)
        except (ImportError, ModuleNotFoundError):
            self.not_installed.append("undervolt")
        except Exception as e:
            self.import_errors["undervolt"] = common.get_exception_as_string(e)

        try:
            self.troubleshooters["openrazer"] = TROUBLESHOOT_MODULES["openrazer"]
        except NameError:
            # Backend does not have a troubleshooter.
            pass

    def get_backend(self, device):
        """
        Returns the backend object for the specified device.
        """
        # FIXME: Legacy code used this function for "backend_id"
        if type(device) == str:
            backend_id = device
            for backend in self.backends:
                if backend_id == backend.backend_id:
                    return backend

        for module in self.backends:
            if device.backend_id == module.backend_id:
                return module

    def is_backend_running(self, backend_id):
        """
        Returns a boolean to indicate whether a specific backend ID is running
        and was successfully initialized.
        """
        for module in self.backends:
            if module.backend_id == backend_id:
                return True
        return False

    def get_versions(self):
        """
        Return a dictionary of versions for each running backend.
        """
        versions = {}
        for module in self.backends:
            versions[module.backend_id] = module.version
        return versions

    def _reload_device_cache_if_empty(self):
        """
        Reload the cache of DeviceItem()'s if it hasn't been initalized yet.
        """
        if self.device_cache:
            return

        for backend in self.backends:
            device_list = backend.get_devices()

            if not type(device_list) == list:
                continue

            # Assign 'backend' variable into device object
            for device in device_list:
                device.backend = backend

            self.device_cache = self.device_cache + device_list

    def invalidate_cache(self):
        """
        A fault was detected with the device list. For example, a backend's daemon died,
        or devices were inserted/removed.
        """
        self.device_cache = []

    def reload_device_cache(self):
        """
        Clear the device object cache and reload.
        """
        self.device_cache = []
        self._reload_device_cache_if_empty()

    def get_devices(self):
        """
        Returns a list of DeviceItem() objects.
        """
        self._reload_device_cache_if_empty()
        return self.device_cache

    def get_device_by_name(self, name):
        """
        Returns a fresh DeviceItem() by looking up its device name, or None if
        there is no device with that name.
        """
        for backend in self.backends:
            device = backend.get_device_by_name(name)
            if isinstance(device, Backend.DeviceItem):
                return device
        return None

    def get_device_by_serial(self, serial):
        """
        Returns a fresh DeviceItem() object by looking up its serial number, or
        None if there is no device with that serial string.
        """
        for backend in self.backends:
            device = backend.get_device_by_serial(serial)
            if isinstance(device, Backend.DeviceItem):
                return device
        return None

    def get_devices_by_form_factor(self, form_factor_id):
        """
        Returns a list of DeviceItem()'s based on the form factor specified, or empty list.
        """
        self._reload_device_cache_if_empty()
        devices = []
        for device in self.device_cache:
            if device.form_factor["id"] == form_factor_id:
                devices.append(device)
        return devices

    def get_unsupported_devices(self):
        """
        Returns a list of connected devices that cannot be controlled by their backend.
        """
        unknown_devices = []
        for backend in self.backends:
            device_list = backend.get_unsupported_devices()

            # Assign 'backend' variable into device object
            for device in device_list:
                device.backend = backend

            unknown_devices = unknown_devices + device_list
        return unknown_devices

    def troubleshoot(self, backend, i18n, fn_progress_set_max, fn_progress_advance):
        """
        Performs a series of troubleshooting steps to identify possible
        reasons why a particular backend is non-functional.

        Params:
            backend         (str)       ID of backend to check
            i18n            (obj)       _ function for translating strings
            fn_progress_set_max         See _backend.Backend.troubleshoot()
            fn_progress_advance         See _backend.Backend.troubleshoot()

        Returns:
            (list)          Results from the troubleshooter
            None            Troubleshooter not available
            False           Troubleshooter failed
        """
        try:
            return self.troubleshooters[backend](i18n, fn_progress_set_max, fn_progress_advance)
        except KeyError:
            # Troubleshooter not available for this backend
            return None
        # TODO: Catch errors via interfaces

    def restart(self, backend):
        """
        Restarts a specific backend.
        """
        for module in self.backends:
            if module.backend_id == backend:
                return module.restart()

    def get_active_effect(self, zone):
        """
        Return the first active Backend.EffectOption from the specified zone.
        """
        for option in zone.options:
            if isinstance(option, Backend.EffectOption) and option.active:
                return option

    def get_active_parameter(self, option):
        """
        Return the active Backend.Option.Parameter from the specified option.
        """
        for param in option.parameters:
            if param.active:
                return param

    def get_active_colours_required(self, option):
        """
        Return the number of colours required for the specified option.
        When parameters are present, there may be a different number of colours.
        """
        param = self.get_active_parameter(option)
        if param:
            return param.colours_required
        return option.colours_required

    def get_default_parameter(self, option):
        """
        Return the default Backend.Option.Parameter() object for an option.

        There should only be one default, so the first one will be returned.
        If there are no defaults, the first parameter will be returned.
        """
        if not option.parameters:
            return None

        for param in option.parameters:
            if param.default:
                return param

        return option.parameters[0]

    def _apply_option_with_same_params(self, option):
        """
        Re-apply the specified Backend.Option() instance, using the same
        parameters and colours.
        """
        if option.parameters:
            param_data = option.parameters[0].data
            for param in option.parameters:
                if param.active:
                    param_data = param.data
            option.apply(param_data)

        elif isinstance(option, Backend.ToggleOption):
            option.apply(option.active)

        elif isinstance(option, Backend.SliderOption):
            option.apply(option.value)

        elif isinstance(option, (Backend.EffectOption, Backend.MultipleChoiceOption)):
            option.apply()

    def replay_active_effect(self, device):
        """
        Re-applies the 'active' effect for all zones on the device.

        For example, this may be used to restore previously played effect prior to
        opening the effect editor which was physically previewing on the hardware.
        """
        # TODO: Catch error?
        device.refresh()

        # Was the device playing a software effect?
        state = procpid.DeviceSoftwareState(device.serial)
        effect = state.get_effect()
        if effect:
            procmgr = procpid.ProcessManager("helper")
            procmgr.start_component(["--run-fx", effect["path"], "--device-serial", device.serial])
            return

        # Was the device running a hardware effect?
        for zone in device.zones:
            option = self.get_active_effect(zone)
            if option:
                if option.active:
                    self._apply_option_with_same_params(option)

    def set_colour_for_option(self, option, hex_value, colour_pos=0):
        """
        Set a new colour for the specified option.

        Params:
            option      (obj)   Backend.Option() inherited object
            hex_value   (str)   New #RRGGBB string
            colour_pos  (int)   (Optional) Position to append. 0 = Primary, 1 = Secondary, etc
        """
        option.colours[colour_pos] = hex_value
        self._apply_option_with_same_params(option)

    def set_colour_for_active_effect_zone(self, zone, hex_value, colour_pos=0):
        """
        Set a new colour for the effect that's active in the specified zone.

        Params:
            zone        (obj)   Backend.DeviceItem.Zone() object
            hex_value   (str)   New #RRGGBB string
            colour_pos  (int)   (Optional) Position to append. 0 = Primary, 1 = Secondary, etc
        """
        option = self.get_active_effect(zone)
        if option:
            return self.set_colour_for_option(option, hex_value, colour_pos)

    def set_colour_for_active_effect_device(self, device, hex_value, colour_pos=0):
        """
        Set a new colour for all the device's active effects.

        Params:
            device      (obj)   Backend.DeviceItem() object
            hex_value   (str)   New #RRGGBB string
            colour_pos  (int)   (Optional) Position to append. 0 = Primary, 1 = Secondary, etc
        """
        for zone in device.zones:
            option = self.get_active_effect(zone)
            if option:
                self.set_colour_for_option(option, hex_value, colour_pos)

    def stop_software_effect(self, serial):
        """
        Prior to applying a hardware effect, make sure any software effects
        have stopped.
        """
        process = procpid.ProcessManager(serial)
        state = procpid.DeviceSoftwareState(serial)

        if state.get_effect() or process.is_another_instance_is_running():
            process.stop()
            state.clear_effect()

        if state.get_preset():
            state.clear_preset()
