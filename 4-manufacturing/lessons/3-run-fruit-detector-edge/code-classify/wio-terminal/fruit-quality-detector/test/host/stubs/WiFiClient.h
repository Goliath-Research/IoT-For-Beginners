#pragma once

#include "Stream.h"

#include <stddef.h>
#include <stdint.h>

/*
 * Stand-in for Seeed Arduino rpcWiFi 1.0.5 WiFiClient.
 * connect() succeeds and read() returns the bytes queued by the test.
 * Those bytes are the HTTP response the peer sent. This object does not
 * parse or resize them; HTTPClient does that.
 */
class WiFiClient : public Stream {
  public:
    WiFiClient();
    int connect(const char *host, uint16_t port);
    int connect(const char *host, uint16_t port, int32_t timeout);
    size_t write(uint8_t data) override;
    size_t write(const uint8_t *buf, size_t size) override;
    int available() override;
    int read() override;
    int peek() override;
    void flush() override;
    void stop();
    uint8_t connected();

  private:
    bool connected_;
};
