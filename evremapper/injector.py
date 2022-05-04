#!/usr/bin/env python3

import time
import multiprocessing
import evdev
import asyncio
import sys

from typing import Dict, List

from evremapper.devices import _DeviceGroup
from evremapper.logger import logger
from evremapper.config import InputEvent
from evremapper.input_control import InputControl

CapabilitiesDict = Dict[int, List[int]]
DeviceSources = List[evdev.InputDevice]

EV_DEVICE_PREFIX = "ev-remapper"

# Messages
CLOSE = 0

# States
UNKNOWN = -1
STARTING = 2
FAILED = 3
RUNNING = 4
STOPPED = 5
NO_DEVICES = 6


def is_in_capabilities(event: InputEvent, capabilites_dict):
    if event.code in capabilites_dict.get(event.type, []):
        return True

    return False


def udev_name(device_name: str):
    max_len = 80  # any longer than 80 chars gives an error
    remaining = max_len - len(EV_DEVICE_PREFIX) - 2  # 1 for the space char
    suffix = device_name[:remaining]
    name = f"{EV_DEVICE_PREFIX} {suffix}"
    return name


class Injector(multiprocessing.Process):
    def __init__(self,
                 group: _DeviceGroup,
                 config) -> None:
        # TODO: create a state field that will tell us the status of the process
        self._state = UNKNOWN

        self.group = group
        self.config = config

        self._msg_pipe = multiprocessing.Pipe()

        super().__init__(name=group)

    def get_state(self):
        alive = self.is_alive()  # reports whether the process is alive

        if self._state == UNKNOWN and not alive:
            # `self.start()` has not been called yet
            return self._state

        if self._state == UNKNOWN and alive:
            # We are alive but state is not known means starting up
            self._state = STARTING

        if self._state == STARTING and self._msg_pipe[1].poll():
            # if msg pipe will hold the true status
            msg = self._msg_pipe[1].recv()
            self._state = msg

        if self._state in [STARTING, RUNNING] and not alive:
            # we thought it is running, but the process is not alive. Crash condition
            self._state = FAILED
            logger.error("Injector process was unexpectedly found stopped")

        return self._state

    def stop_injecting(self):
        logger.info('Stopping injector for group "%s"', self.group.key)
        self._msg_pipe[1].send(CLOSE)
        self._state = STOPPED

    def _grab_devices(self) -> DeviceSources:
        sources = []
        for path in self.group.paths:
            input_source = self._grab_device(path)
            if input_source is not None:
                sources.append(input_source)

        return sources

    def _grab_device(self, device_path) -> evdev.InputDevice:
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

    async def _msg_listener(self):
        """Wait for messages from main process and process them"""
        loop = asyncio.get_event_loop()
        while True:
            read_ready = asyncio.Event()
            loop.add_reader(self._msg_pipe[0].fileno(), read_ready.set)
            await read_ready.wait()
            read_ready.clear()

            msg = self._msg_pipe[0].recv()
            if msg == CLOSE:
                logger.debug('received close signal at injector "%s"', self.group.key)
                loop.stop()
                return

    def _copy_capabilities(self, input_device: evdev.InputDevice) -> CapabilitiesDict:
        """Copy capabilities for a new device."""
        ecodes = evdev.ecodes

        capabilities = input_device.capabilities(absinfo=True)

        # just like what python-evdev does in from_device
        if ecodes.EV_SYN in capabilities:
            del capabilities[ecodes.EV_SYN]
        if ecodes.EV_FF in capabilities:
            del capabilities[ecodes.EV_FF]

        if ecodes.ABS_VOLUME in capabilities.get(ecodes.EV_ABS, []):
            # For some reason an ABS_VOLUME capability likes to appear
            # for some users. It prevents mice from moving around and
            # keyboards from writing symbols
            capabilities[ecodes.EV_ABS].remove(ecodes.ABS_VOLUME)

        return capabilities

    def run(self):
        logger.info('Starting injecting the for device "%s"', self.group.key)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        sources = self._grab_devices()

        if len(sources) == 0:
            logger.error("Did not grab any devices")
            self._msg_pipe[0].send(NO_DEVICES)
            return

        logger.debug('sources "%s"', sources)

        # Eventually will hold all couroutines to read and write input for each input device in group
        couroutines = []

        for source in sources:
            try:
                # Copy as much info as possible
                forward_to = evdev.UInput(
                    name=udev_name(source.name),
                    events=self._copy_capabilities(source),
                    vendor=source.info.vendor,
                    product=source.info.product,
                    version=source.info.version,
                    bustype=source.info.bustype,
                    input_props=source.input_props(),
                )

                logger.debug("forwarding to uinput %s", forward_to.name)
            # TODO: Create a KeycodeMapper with async run methods to read events from source
            # pass them on to forward_to and append it to coroutines to be run in event loop

            except TypeError as e:
                if "input_props" in str(e):
                    # UInput constructor doesn't support input_props and
                    # source.input_props doesn't exist with old python-evdev versions.
                    logger.error("Please upgrade your python-evdev version. Exiting")
                    # TODO: send sth on msg pipe?
                    sys.exit(12)

                raise e

            input_control = InputControl(source, forward_to, self.config)
            couroutines.append(input_control.run())

        couroutines.append(self._msg_listener())

        self._msg_pipe[0].send(RUNNING)

        # try-except block for cleanly catching asyncio cancellation
        try:
            loop.run_until_complete(asyncio.gather(*couroutines))
        except RuntimeError as error:
            # loop stops via `CLOSE` msg which causes this error msg.
            if str(error) != "Event loop stopped before Future completed.":
                raise error
        except OSError as e:
            logger.error("Failed to run injector coroutines: %s", str(e))

        logger.info('Ungrabbing all input devices for device group "%s"', self.group.key)
        for source in sources:
            # ungrab at the end to make the next injection process not fail its grabs
            try:
                source.ungrab()
            except (OSError, IOError) as error:
                # ungrabbing an ungrabbed device can cause an IOError
                logger.debug("OSError for ungrab on %s: %s", source.path, str(error))
