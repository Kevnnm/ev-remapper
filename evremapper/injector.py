#!/usr/bin/env python3

import time
import multiprocessing
import evdev
import asyncio

from evremapper.devices import _DeviceGroup
from evremapper.logger import logger
from evremapper.config import InputEvent


# Messages
CLOSE = 0


def is_in_capabilities(event: InputEvent, capabilites_dict):
    if event.code in capabilites_dict.get(event.type, []):
        return True

    return False


class Injector(multiprocessing.Process):
    def __init__(self,
                 group: _DeviceGroup,
                 config) -> None:
        # TODO: create a state field that will tell us the status of the process
        self.group = group
        self.config = config

        self._msg_pipe = multiprocessing.Pipe()

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

    def stop_injecting(self):
        logger.info('Stopping injector for group "%s"', self.group.key)
        self._msg_pipe[1].send(CLOSE)

    def run(self):
        logger.info('Starting injecting the for device "%s"', self.group.key)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        sources = self._grab_devices()

        logger.debug('sources "%s"', sources)

        # Eventually will hold all couroutines to read and write input for each input device in group
        couroutines = []

        couroutines.append(self._msg_listener())

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
