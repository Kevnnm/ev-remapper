#!/usr/bin/env python3

from evremapper.logger import logger
from evremapper.configs.context import RuntimeContext

import evdev


class InputControl:
    def __init__(self, source: evdev.InputDevice, forward_to: evdev.UInput, context: RuntimeContext):
        self._source: evdev.InputDevice = source
        self._forward_to: evdev.UInput = forward_to
        self._context = context

    def forward(self, key):
        self._forward_to.write(*key)

    async def run(self):
        logger.debug(
            "Starting to listen for events from %s, fd %s",
            self._source.path,
            self._source.fd,
        )

        logger.debug("key_to_code map: %s", self._context.key_to_code)

        async for ev in self._source.async_read_loop():
            if ev.type == evdev.ecodes.EV_KEY and ev.value == 2:
                # button-hold event. Environments (gnome, etc.) create them on
                # their own for the injection-fake-device if the release event
                # won't appear, no need to forward or map them.
                continue

            if ev.code in self._context.key_to_code:
                remapped_code = self._context.key_to_code[ev.code]
                self.forward((ev.type, remapped_code, ev.value))
            else:
                self.forward((ev.type, ev.code, ev.value))
            # if ev.code == evdev.ecodes.KEY_CAPSLOCK:
            #     self.forward((ev.type, evdev.ecodes.KEY_LEFTCTRL, ev.value))

        logger.error('The async_read_loop for "%s" stopped early', self._source.path)
