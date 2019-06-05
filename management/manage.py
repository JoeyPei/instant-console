'''
@Project:console 
@Time:5/16/2019 12:58 PM 
'''
import os
import syslog
import asyncio
import telnetlib
from datetime import datetime
import uvloop
from sanic import Sanic
from sanic import response
from management.serial_configuration import MYSERIALCONFIG
from management.profile import KEEP_DAYS, LOG_PATH

app = Sanic(__name__)
app.config.KEEP_ALIVE = False
app.config.KEEP_ALIVE_TIMEOUT = 75
app.config.REQUEST_TIMEOUT = 120
app.config.RESPONSE_TIMEOUT = 120
app.static('/favicon.ico', './favicon.ico')
app.static('/static', './static')
app.static('/log', './log')

MANAGE_PORT = 4321


class DiscoveryProtocol:
    def __init__(self):
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        print("Received:", data.decode())

        print("Close the socket")
        self.transport.close()

    def error_received(self, exc):
        print('Error received:', exc)

    def connection_lost(self, exc):
        print("Socket closed, stop the event loop")


async def rotate(path):
    while True:
        ret = os.listdir(path)
        remove = []
        now = datetime.now()
        for file in ret:
            if file.startswith('port'):
                try:
                    raw = file.split('-')[-1].split('.')[0]
                    date = datetime.strptime(raw, '%Y%m%d')
                    period = now - date
                    if period.days > KEEP_DAYS:
                        remove.append(file)
                except Exception as e:
                    syslog.syslog(syslog.LOG_ERR, str(e))
        syslog.syslog(syslog.LOG_INFO, 'Aged log' + str(remove))
        for f in remove:
            syslog.syslog(syslog.LOG_INFO, 'remove log {}'.format(path))
            os.remove(os.path.join(path, f))
        await asyncio.sleep(3600)


@app.route('/')
async def index(request):
    return await response.file('index.html')

@app.route('/api/v1/ser2net/status', methods=['GET'])
async def status(request):
    ret = os.popen('service ser2net status | grep Active').read().strip()
    return response.text(ret)

@app.route('/api/v1/device/status', methods=['GET'])
async def status(request):
    try:
        syslog.syslog(syslog.LOG_INFO, '{} try to get status'.format(request.ip))
        conn = telnetlib.Telnet()
        conn.open('127.0.0.1', MANAGE_PORT)
        conn.read_some()
        conn.write('showshortport\r\n'.encode())
        buf = conn.read_until(b'->', timeout=3).decode()
        conn.close()
        buf = buf.split('\r\n')[2:-1]
        ret = []
        mapping = MYSERIALCONFIG.get_map()

        for i in range(len(buf)):
            line = buf[i].split()
            device = line[4].split('/')[-1]

            if device not in mapping:
                continue
            info = {
                'port': line[0],
                'timeout': line[2],
                'connect': line[3],
                'device': line[4],
                'in': line[5],
                'out': line[6],
                'status': mapping[device]
            }
            # print(info)
            ret.append(info)
        return response.json(ret)

    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, str(e))
        return response.json(False)


@app.route('/api/v1/disconnect', methods=['POST'])
async def disconnect(request):
    try:
        port = request.json.get('port')
        syslog.syslog(syslog.LOG_INFO, "{} request to disconnect {}".format(request.ip, port))
        conn = telnetlib.Telnet()
        conn.open('127.0.0.1', MANAGE_PORT)
        conn.read_some()
        conn.write('disconnect {}\r\n'.format(port).encode())
        conn.close()
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, str(e))
        return response.json(
            False,
            status=501
        )
    return response.json(True)


@app.route('/api/v1/action', methods=['POST'])
async def action(request):
    try:
        opmode = request.json.get('opmode')

        syslog.syslog(syslog.LOG_INFO, "{} request to execute action {}".format(request.ip, opmode))
        ret = False
        if not opmode:
            ret = False
        elif opmode == 'restart':
            os.system('service ser2net stop')
            os.system('service ser2net start')
            ret = True
        elif opmode == 'reboot':
            os.system('reboot')
            ret = True
        elif opmode == 'detect':
            ret = MYSERIALCONFIG.update()
        elif opmode == 'generate':
            ret = MYSERIALCONFIG.write_config()
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR, str(e))
        return response.json(
            False,
            status=501
        )
    return response.json(ret)


@app.route('/api/v1/index', methods=['GET'])
async def index(request):
    syslog.syslog(syslog.LOG_INFO, "{} request to get index".format(request.ip))
    return response.json(
        {'file': os.listdir(LOG_PATH)}
    )


def main():
    app.add_task(rotate(LOG_PATH))
    app.run(host="0.0.0.0", port=80, debug=False, access_log=True)

if __name__ == "__main__":
    syslog.openlog("ser2net_mgmt", syslog.LOG_PID)
    MYSERIALCONFIG.initialize()
    main()

