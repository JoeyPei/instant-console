import random
import datetime

def generate_name():
    prefix = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    suffix = random.sample('zyxwvutsrqponmlkjihgfedcba1234567890',5)
    return prefix + "-" + "".join(suffix)