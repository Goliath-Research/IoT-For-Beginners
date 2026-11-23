"""Light sensor property from Seeed grove.py grove/grove_light_sensor_v1_2.py.

light reads ADC channel and returns that value.
"""

from grove.adc import ADC

__all__ = ["GroveLightSensor"]


class GroveLightSensor(object):
    def __init__(self, channel):
        self.channel = channel
        self.adc = ADC()

    @property
    def light(self):
        value = self.adc.read(self.channel)
        return value


Grove = GroveLightSensor
