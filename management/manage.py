'''
@Project:console 
@Time:5/16/2019 12:58 PM 
'''
import os
import asyncio
import telnetlib
from datetime import datetime
import uvloop
from sanic import Sanic
from sanic import response

from management.serial_configuration import MYSERIALCONFIG, logger
from management.config import KEEP_DAYS, LOG_PATH, MANAGE_PORT, REMOTE_SERVER

app = Sanic(__name__)
app.config.KEEP_ALIVE = False
app.config.KEEP_ALIVE_TIMEOUT = 75
app.config.REQUEST_TIMEOUT = 120
app.config.RESPONSE_TIMEOUT = 120
app.static('/favicon.ico', './favicon.ico')
app.static('/static', './static')
app.static('/log', './log')


async def rotate(path):
    while True:
        ret = os.listdir(path)
        remove = []
        now = datetime.now()
        for file in ret:
            if file.startswith('port'):
                try:
                    raw = file.split('-')[-1].split(b".")[0]
                    date = datetime.strptime(raw, '%Y%m%d')
                    period = now - date
                    if period.days > KEEP_DAYS:
                        remove.append(file)
                except Exception as e:
                    logger.info(str(e))
        logger.info('Aged log' + str(remove))
        for f in remove:
            logger.info('remove log {}'.format(path))
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
        logger.info('{} try to get status'.format(request.ip))
        conn = telnetlib.Telnet()
        conn.open('127.0.0.1', MANAGE_PORT)
        conn.read_some()
        conn.write('showshortport\r\n'.encode())
        buf = conn.read_until(b'->', timeout=3).decode()
        conn.close()
        buf = buf.split('\r\n')[2:-1]
        ret = []

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
            }

            ret.append(info)
        return response.json(ret)

    except Exception as e:
        logger.info(str(e))
        return response.json(False)

@app.route('/api/v1/map', methods=['GET'])
async def map(request):
    try:
        if request.method == 'GET':
            return response.json(MYSERIALCONFIG.config)
        elif request.method == 'POST':
            MYSERIALCONFIG.config = response.json
            MYSERIALCONFIG.sync()
            return response.json(True)
    except Exception as e:
        logger.info(str(e))
        return response.json(
            False,
            status=501
        )

@app.route('/api/v1/config')
async def config(request):
    try:
        logger.info("{} request to {} config".format(request.ip, request.method.lower()))
        if request.method == 'GET':
            with open('management/config.py', 'r') as _c:
                raw = _c.readlines()
                ret = {}
                for line in raw:
                    o = line.split('=')
                    if len(o) == 2:
                        p, q = o
                        ret[p.strip().lower()] = q.rstrip('\n').strip()
                return response.json(ret)

        elif request.method == 'POST':
            tmp = []
            for k,v in request.json.items():
                tmp.append(k.upper() + ' = ' + v)
            with open('config.py', 'w') as _c:
                _c.writelines(tmp)
            return True
        
    except Exception as e:
        logger.info(str(e))
        return response.json(
            False,
            status=501
        )

@app.route('/api/v1/action', methods=['POST'])
async def action(request):
    try:
        opmode = request.json.get('opmode')

        logger.info("{} request to execute action {}".format(request.ip, opmode))
        ret = False
        if not opmode:
            ret = False
        elif opmode == 'disconnect':
            try:
                port = request.json.get('port')
                syslog.syslog(syslog.LOG_INFO, "{} request to disconnect {}".format(request.ip, port))
                conn = telnetlib.Telnet()
                conn.open('127.0.0.1', MANAGE_PORT)
                conn.read_some()
                conn.write('disconnect {}\r\n'.format(port).encode())
                conn.close()
            except Exception as e:
                logger.info(str(e))
                return response.json(
                    False,
                    status=501
                )
        elif opmode == 'restart':
            os.system('service ser2net stop')
            os.system('service ser2net start')
            ret = True
        elif opmode == 'reboot':
            os.system('reboot')
        elif opmode == 'update':
            ret = MYSERIALCONFIG.update()
        elif opmode == 'reset':
            ret = MYSERIALCONFIG.reset()
        elif opmode == 'prune':
            ret = MYSERIALCONFIG.prune()
        elif opmode == 'generate':
            ret = MYSERIALCONFIG.write_config()

    except Exception as e:
        logger.info(str(e))
        return response.json(
            False,
            status=501
        )
    return response.json(ret)

@app.route('/api/v1/log', methods=['GET'])
async def system_log(request):
    with open('ser2net_mgmt.log', 'r') as _f:
        rtn = _f.readlines()
        return response.json('\r\n'.join(rtn))


@app.route('/api/v1/index', methods=['GET'])
async def index(request):
    logger.info("{} request to get index".format(request.ip))
    return response.json(
        {'file': os.listdir(LOG_PATH)}
    )

async def report():
    url = 'http://{}:{}/console'.format(*REMOTE_SERVER)
    async with aiohttp.ClientSession() as session:
        while True:
            await session.post(url, json=MYSERIALCONFIG.get_status())
            await asyncio.sleep(300)


def main():
    #app.add_task(rotate(LOG_PATH))
    app.run(host="0.0.0.0", port=8080, debug=False, access_log=True)

if __name__ == "__main__":
    syslog.openlog("ser2net_mgmt", syslog.LOG_PID)
    MYSERIALCONFIG.initialize()
    main()

