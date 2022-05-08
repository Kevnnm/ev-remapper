#!/usr/bin/env python3

import evdev

from evremapper.configs.config import InputEvent


class RuntimeContext:
    """Specifically used by the service daemon to get mappings for keycodes"""

    def __init__(self, mappings):
        self.key_to_code = {}
        self._populate_keycode_map(mappings)

    def _populate_keycode_map(self, mappings):
        self.key_to_code = {}
        for key_code_str in mappings:
            self.key_to_code[evdev.ecodes.ecodes[key_code_str]] = evdev.ecodes.ecodes[mappings[key_code_str]]
