#pragma once

static const int WL_CONNECTED = 3;

class WiFiClass {
  public:
    int status() { return WL_CONNECTED; }
    void begin(const char *, const char *) {}
};

extern WiFiClass WiFi;
