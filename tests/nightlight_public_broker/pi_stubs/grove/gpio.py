"""Stand-in for grove.gpio.gpio_rpi.GPIO.

Seeed grove.py (master) grove/gpio/gpio_rpi.py write() calls
RPi.GPIO.output(self.pin, output). This records that call. The Raspberry Pi
GPIO device is not present here, so the platform write itself is not run.
"""

import os


class GPIO:
    OUT = 0
    IN = 1

    def __init__(self, pin, direction=None):
        self.pin = pin
        if direction is not None:
            self.dir(direction)

    def dir(self, direction):
        return None

    def write(self, output):
        path = os.environ.get("NIGHTLIGHT_GPIO_LOG")
        if not path:
            return
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{self.pin} {int(output)}\n")
            handle.flush()
