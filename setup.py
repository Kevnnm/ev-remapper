#!/usr/bin/env python3

import os
import glob
from setuptools import setup


def get_packages(base="evremapper"):
    """Recursively grab all module directories. For example 'evremapper' and 'evremapper.config'"""
    if not os.path.exists(os.path.join(base, "__init__.py")):
        # only python modules
        return []

    result = [base.replace("/", ".")]
    for name in os.listdir(base):
        if not os.path.isdir(os.path.join(base, name)):
            continue

        if name == "__pycache__":
            continue

        # find more python submodules in that directory
        result += get_packages(os.path.join(base, name))

    return result


setup(
    name="ev-remapper",
    version="1.0.0",
    description="Tool to remap input event codes using libevdev",
    author="Kevnnm",
    author_email="kevin@mcmullin.one",
    url="https://github.com/kevnnm/ev-remapper",
    license="MIT",
    packages=get_packages(),
    include_package_data=True,
    # TODO: setup udev rules to autoload when devices are input devices are plugged in
    # TODO: dbus-1/system.d configurations for when ipc is implemented
    data_files=[
        ("/usr/share/ev-remapper/", glob.glob("data/*")),
        ("/usr/share/polkit-1/actions/", ["data/ev-remapper.policy"]),
        ("/etc/dbus-1/system.d/", ["data/evremapper.Manager.conf"]),
        ("/usr/lib/systemd/system/", ["data/ev-remapper.service"]),
        ("/usr/bin/", ["bin/ev-remapper-service"]),
    ],
    install_requires=["setuptools", "evdev", "pydbus", "pygobject"],
)
