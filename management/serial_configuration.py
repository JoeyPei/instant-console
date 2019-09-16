#!/usr/bin/env python3
'''
@Project:console
@Time:5/9/2019 6:30 PM
'''
import os
import syslog
import subprocess
import pyudev
from management.config import LOG_PATH

BASE = 2000
MAX_SUPPORT_PORT = 30

class SerialConfiguration:
    def __init__(self, base=2000):
        self.config = {}
        self.device = [None] * MAX_SUPPORT_PORT
        self.tag = '/tmp/ser2net_update'

    def get_devices(self):
        context = pyudev.Context()
        devices = [d.sys_path for d in context.list_devices(subsystem='usb-serial')]
        return devices

    def get_pair(self, path):
        _ = path.split("/")
        return "/".join(_[:-1]), _[-1]

    def update_map(self):
        device_list = self.get_devices()

        for item in device_list:
            path, dev = self.get_pair(item)

            if config.get(path):
                try:
                    idx = self.device.index(None)
                    self.device[idx] = dev
                except ValueError:
                    return False
            config[path] = dev
        return True

    def sync(self):
        for idx, dev in enumerate(self.device):
            if not dev:
                continue

            port = str(BASE + idx)
            path = 'serial_' + port

            if os.path.exists(path):
                if os.readlink(path) == self.config[dev]:
                    continue
                else:
                    os.remove(path)
                    os.symlink(self.config[dev], path)
            else:
                os.symlink(self.config[dev], path)

    def reset(self):
        self.device = [ d for d in self.device if self.device ]
        self.device.extend([None] * (MAX_SUPPORT_PORT - len(self.device)))

    def initialize(self):
        if not os.path.exists(LOG_PATH):
            syslog.syslog(syslog.LOG_INFO, 'create {}'.format(LOG_PATH))
            os.makedirs(LOG_PATH)

        if os.path.isfile(self.tag):
            os.remove(self.tag)

        if not os.path.exists('log'):
            syslog.syslog(syslog.LOG_INFO, 'symbol link to {}'.format(LOG_PATH))
            os.system('ln -s /tmp/ser2net ./log')

        if not os.path.isfile('/etc/ser2net.conf'):
            syslog.syslog(syslog.LOG_INFO, 'copy ser2net.conf')
            os.system('cp management/ser2net.conf /etc/ser2net.conf')
            os.system('cp management/ser2net /etc/init.d/ser2net')
            os.system('update-rc.d ser2net')


MYSERIALCONFIG = SerialConfiguration()
