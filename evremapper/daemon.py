#!/usr/bin/env python3

from pydbus import SystemBus
from evremapper.logger import logger
from evremapper.devices import _DeviceDetection, DeviceGroupEncoder

import time
import sys
import json
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
                    <method name='refresh'>
                    </method>
                </interface>
            </node>
        """

    def __init__(self):
        # TODO Initialize structures here
        logger.debug("Creating daemon")

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

    def refresh(self):
        now = time.time()
        if now - 10 > self.refreshed_devices_at:
            logger.debug("Refreshing device list due to time since last refresh")
            time.sleep(0.1)
            # groups.refresh()
            (r, w) = Pipe()
            _DeviceDetection(w).start()

            result = r.recv()
            logger.debug("finished refreshing")
            logger.debug(DeviceGroupEncoder().encode(result))
            self.refreshed_devices_at = now
            return
