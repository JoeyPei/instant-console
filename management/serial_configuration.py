#!/usr/bin/env python3
'''
@Project:console
@Time:5/9/2019 6:30 PM
'''
import os
import syslog
import subprocess
from management.config import LOG_PATH


class SerialConfiguration:
    def __init__(self, base=2000):
        self.kernel = {}
        self.base = base
        self.change = False
        self.tag = '/tmp/ser2net_update'

    @staticmethod
    def get_devices():
        kernels = set()
        p = subprocess.Popen(['ls', '/dev'], stdout=subprocess.PIPE)
        q = subprocess.Popen(['grep', 'USB'], stdin=p.stdout, stdout=subprocess.PIPE)
        devices = q.stdout.read().decode().strip().split('\n')

        if not devices:
             return kernels

        devices.sort(key=lambda x: int(x.strip("ttyUSB")))

        if not devices[0]:
            return kernels

        for i, dev in enumerate(devices):
            p = subprocess.Popen(['udevadm', 'info', '-a', '--name=/dev/{}'.format(dev)], stdout=subprocess.PIPE)
            q = subprocess.Popen(['grep', 'KERNELS'], stdin=p.stdout, stdout=subprocess.PIPE)
            k = q.stdout.read().decode().split('\n')[2].strip().split(',')[0].split('=')[-1]
            # kernels.add((dev, k))
            kernels.add(k)

        return kernels

    def get_status(self):
        self.read_config()
        kernels = SerialConfiguration.get_devices()
        ret = dict()
        # print(kernels)
        for k, p in self.kernel.items():
            # print(k, k in kernels)
            ret[p] = k in kernels
        return ret

    def get_map(self):
        ret = dict()
        devices = os.popen('ls -l /dev | grep USB').read().split('\n')[:-1]

        for dev in devices:
            info = dev.split()
            if info[-2] == '->':
                port = info[-3]
                mapping = info[-1]
                ret[port] = 'mapping:'+ mapping
            else:
                port = info[-1]
                ret[port] = 'float'
        return ret

    def update(self):
        self.read_config()
        # print(self.kernel)
        kernels = SerialConfiguration.get_devices()
        new_node = []
        use_port = set()
        dep_port = []

        # 1. check invalid node
        for k in kernels:
            if k not in self.kernel:
                print('difference', k)
                self.change = True
                new_node.append(k)
            else:
                use_port.add(k)

        # remove unuse node
        for k in self.kernel:
            if k not in use_port:
                dep_port.append((k, self.kernel[k]))

        # 2. add new node
        for k in new_node:
            if dep_port:
                invalid, self.kernel[k] = dep_port.pop()
                del self.kernel[invalid]
            else:
                self.kernel[k] = self.base
                self.base += 1

        if new_node and not os.path.isfile(self.tag):
            os.system("touch {}".format(self.tag))

        return os.path.isfile(self.tag)

    def read_config(self):
        self.kernel = {}
        if not os.path.isfile('/etc/udev/rules.d/serial.rules'):
            self.base = self.base - self.base % 1000
            return False
        with open('/etc/udev/rules.d/serial.rules', 'r') as f:
            for line in f.readlines():
                kernel, symbol = line.split(',')
                kernel = kernel.split('==')[-1]
                port = symbol.split('+=')[-1].split('_')[-1].strip().rstrip("\"")
                self.kernel[kernel] = port
                self.base = max(int(port)+1, self.base)

    def write_config(self):
        if not self.change:
            return False

        os.system('cat /dev/null > /etc/udev/rules.d/serial.rules')
        syslog.syslog(syslog.LOG_INFO, 'update rules')
        conf = []
        for k, v in self.kernel.items():
            rule = "".join(['KERNELS==', k, ', ', 'SYMLINK+="serial_{}"'.format(v)])
            rule = rule.replace('"', '\\"')
            conf.append(rule)

        conf.sort(key=lambda x:x.split("_")[-1])
        # print(conf)
        for c in conf:
            os.system('echo {} >> /etc/udev/rules.d/serial.rules'.format(c))

        self.change = False
        return True

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

        if os.path.isfile('/etc/udev/rules.d/serial.rules'):
            self.read_config()
        self.update()
        self.write_config()


MYSERIALCONFIG = SerialConfiguration()
