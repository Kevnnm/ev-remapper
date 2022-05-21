#!/usr/bin/env python3

import threading
import asyncio
import multiprocessing
import json

from typing import List

from evremapper.logger import logger

import evdev
from evdev.ecodes import (
    EV_KEY,
    EV_REL,
    REL_X,
    REL_Y,
    REL_WHEEL,
    BTN_LEFT,
    KEY_A
)

KEYBOARD = "keyboard"
MOUSE = "mouse"
UNKNOWN = "unknown"

if not hasattr(evdev.InputDevice, "path"):
    # for evdev < 1.0.0 patch the path property
    @property
    def path(device):
        return device.fn

    evdev.InputDevice.path = path


def _is_keyboard_dev(capabilities) -> bool:
    if KEY_A in capabilities.get(EV_KEY, []):
        return True
    return False


def _is_mouse_dev(capabilities) -> bool:
    rel_evs = [REL_X, REL_Y, REL_WHEEL]
    for ev in rel_evs:
        if ev not in capabilities.get(EV_REL, []):
            return False

    if BTN_LEFT not in capabilities.get(EV_KEY, []):
        return False

    return True


def classify(device: evdev.InputDevice):
    """Classify the type of this device"""
    capabilities = device.capabilities(absinfo=False)

    if _is_mouse_dev(capabilities):
        return MOUSE
    if _is_keyboard_dev(capabilities):
        return KEYBOARD

    return UNKNOWN


def device_identifier(device: evdev.InputDevice):
    return (
        f"{device.info.bustype}"
        f"{device.info.vendor}_"
        f"{device.info.product}_"
        f'{device.phys.split("/")[0] or "-"}'
    )


class _DeviceGroup:
    def __init__(self, paths: List[str], names: List[str], types: List[str], key: str):

        self.key = key

        self.paths = paths
        self.names = names
        self.types = types

        self.name: str = sorted(names, key=len)[0]

    def dumps(self):
        """Return a string representing this object."""
        return json.dumps(
            dict(paths=self.paths, names=self.names, types=self.types, key=self.key)
        )

    def __repr__(self):
        return f"DeviceGroup({self.key})"


class DeviceGroupEncoder(json.JSONEncoder):
    def default(self, o):
        return o.__dict__


class _DeviceDetection(threading.Thread):
    def __init__(self, pipe):
        self.pipe = pipe
        super().__init__()

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        logger.debug("Searching for valid device paths")

        # Their are often multiple device paths associated with a single hardware
        # so we have to group them together
        dev_groups = {}
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
            except Exception as e:
                logger.error("Failed to access %s: %s", path, str(e))
                continue

            if dev.name in ["Power Button", "Sleep Button"]:  # Not gonna try to remap these devices
                continue

            device_type = classify(dev)

            capabilities = dev.capabilities(absinfo=False)

            key_codes = capabilities.get(EV_KEY)

            if key_codes is None:
                continue

            dev_id = device_identifier(dev)
            if dev_groups.get(dev_id) is None:
                dev_groups[dev_id] = []

            logger.debug('Found %s device "%s"("%s") at %s', device_type, dev.name, dev_id, path)

            dev_groups[dev_id].append((dev.name, path, device_type))

        result = []
        used_keys = set()
        for group in dev_groups.values():
            names = [device[0] for device in group]
            paths = [device[1] for device in group]
            types = [device[2] for device in group]

            key_base = sorted(names, key=len)[0]
            key = key_base
            i = 2
            while key in used_keys:
                key = f"{key_base} {i}"
                i += 1
            used_keys.add(key)

            group = _DeviceGroup(
                key=key,
                paths=paths,
                types=types,
                names=names
            )

            result.append(group)

        self.pipe.send(result)


class _DeviceGroups:
    def __init__(self):
        self._groups: List[_DeviceGroup] = None

    def __iter__(self):
        return iter(self._groups)

    def __getattribute__(self, key):
        """To lazy load _groups info when needed."""
        # Can't use getattr function because we will end up recursively calling this
        # function permanently
        if key == "_groups" and object.__getattribute__(self, "_groups") is None:
            object.__setattr__(self, "_groups", {})
            object.__getattribute__(self, "refresh")()

        return object.__getattribute__(self, key)

    def refresh(self):
        # groups.refresh()
        (r, w) = multiprocessing.Pipe()
        _DeviceDetection(w).start()

        result = r.recv()
        self._groups = result

    def find(self, key=None, path=None, include_evremapper=False):
        for group in self._groups:
            if not include_evremapper and group.name.startswith("ev-remapper"):
                continue

            if key and group.key != key:
                continue

            if path and path not in group.paths:
                continue

            return group


# Global instance for holding all device information
DevGroups = _DeviceGroups()
