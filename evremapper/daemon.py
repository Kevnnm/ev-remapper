#!/usr/bin/env python3

from pydbus import SystemBus
from evremapper.logger import logger

import sys

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
                </interface>
            </node>
        """

    def __init__(self):
        # TODO Initialize structures here
        logger.debug("Creating daemon")

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
