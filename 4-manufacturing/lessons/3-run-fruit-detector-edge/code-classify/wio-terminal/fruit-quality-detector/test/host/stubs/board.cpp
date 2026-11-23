#include "Arduino.h"
#include "SPI.h"
#include "Wire.h"
#include "exchange.h"
#include "rpcWiFi.h"

HostSerial Serial;
SPIClass SPI;
TwoWire Wire;
WiFiClass WiFi;

size_t HostSerial::write(uint8_t c) {
    g_serial.push_back(static_cast<char>(c));
    return 1;
}

static unsigned long g_millis = 0;

unsigned long millis(void) {
    return g_millis++;
}

void delay(unsigned long) {
    g_millis += 1;
}

void pinMode(uint8_t, uint8_t) {}

void digitalWrite(uint8_t, uint8_t) {}

int digitalRead(uint8_t) {
    return HIGH;
}
