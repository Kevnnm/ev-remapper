#!/usr/bin/env python3

from evremapper.configs.config import ConfigBase
from evremapper.logger import logger

from typing import Dict
import os
import json


class GlobalConfig(ConfigBase):
    """Class for saving and loading mapping config files"""

    def __init__(self):
        self._has_unsaved_changes = False

        super().__init__()

    def empty(self):
        """Remove all mappings and custom configs without saving."""
        self._has_unsaved_changes = True
        self.flush()

    def load(self, path):
        logger.info('Loading config from "%s"', path)

        if not os.path.exists(path):
            raise FileNotFoundError(f'Tried to load non-existing config "{path}"')

        self.empty()
        self._has_unsaved_changes = False

        with open(path, "r") as file:
            json_dict = json.load(file)

            if not isinstance(json_dict["autoload"], dict):
                logger.error("expected `autoload` to be dict but found %s",
                             'invalid config at "%s"',
                             type(json_dict.get("autoload")),
                             path
                             )
                return

            for key in json_dict:
                self.set(key, json_dict[key])
