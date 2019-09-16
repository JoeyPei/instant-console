'''
@Project:console 
@Time:5/20/2019 5:30 PM 
'''
import syslog
from management.serial_configuration import MYSERIALCONFIG
from management.config import COOKIES
from management.manage import main


if __name__ == "__main__":
    syslog.openlog("ser2net_mgmt", syslog.LOG_PID)
#    MYSERIALCONFIG.initialize()
    main()
