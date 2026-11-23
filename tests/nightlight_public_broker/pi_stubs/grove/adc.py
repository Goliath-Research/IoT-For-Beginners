"""ADC stand-in so the sample loop can read a sensor value.

The nightlight and soil-moisture apps only need ADC.read(channel). The real
Seeed ADC talks to the Grove hat over I2C, which is not on this machine.
"""


class ADC:
    def __init__(self, address=0x04):
        self.address = address

    def read(self, channel):
        return 800
