#pragma once

#include <stdint.h>

enum {
    OV2640 = 0,
    JPEG = 1,
    OV2640_640x480 = 2,
    MCU2LCD_MODE = 3,
    ARDUCHIP_TEST1 = 4,
    OV2640_CHIPID_HIGH = 5,
    OV2640_CHIPID_LOW = 6,
    Auto = 7,
    Normal = 8,
    ARDUCHIP_TRIG = 9,
    CAP_DONE_MASK = 1,
    MAX_FIFO_SIZE = 0x7FFFFF
};

/* Methods referenced by camera.h. classifyImage does not call them. */
class ArduCAM {
  public:
    ArduCAM(int, int) {}
    void write_reg(int, int) {}
    uint8_t read_reg(int) { return 0; }
    void set_mode(int) {}
    void wrSensorReg8_8(int, int) {}
    void rdSensorReg8_8(int, uint8_t *) {}
    void set_format(int) {}
    void InitCAM() {}
    void OV2640_set_JPEG_size(int) {}
    void OV2640_set_Light_Mode(int) {}
    void OV2640_set_Special_effects(int) {}
    void flush_fifo() {}
    void clear_fifo_flag() {}
    void start_capture() {}
    uint8_t get_bit(int, int) { return 0; }
    uint32_t read_fifo_length() { return 0; }
    void CS_LOW() {}
    void CS_HIGH() {}
    void set_fifo_burst() {}
};
