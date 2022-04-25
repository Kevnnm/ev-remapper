#!/usr/bin/env python3

from pydbus import SystemBus
from evremapper.logger import logger
from evremapper.devices import DevGroups
from evremapper.injector import Injector
from evremapper.config import Config

import os
import time
import sys
from multiprocessing import Pipe

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib


BUS_NAME = "evremapper.Manager"


class Daemon:

    dbus = f"""
            <node>
                <interface name='{BUS_NAME}'>
                    <method name='hello'>
                        <arg type='s' name='out' direction='in'/>
                        <arg type='s' name='response' direction='out'/>
                    </method>
                    <method name='stop_inject_device'>
                        <arg type='s' name='device_key' direction='in'/>
                    </method>
                    <method name='inject_device'>
                        <arg type='s' name='device_key' direction='in'/>
                        <arg type='s' name='config' direction='in'/>
                        <arg type='b' name='status' direction='out'/>
                    </method>
                </interface>
            </node>
        """

    def __init__(self):
        # TODO Initialize structures here
        logger.debug("Creating daemon")

        self.injectors = {}
        self.refreshed_devices_at = 0

    def run(self):
        logger.debug("Starting daemon")
        loop = GLib.MainLoop()
        loop.run()

    def publish(self):
        bus = SystemBus()
        try:
            bus.publish(BUS_NAME, self)
        except RuntimeError as e:
            logger.error("Service already running? (%s)", str(e))
            sys.exit(1)

    def hello(self, out):
        logger.info('Received "%s" in hello', out)
        return out

    def refresh(self, group_key=""):
        now = time.time()
        if now - 10 > self.refreshed_devices_at:
            logger.debug("Refreshing device list due to time since last refresh")
            time.sleep(0.1)
            DevGroups.refresh()

            logger.debug("Finished refreshing")
            logger.debug("Available device groups: %s", [group.key for group in DevGroups])
            self.refreshed_devices_at = now
            return

        if not DevGroups.find(key=group_key):
            logger.debug("Refreshing device list due to missing device")
            time.sleep(0.1)
            DevGroups.refresh()

            logger.debug("finished refreshing")
            logger.debug("%s", [group.key for group in DevGroups])
            self.refreshed_devices_at = now

    def stop_inject_device(self, device_key):
        if self.injectors.get(device_key) is None:
            logger.warning('request to stop injecting for "%s" but none is running', device_key)
            return

        self.injectors[device_key].stop_injecting()

    def inject_device(self, device_key, config):
        logger.info('request to inject device "%s"', device_key)
        self.refresh(device_key)

        inject_group = DevGroups.find(key=device_key)

        config = Config.from_string(config)
        logger.debug("config to inject: %s", config)

        injector = Injector(inject_group, config)
        injector.start()
        self.injectors[inject_group.key] = injector

        return True
