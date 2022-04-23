#!/usr/bin/env python3

import json
from dataclasses import dataclass

from evremapper.logger import logger


class Config:
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
