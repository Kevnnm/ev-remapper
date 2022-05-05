#!/usr/bin/env python3


import os
import getpass
import pwd


def get_user():
    try:
        return os.getlogin()
    except OSError:
        pass

    try:
        user = os.environ["USER"]
    except KeyError:
        return getpass.getuser()

    if user == "root":
        try:
            return os.environ["SUDO_USER"]
        except KeyError:
            # no sudo
            pass

        try:
            pkexec_uid = int(os.environ["PKEXEC_UID"])
            return pwd.getpwuid(pkexec_uid).pw_name
        except KeyError:
            # no pkexec or the uid is unknown
            pass

    return user


def get_home(user):
    """Get the user's home directory."""
    return pwd.getpwnam(user).pw_dir


USER = get_user()
HOME = get_home(USER)
CONFIG_PATH = os.path.join(HOME, ".config/ev-remapper")
