"""GroveRelay.on/off from Seeed grove.py grove/grove_relay.py.

on() calls GPIO.write(1). off() calls GPIO.write(0).
"""

import time

from grove.gpio import GPIO

__all__ = ["GroveRelay"]


class GroveRelay(GPIO):
    def __init__(self, pin):
        super(GroveRelay, self).__init__(pin, GPIO.OUT)

    def on(self):
        self.write(1)

    def off(self):
        self.write(0)


Grove = GroveRelay
