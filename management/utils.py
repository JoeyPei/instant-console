import asyncio
import aiohttp
import re
import json

from management.secret import decodeURL, orginalAuthUrl, decodeURLReferer
from management.config import COOKIES

try:
    f = open('./cookies', 'r')
    COOKIES = json.load(f)
except:
    pass

async def authLoginSSO(username, password):
    # Use session module to keep cookies
    async with aiohttp.ClientSession() as session:
        phase1Request = await session.get(orginalAuthUrl, ssl=False)

        phase1AuthData = {
            'pf.username': username,
            'pf.pass': password,
            'pf.ok': '',
            'pf.cancel': ''
        }

        phase5Auth = await session.post(phase1Request.url, data=phase1AuthData, ssl=False)
        # Phase 6:
        # SAML auth
        resp = await phase5Auth.text()
        m = re.search('name="SAMLResponse" value="(.+)"', resp)
        samlResponse = m.group(1)
        m = re.search('name="RelayState" value="(.+)"', resp)
        relayState = m.group(1)
        m = re.search('form method="post" action="(.+)"', resp)
        samlDest = m.group(1)
        phase6Auth = await session.post(samlDest, data={'SAMLResponse':samlResponse, 'RelayState':relayState}, ssl=False)

        # Phase 7:
        resp = await phase6Auth.text()
        m = re.search('form method="post" action="(.+)"', resp)
        authPhase7Host = m.group(1)
        m = re.search('name="TargetResource" value="(.+)"', resp)
        authPhase7TargetSource = m.group(1)
        m = re.search('name="REF" value="(.+)"', resp)
        authPhase7REF = m.group(1)
        phase7Auth =  await session.post(authPhase7Host, data={'TargetResource': authPhase7TargetSource, 'REF': authPhase7REF}, ssl=False)

        resp = await phase7Auth.text()
        m = re.search("\"email\":\"([a-zA-Z\d\.]+@hpe.com)\"", resp)
        hpe_email = m.group(1).strip()
        # okay...this page has been changed

        my_cookies = phase7Auth.cookies#session.cookie_jar

        COOKIES['sessionid'] = my_cookies['sessionid'].value
        COOKIES['csrftoken'] = my_cookies['csrftoken'].value
        COOKIES['username'] = username
        # COOKIES['hpe_email'] = hpe_email
        print(COOKIES)
        with open("./cookies", 'w') as _f:
            _f.write(json.dumps(COOKIES))

        with open("./user", 'w') as _f:
            _f.write(hpe_email)

    return True


async def get_support_passwd(token):
    otpData = {
        "reason": "linux_cmds",
        "key": token.replace('-', ''),
        "decode_type": "aos"
    }

    if COOKIES is None:
        return False
    async with aiohttp.ClientSession(cookies=COOKIES) as session:
        tokenPost = await session.post(decodeURL, headers={'Referer': decodeURLReferer, 'X-CSRFToken': COOKIES['csrftoken']}, ssl=False, data=json.dumps(otpData))
        resp = await tokenPost.text()
        print(resp)
        otp = json.loads(resp).get('password').strip('\x00')
        print(otp)
    return otp

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(authLoginSSO("jypei@arubanetworks.com", "joey@2020"))
    loop.run_until_complete(get_support_passwd("B68E-C853-D53F-9BA0"))
