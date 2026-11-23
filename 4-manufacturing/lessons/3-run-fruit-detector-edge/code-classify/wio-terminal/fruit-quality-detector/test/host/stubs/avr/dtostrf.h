#pragma once

#include <stdio.h>

/* Arduino avr/dtostrf.h: write a decimal into a caller-supplied buffer. */
inline char *dtostrf(double value, signed char width, unsigned char prec, char *buffer) {
    char format[16];
    snprintf(format, sizeof(format), "%%%d.%df", (int)width, (int)prec);
    sprintf(buffer, format, value);
    return buffer;
}
