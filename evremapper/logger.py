#!/usr/bin/env python3

import os
import logging
import shutil

from evremapper.user import HOME

LOG_FILE = (
    "/var/log/ev-remapper.log"
    if os.access("/var/log", os.W_OK)
    else f"{HOME}/.log/ev_remapper.log"
)

logger = logging.getLogger("ev-remapper")


def logger_verbosity(debug):
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)


def add_loghandler(log_path=LOG_FILE):
    try:
        log_path = os.path.expanduser(log_path)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        if os.path.isdir(log_path):
            shutil.rmtree(log_path)  # recursively remove if directory

        if os.path.exists(log_path):
            with open(log_path, "r") as file:
                data = file.readlines()[-1000:]

            with open(log_path, "w") as file:
                file.truncate(0)
                file.writelines(data)

        file_handler = logging.FileHandler(log_path)
        logger.addHandler(file_handler)

        logger.debug('Started logging to "%s"', log_path)
    except PermissionError:
        logger.debug('permission denied logging to "%s"', log_path)
