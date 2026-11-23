#pragma once

#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t byte;
typedef bool boolean;

#define HIGH 0x1
#define LOW 0x0
#define OUTPUT 0x1
#define INPUT_PULLUP 0x2

#define PIN_SPI_SS 1
#define WIO_KEY_C 2

template <typename A, typename B>
inline auto min(A a, B b) -> decltype(a < b ? a : b) {
    return a < b ? a : b;
}

#include "avr/pgmspace.h"
#include "WString.h"
#include "Print.h"
#include "Stream.h"

inline void yield(void) {}

unsigned long millis(void);
void delay(unsigned long ms);

void pinMode(uint8_t pin, uint8_t mode);
void digitalWrite(uint8_t pin, uint8_t value);
int digitalRead(uint8_t pin);

class HostSerial : public Print {
  public:
    size_t write(uint8_t c) override;
    void begin(unsigned long) {}
    explicit operator bool() const { return true; }
};

extern HostSerial Serial;
