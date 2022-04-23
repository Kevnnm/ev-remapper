#!/usr/bin/env python3

import time
import multiprocessing
import evdev

from evremapper.devices import _DeviceGroup
from evremapper.logger import logger
from evremapper.config import InputEvent


def is_in_capabilities(event: InputEvent, capabilites_dict):
    if event.code in capabilites_dict.get(event.type, []):
        return True

    return False


class Injector(multiprocessing.Process):
    def __init__(self, group: _DeviceGroup, config) -> None:
        self.group = group
        self.config = config

        super().__init__(name=group)

    def _grab_devices(self):
        sources = []
        for path in self.group.paths:
            input_source = self._grab_device(path)
            if input_source is not None:
                sources.append(input_source)

        return sources

    def _grab_device(self, device_path):
        try:
            dev = evdev.InputDevice(device_path)
        except (IOError, OSError):
            logger.error('could not find device at "%s"', device_path)
            return None

        device_capabilities = dev.capabilities(absinfo=False)

        grab = False
        for key in self.config:
            if is_in_capabilities(key, device_capabilities):
                grab = True
                logger.info('grabbing device at "%s" because of event "%s"', device_path, key)

        if not grab:
            logger.debug("no need to grab device at '%s'", device_path)
            return None

        attempts = 0
        while True:
            try:
                dev.grab()
                logger.debug("Grab %s", device_path)
                break
            except IOError as error:
                attempts += 1

                # it might take a little time until the device is free if
                # it was previously grabbed.
                logger.debug("Failed attempts to grab %s: %d", device_path, attempts)

                if attempts >= 10:
                    logger.error("Cannot grab %s, it is possibly in use", device_path)
                    logger.error(str(error))
                    return None

            time.sleep(0.2)

        return dev

    def run(self):
        sources = self._grab_devices()

        logger.debug('sources "%s"', sources)

        for source in sources:
            # ungrab at the end to make the next injection process not fail
            # its grabs
            try:
                source.ungrab()
            except (OSError, IOError) as error:
                # ungrabbing an ungrabbed device can cause an IOError
                logger.debug("OSError for ungrab on %s: %s", source.path, str(error))
