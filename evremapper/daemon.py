#!/usr/bin/env python3

from pydbus import SystemBus
from evremapper.logger import logger
from evremapper.devices import DevGroups
from evremapper.injector import Injector, UNKNOWN
from evremapper.configs.mappings import Mappings
from evremapper.configs.context import RuntimeContext
from evremapper.user import USER
from evremapper.configs.paths import get_config_path
from evremapper.configs.global_config import global_config

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
                    <method name='autoload_single'>
                        <arg type='s' name='device_key' direction='in'/>
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

        self.global_config = global_config

        # try to set the config_dir right away
        if USER != "root":
            self.set_config_dir(get_config_path())

        # check privileges
        if os.getuid() != 0:
            logger.warning("The service usually needs elevated privileges")

        self.injectors = {}
        self.refreshed_devices_at = 0

    @classmethod
    def connect(cls, fallback=True):
        """Try to connect to a running daemon, if not running then start one"""
        try:
            system_bus = SystemBus()
            daemon = system_bus.get(BUS_NAME, timeout=10)
            logger.info("connected to running daemon")
            return daemon
        except GLib.GError as error:
            if not fallback:
                logger.error("Service not running? %s", error)
                return None

            return None  # TODO: fix autostart feature

            logger.info("Starting the service")
            # Blocks until pkexec is done asking for the password.
            # Runs via input-remapper-control so that auth_admin_keep works
            # for all pkexec calls of the gui
            # debug = " -d" if is_debug() else ""
            cmd = "pkexec ev-remapper-control start-daemon"

            # using pkexec will also cause the service to continue running in
            # the background after the gui has been closed, which will keep
            # the injections ongoing

            logger.debug("Running `%s`", cmd)
            os.system(cmd)
            time.sleep(0.2)

            # try a few times if the service was just started
            for attempt in range(3):
                try:
                    daemon = system_bus.get(BUS_NAME, timeout=10)
                    break
                except GLib.GError as error:
                    logger.debug("Attempt %d to reach the service failed:", attempt + 1)
                    logger.debug('"%s"', error)
                time.sleep(0.2)
            else:
                logger.error("Failed to connect to the service")
                sys.exit(8)

        if USER != "root":
            config_path = get_config_path()
            logger.debug('Telling service about "%s"', config_path)
            daemon.set_config_dir(get_config_path(), timeout=2)

        return daemon

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
        if self.config_dir == config_dir:
            return

        config_path = os.path.join(config_dir, "config.json")
        if not os.path.exists(config_path):
            logger.error('config path does not exist "%s"', config_path)

        logger.debug('setting config directory to "%s"', config_dir)
        self.config_dir = config_dir

        config_path = os.path.join(
            self.config_dir,
            "config.json"
        )

        self.global_config.load(config_path)

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
        if inject_group is None:
            return False

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

    def autoload_single(self, device_key):
        logger.info('request to autoload device "%s"', device_key)

        if self.config_dir is None:
            logger.error('user tried to inject "%s" before informing service of config_dir, call set_config_dir', device_key)
            return False

        self.refresh(device_key)

        inject_group = DevGroups.find(key=device_key)
        autoload = self.global_config.get("autoload")
        try:
            mapping_name = autoload[inject_group.key]
        except KeyError:
            logger.info('request to autoload_single but device is not set to autoload: "%s"', device_key)
            return False

        mapping_path = os.path.join(
            self.config_dir,
            "mappings",
            inject_group.name,
            f"{mapping_name}.json"
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
        logger.info('request to autoload devices')

        if self.config_dir is None:
            logger.error('user tried to autoload before informing service of config_dir, call set_config_dir')
            return False

        self.refresh()

        autoload = self.global_config.get("autoload")
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
