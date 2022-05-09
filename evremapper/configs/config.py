#!/usr/bin/env python3

import json
from dataclasses import dataclass

from evremapper.logger import logger


class ConfigBase:
    def __init__(self):
        self._config = {}

    def _resolve(self, path, callback, config=None):
        """
        Resolves a keypath and calls callback on the value

        Parameters
        ----------
        path: string or string[]
            Can be in the form 'key1.key2.key3' or
            ['key1', 'key2', 'key3']
        callback: func(parent, child, key)
            Function to be called on the resolved value
        config:
            Config to resolve defaults to self._config

        """
        keys = path.copy() if isinstance(path, list) else path.split(".")

        if config is None:
            child = self._config
        else:
            child = config

        while True:
            key = keys.pop()
            parent = child
            child = child.get(key)
            if len(keys) == 0:  # No more keys to follow
                return callback(parent, child, key)

            if child is None:
                parent[key] = {}
                child = parent[key]

    def remove(self, path):
        def callback(parent, child, key):
            if child is not None:
                del parent[key]

        self._resolve(path, callback)

    def set(self, path, value):
        def callback(parent, child, key):
            parent[key] = value

        self._resolve(path, callback)

    def get(self, path):
        def callback(parent, child, key):
            return child

        return self._resolve(path, callback)

    def flush(self):
        """Flushes all configs in memory"""
        self._config = {}

    @classmethod
    def from_string(cls, string: str):
        try:
            config = json.loads(string)
            if not isinstance(config, dict):
                logger.error("invalid config string")
                raise ValueError

            ret = {}
            for key in config:
                event_descriptor = InputEvent.from_string(key)
                ret[event_descriptor] = config[key]

            return ret
        except (json.JSONDecodeError, ValueError):
            logger.error("failed to decode config from string")


@dataclass(frozen=True)
class InputEvent:

    sec: int
    usec: int
    type: int
    code: int
    value: int

    @classmethod
    def from_string(cls, string: str):
        """Create a InputEvent from a string like 'type, code, value'"""
        try:
            t, c, v = string.split(",")
            return cls(0, 0, int(t), int(c), int(v))
        except (ValueError, AttributeError):
            raise ValueError(
                f"failed to create InputEvent from {string = !r}"
            )

    def __repr__(self):
        return f"InputEvent({self.type},{self.code},{self.value})"
