#!/usr/bin/env python3

from evremapper.configs.config import ConfigBase
from evremapper.logger import logger

from typing import Dict
import os
import json


class Mappings(ConfigBase):
    """Class for saving and loading mapping config files"""

    def __init__(self):
        self._mappings: Dict[int, int] = {}
        self._has_unsaved_changes = False

        super().__init__()

    def empty(self):
        """Remove all mappings and custom configs without saving."""
        self._mapping = {}
        self._has_unsaved_changes = True
        self.flush()

    def load(self, path):
        logger.info('Loading mappings from "%s"', path)

        if not os.path.exists(path):
            raise FileNotFoundError(f'Tried to load non-existing preset "{path}"')

        self.empty()
        self._has_unsaved_changes = False

        with open(path, "r") as file:
            json_dict = json.load(file)

            if not isinstance(json_dict["mappings"], dict):
                logger.error("expected `mappings` to be dict but found %s",
                             'invalid mapping config at "%s"',
                             type(json_dict.get("mappings")),
                             path
                             )
                return

            mappings = json_dict["mappings"]

            for key_name in mappings:
                self._mappings[key_name] = mappings[key_name]
