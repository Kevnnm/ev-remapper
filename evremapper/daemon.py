#!/usr/bin/env python3

from pydbus import SystemBus
from evremapper.logger import logger
from evremapper.devices import DevGroups
from evremapper.injector import Injector, UNKNOWN
from evremapper.configs.mappings import Mappings
from evremapper.configs.context import RuntimeContext
from evremapper.user import USER
from evremapper.configs.paths import get_config_path
from evremapper.configs.global_config import GlobalConfig

import time
import sys
import os

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib


BUS_NAME = "evremapper.Manager"


class Daemon:

    dbus = f"""
            <node>
                <interface name='{BUS_NAME}'>
                    <method name='set_config_dir'>
                        <arg type='s' name='config_dir' direction='in'/>
                    </method>
                    <method name='stop_inject_device'>
                        <arg type='s' name='device_key' direction='in'/>
                    </method>
                    <method name='inject_device'>
                        <arg type='s' name='device_key' direction='in'/>
                        <arg type='s' name='config' direction='in'/>
                        <arg type='b' name='status' direction='out'/>
                    </method>
                    <method name='autoload'>
                        <arg type='b' name='status' direction='out'/>
                    </method>
                    <method name='stop_all'>
                    </method>
                    <method name='get_state'>
                        <arg type='s' name='device_key' direction='in'/>
                        <arg type='i' name='state' direction='out'/>
                    </method>
                    <method name='hello'>
                        <arg type='s' name='out' direction='in'/>
                        <arg type='s' name='response' direction='out'/>
                    </method>
                </interface>
            </node>
        """

    def __init__(self):
        logger.debug("Creating daemon")

        self.config_dir = None

        # try to set the config_dir right away
        if USER != "root":
            self.set_config_dir(get_config_path())

        # check privileges
        if os.getuid() != 0:
            logger.warning("The service usually needs elevated privileges")

        self.injectors = {}
        self.refreshed_devices_at = 0

    @classmethod
    def connect(cls):
        """Try to connect to a running daemon, if not running then start one"""
        try:
            system_bus = SystemBus()
            system_bus.get(BUS_NAME, timeout=10)
            logger.info("connected to running daemon")
        except GLib.GError:
            logger.info("failed to connect to running daemon")
            # TODO: start the daemon if not running using pkexec
            # logger.info("Starting the service")
            # Blocks until pkexec is done asking for the password.

    def set_config_dir(self, config_dir):
        """
        Sets the configuration directory

        The configuration directory will be the default path that the service
        will look for configuration files

        Parameters
        ----------
        config_dir : string
            This path contains config.json and the
            presets directory

        """
        config_path = os.path.join(config_dir, "config.json")
        if not os.path.exists(config_path):
            logger.error('config path does not exist "%s"', config_path)

        logger.debug('setting config directory to "%s"', config_dir)
        self.config_dir = config_dir

    def run(self):
        logger.debug("Starting daemon")
        loop = GLib.MainLoop()
        loop.run()

    def get_state(self, device_key):
        logger.info('request device "%s" state', device_key)
        injector = self.injectors.get(device_key, None)

        if injector is None:
            logger.debug('injector not found "%s"', device_key)
            return UNKNOWN

        state = injector.get_state()
        logger.debug('device state "%s"', state)
        return state

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

    def inject_device(self, device_key, mapping):
        logger.info('request to inject device "%s"', device_key)

        if self.config_dir is None:
            logger.error('user tried to inject "%s" before informing service of config_dir, call set_config_dir', device_key)
            return False

        self.refresh(device_key)

        inject_group = DevGroups.find(key=device_key)

        mapping_path = os.path.join(
            self.config_dir,
            "mappings",
            inject_group.name,
            f"{mapping}.json"
        )

        mappings = Mappings()
        mappings.load(mapping_path)
        context = RuntimeContext(mappings._mappings)

        logger.debug("mappings to inject: %s", mappings._mappings)

        # Make sure we stop injector for this device, if already running
        if self.injectors.get(device_key) is not None:
            self.stop_inject_device(device_key)

        injector = Injector(inject_group, context)
        injector.start()
        self.injectors[inject_group.key] = injector

        return True

    def autoload(self):
        logger.info('request to autoload devices"')

        if self.config_dir is None:
            logger.error('user tried to autoload before informing service of config_dir, call set_config_dir')
            return False

        self.refresh()

        config_path = os.path.join(
            self.config_dir,
            "config.json"
        )
        global_config = GlobalConfig()
        global_config.load(config_path)

        autoload = global_config.get("autoload")
        logger.debug('autoloading: %s', list(autoload.keys()))

        for dev_key in autoload:
            inject_group = DevGroups.find(key=dev_key)
            if inject_group is None:
                logger.info('could not find device to autoload: "%s", skipping', dev_key)

            self.inject_device(dev_key, autoload[dev_key])

        return True

    def stop_all(self):
        logger.info('request to stop all injectors')

        for injector_key in self.injectors:
            self.injectors[injector_key].stop_injecting()
