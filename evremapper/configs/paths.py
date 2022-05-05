#!/usr/bin/env python3
import os

from inputremapper.logger import logger
from inputremapper.user import CONFIG_PATH


def get_mapping_path(group_name=None, preset=None):
    """Get a path to the stored preset, or to store a preset to."""
    presets_base = os.path.join(CONFIG_PATH, "presets")

    if group_name is None:
        return presets_base

    if preset is not None:
        assert not preset.endswith(".json")
        preset = f"{preset}.json"

    if preset is None:
        return os.path.join(presets_base, group_name)

    return os.path.join(presets_base, group_name, preset)


def get_config_path(*paths):
    """Get a path in ~/.config/input-remapper/"""
    return os.path.join(CONFIG_PATH, *paths)
