#!/usr/bin/env python3
'''
@Project:console
@Time:5/9/2019 6:30 PM
'''
import os
import json
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
        self.context = pyudev.Context()

    def get_devices(self):
        devices = [d.sys_path for d in self.context.list_devices(subsystem='usb-serial')]
        return devices

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
                    print("Insert new device [{}]: {} ".format(idx, path))
                    self.device[idx] = path
                except ValueError:
                    print("device has reached maximum number")
                    return False

            # Update or Insert new item
            self.config[path] = dev

        return True

    def sync(self):
        print("sync config")
        for idx, path in enumerate(self.device):
            port = str(BASE + idx)
            link = '/dev/serial_' + port

            if os.path.lexists(link):
                if path:
                    if os.readlink(link) == self.config.get(path):
                        continue
                    else:
                        print("Delete symbol link: {}".format(link))
                        os.remove(link)
                        print("Create symbol link: {} -> {}".format(self.config[path], link))
                        os.symlink(self.config[path], link)
                else:
                    print("Delete invalid link: {}".format(link))
                    os.remove(link)
            else:
                if path:
                    print("Create symbol link: {} -> {}".format(self.config[path], link))
                    os.symlink(self.config[path], link)

        self.save()

    def reset(self):
        self.config = {}
        self.device = [None] * MAX_SUPPORT_PORT
        self.update()
        print("Reset. Total Devices: {}".format(len(self.config)))

    def prune(self):
        print("Delete invalid node")
        valid_devices = [self.get_pair(d)[0] for d in self.get_devices()]
        for idx, item in enumerate(self.device):
            try:
                valid_devices.index(item)
            except ValueError:
                print("Delete device [{}] :{}".format(idx, item))
                self.device[idx] = None
                if self.config.get(item):
                    del self.config[item]

        self.sync()

    def save(self):
        config = {
            'map': self.config,
            'index': self.device
        }

        with open('serial.map', 'w') as _map:
            _map.write(json.dumps(config))
        print("save serial.map")

    def load(self):
        print("load serial.map")
        try:
            with open('serial.map', 'r') as _map:
                raw = _map.read()
                config = json.loads(raw)
                self.config = config['map'] or {}
                self.device = config['index'] or {}
        except:
            print("Failed to load serial.map")

    def update(self):
        print("update")
        self.update_map(self.get_devices())
        self.sync()

    def auto_update(self, action, device):
        if action == "add":
            print('auto-update: {}  Device:{}'.format(action, device.sys_name))
            self.update_map([device.sys_path])
            self.sync()

        if action == "remove":
            path, dev = self.get_pair(device.sys_path)
            idx = self.device.index(path)
            port = str(BASE + idx)
            link = '/dev/serial_' + port
            print("auto-update: Delete symbol link: {}".format(link))
            if os.path.lexists(link):
                os.remove(link)

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

        self.load()
        monitor = pyudev.Monitor.from_netlink(self.context)
        monitor.filter_by('usb-serial')
        self.observer = pyudev.MonitorObserver(monitor, self.auto_update)
        self.observer.start()
        print('initialize observer')

    def generate_conf(self):
        port_template = '{num}:telnet:0:/dev/serial_{num}:9600 8DATABITS NONE 1STOPBIT {flag} \r\n'
        with open('ser2net.conf', 'w') as _conf:
            _conf.write('TRACEFILE:log:/tmp/ser2net/port_\p-\Y\m\D.log\r\n')
            _conf.write('CONTROLPORT:localhost,4321\r\n\r\n')
            _conf.writelines([
                port_template.format(num=num, flag=' tr=log rotate')
                for num in range(BASE, BASE + MAX_SUPPORT_PORT)
            ])


MYSERIALCONFIG = SerialConfiguration()
