#!/usr/bin/env python3
'''
@Project:console
@Time:5/9/2019 6:30 PM
'''
import os
import json
import subprocess
from threading import Lock

import pyudev
import logging

logging.basicConfig(filename='ser2net_mgmt.log', filemode='w', level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from management.utils import generate_name
from management.config import LOG_PATH, MANAGE_PORT, PORT_BASE, MAX_SUPPORT_PORT


class SerialConfiguration:
    def __init__(self):
        self.config = {}
        self.device = [None] * MAX_SUPPORT_PORT
        self.tag = '/tmp/ser2net_update'
        self.observer = None
        self.context = pyudev.Context()

    def get_devices(self):
        devices = [d.sys_path for d in self.context.list_devices(subsystem='usb-serial')]
        return devices

    def get_status(self):
        info = {
            'map': self.config,
            'index': self.device,
            'identifier': '',
        }

        return info

    def set_config(self, info):
        self.config = info.get('map')
        self.device = info.get('index')
        identifier = info.get('identifier')

        return True

    def get_pair(self, path):
        _ = path.split("/")
        return "/".join(_[:-1]), _[-1]

    def update_map(self, devices):
        for item in devices:
            path, dev = self.get_pair(item)

            # If not found, insert to self.device
            if not self.config.get(path):
                try:
                    idx = self.device.index(None)
                    if idx:
                        logger.info("Insert new device [{}]: {} ".format(idx, path))
                        self.device[idx] = path
                except ValueError:
                    logger.info("device has reached maximum number")
                    return False
            # Update or Insert new item
            self.config[path] = dev

        return True

    def sync(self):
        logger.info("sync config")
        for idx, path in enumerate(self.device):
            port = str(PORT_BASE + idx)
            link = '/dev/serial_' + port

            if os.path.lexists(link):
                if path:
                    if os.readlink(link) == self.config.get(path):
                        continue
                    else:
                        logger.info("Delete symbol link: {}".format(link))
                        os.remove(link)
                        logger.info("Create symbol link: {} -> {}".format(self.config[path], link))
                        os.symlink(self.config[path], link)
                else:
                    logger.info("Delete invalid link: {}".format(link))
                    os.remove(link)
            else:
                if path:
                    logger.info("Create symbol link: {} -> {}".format(self.config[path], link))
                    os.symlink(self.config[path], link)

        self.save()

    def reset(self):
        self.config = {}
        self.device = [None] * MAX_SUPPORT_PORT
        self.update()
        logger.info("Reset. Total Devices: {}".format(len(self.config)))
        return True

    def prune(self):
        logger.info("Delete invalid node")
        valid_devices = [self.get_pair(d)[0] for d in self.get_devices()]
        for idx, item in enumerate(self.device):
            try:
                valid_devices.index(item)
            except ValueError:
                logger.info("Delete device [{}] :{}".format(idx, item))
                self.device[idx] = None
                if self.config.get(item):
                    del self.config[item]

        self.sync()
        return True

    def save(self):
        config = {
            'map': self.config,
            'index': self.device
        }

        with open('serial.map', 'w') as _map:
            _map.write(json.dumps(config))
        logger.info("save serial.map")

    def load(self):
        logger.info("load serial.map")
        try:
            with open('serial.map', 'r') as _map:
                raw = _map.read()
                config = json.loads(raw)
                self.config = config['map'] or {}
                self.device = config['index'] or {}
        except:
            logger.info("Failed to load serial.map")

    def update(self):
        logger.info("update")
        self.update_map(self.get_devices())
        self.sync()
        return True

    def auto_update(self, action, device):
        if action == "add":
            logger.info('auto-update: {}  Device:{}'.format(action, device.sys_name))
            self.update_map([device.sys_path])
            self.sync()

        if action == "remove":
            path, dev = self.get_pair(device.sys_path)
            if self.config.get(path):
                idx = self.device.index(path)
                port = str(PORT_BASE + idx)
                link = '/dev/serial_' + port
                logger.info("auto-update: Delete symbol link: {}".format(link))
                if os.path.lexists(link):
                    os.remove(link)

    def initialize(self):
        if not os.path.exists(LOG_PATH):
            logger.info('create {}'.format(LOG_PATH))
            os.makedirs(LOG_PATH)

        if os.path.isfile(self.tag):
            os.remove(self.tag)

        if not os.path.exists('log'):
            logger.info('symbol link to {}'.format(LOG_PATH))
            os.system('ln -s /tmp/ser2net ./log')

        self.generate_conf()

        self.load()
        monitor = pyudev.Monitor.from_netlink(self.context)
        monitor.filter_by('usb-serial')
        self.observer = pyudev.MonitorObserver(monitor, self.auto_update)
        self.observer.start()
        logger.info('initialize observer')

        # os.system('cp management/ser2net /etc/init.d/ser2net')
        # os.system('update-rc.d ser2net')

    def generate_conf(self):
        port_template = '{num}:telnet:0:/dev/serial_{num}:9600 8DATABITS NONE 1STOPBIT {flag} \r\n'
        with open('ser2net.conf', 'w') as _conf:
            _conf.write('TRACEFILE:log:/tmp/ser2net/port_\p-\Y\m\D.log\r\n')
            _conf.write('CONTROLPORT:localhost,{}\r\n\r\n'.format(MANAGE_PORT))
            _conf.writelines([
                port_template.format(num=num, flag=' tr=log rotate')
                for num in range(PORT_BASE, PORT_BASE + MAX_SUPPORT_PORT)
            ])

        if not os.path.isfile('/etc/ser2net.conf'):
            logger.info('copy ser2net.conf')
            os.system('cp ser2net.conf /etc/ser2net.conf')


MYSERIALCONFIG = SerialConfiguration()
logger = logging.getLogger('ser2net_mgmt')