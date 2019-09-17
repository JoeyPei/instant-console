#!/usr/bin/env python3
'''
@Project:console
@Time:5/9/2019 6:30 PM
'''
import os
# import syslog
import subprocess
import pyudev
from management.config import LOG_PATH

BASE = 2000
MAX_SUPPORT_PORT = 30

class SerialConfiguration:
    def __init__(self):
        self.config = {}
        self.device = [None] * MAX_SUPPORT_PORT
        self.tag = '/tmp/ser2net_update'
        self.observer = None
        self.context = None

    def get_devices(self):
        devices = [d.sys_path for d in self.context.list_devices(subsystem='usb-serial')]
        return devices

    def get_pair(self, path):
        _ = path.split("/")
        return "/".join(_[:-1]), _[-1]

    def update_map(self):
        device_list = self.get_devices()

        for item in device_list:
            path, dev = self.get_pair(item)

            if self.config.get(path):
                try:
                    idx = self.device.index(None)
                    self.device[idx] = path
                except ValueError:
                    return False
            self.config[path] = dev
        return True

    def sync(self):
        for idx, dev in enumerate(self.device):
            if not dev:
                continue

            port = str(BASE + idx)
            path = 'serial_' + port

            if os.path.exists(path):
                if os.readlink(path) == self.config[path ]:
                    continue
                else:
                    os.remove(path)
                    os.symlink(self.config[dev], path)
            else:
                os.symlink(self.config[dev], '/dev/'+path)

    def reset(self):
        self.device = [ d for d in self.device if self.device ]
        self.device.extend([None] * (MAX_SUPPORT_PORT - len(self.device)))

    def update(self):
        self.update_map()
        self.sync()

    def auto_update(self, action, device):
        print('{}  Device:{}'.format(action, device.sys_name))
        self.update_map()
        self.sync()

    def initialize(self):
        if not os.path.exists(LOG_PATH):
            print('create {}'.format(LOG_PATH))
            os.makedirs(LOG_PATH)

        if os.path.isfile(self.tag):
            os.remove(self.tag)

        if not os.path.exists('log'):
            print('symbol link to {}'.format(LOG_PATH))
            os.system('ln -s /tmp/ser2net ./log')

        self.generate_conf()
        
        if not os.path.isfile('/etc/ser2net.conf'):
            print('copy ser2net.conf')
            # os.system('cp management/ser2net.conf /etc/ser2net.conf')
            # os.system('cp management/ser2net /etc/init.d/ser2net')
            # os.system('update-rc.d ser2net')

        self.context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(self.context)
        monitor.filter_by('usb-serial')
        self.observer = pyudev.MonitorObserver(monitor, self.auto_update)
        self.observer.start()
        print('initialize observer')

    def generate_conf(self):
        port_template = '{num}:telnet:0:/dev/serial_{num}:9600 8DATABITS NONE 1STOPBIT {flag} \r\n'
        with open('ser2net.conf', 'w') as _conf:
            _conf.write('TRACEFILE:log:/tmp/ser2net/port_\p-\Y\m\D.log\r\n')
            _conf.write('CONTROLPORT:localhost,4321\r\n')
            _conf.writelines([
                port_template.format(num=num, flag=' tr=log rotate')
                for num in range(BASE, BASE + MAX_SUPPORT_PORT)
            ])

MYSERIALCONFIG = SerialConfiguration()

# import pyudev
# def test(action, device):
#     print('{} {}'.format(action, device.sys_name))
#
# context = pyudev.Context()
# monitor = pyudev.Monitor.from_netlink(context)
# monitor.filter_by('usb-serial')
# observer = pyudev.MonitorObserver(monitor, test)
# observer.start()