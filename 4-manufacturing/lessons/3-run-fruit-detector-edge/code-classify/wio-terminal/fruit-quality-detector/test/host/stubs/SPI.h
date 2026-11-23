#pragma once

#include <stdint.h>

class SPIClass {
  public:
    void begin() {}
    uint8_t transfer(uint8_t) { return 0; }
};

extern SPIClass SPI;
