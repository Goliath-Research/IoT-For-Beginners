#include "WiFiClient.h"

#include "exchange.h"

#include <string>
#include <vector>

CapturedExchange g_exchange;
std::string g_serial;

static std::vector<uint8_t> g_rx;
static size_t g_rx_pos = 0;

void test_queue_response(const std::string &raw) {
    g_exchange.response = raw;
    g_exchange.request.clear();
    g_exchange.host.clear();
    g_exchange.port = 0;
    g_exchange.connects = 0;
    g_serial.clear();
}

WiFiClient::WiFiClient() : connected_(false) {}

int WiFiClient::connect(const char *host, uint16_t port) {
    return connect(host, port, 0);
}

int WiFiClient::connect(const char *host, uint16_t port, int32_t) {
    g_exchange.host = host ? host : "";
    g_exchange.port = port;
    g_exchange.connects += 1;
    g_rx.assign(g_exchange.response.begin(), g_exchange.response.end());
    g_rx_pos = 0;
    connected_ = true;
    return 1;
}

size_t WiFiClient::write(uint8_t data) {
    g_exchange.request.push_back(static_cast<char>(data));
    return 1;
}

size_t WiFiClient::write(const uint8_t *buf, size_t size) {
    g_exchange.request.append(reinterpret_cast<const char *>(buf), size);
    return size;
}

int WiFiClient::available() {
    if (g_rx_pos >= g_rx.size()) {
        return 0;
    }
    return static_cast<int>(g_rx.size() - g_rx_pos);
}

int WiFiClient::read() {
    if (g_rx_pos >= g_rx.size()) {
        return -1;
    }
    return g_rx[g_rx_pos++];
}

int WiFiClient::peek() {
    if (g_rx_pos >= g_rx.size()) {
        return -1;
    }
    return g_rx[g_rx_pos];
}

void WiFiClient::flush() {}

void WiFiClient::stop() {
    connected_ = false;
}

uint8_t WiFiClient::connected() {
    return connected_ ? 1 : 0;
}
