#!/usr/bin/env python3

import glob
from setuptools import setup

setup(
    name="ev-remapper",
    version="1.0.0",
    description="Tool to remap input event codes using libevdev",
    author="Kevnnm",
    author_email="kevin@mcmullin.one",
    url="https://github.com/kevnnm/ev-remapper",
    license="MIT",
    packages=["evremapper"],
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
