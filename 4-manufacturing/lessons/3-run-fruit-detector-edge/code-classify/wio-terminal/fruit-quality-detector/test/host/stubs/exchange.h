#pragma once

#include <cstdint>
#include <string>

struct CapturedExchange {
    std::string response;
    std::string request;
    std::string host;
    uint16_t port = 0;
    int connects = 0;
};

extern CapturedExchange g_exchange;
extern std::string g_serial;

void test_queue_response(const std::string &raw);
