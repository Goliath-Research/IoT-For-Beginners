#!/usr/bin/env bash
# Host tests for the Wio Terminal edge fruit classifier.
# They compile src/main.cpp with the HTTP client and JSON library the sketch pins,
# then call classifyImage. The suite exits non-zero while a long tagName overflows
# the 32-byte stack buffer.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SKETCH="$(cd "$ROOT/../.." && pwd)"
CACHE="${ROOT}/third_party"
BUILD="${ROOT}/build"
JSON_TAG="v6.17.3"
WIFI_TAG="v1.0.5"
CORE_COMMIT="2e6b174f81b988964ce3811f5b5e39297c2c9c3f"

fetch() {
    local url="$1"
    local dest="$2"
    if [[ -d "$dest" ]]; then
        return
    fi
    mkdir -p "$(dirname "$dest")"
    local tar="${dest}.tar.gz"
    curl -fsSL "$url" -o "$tar"
    tar -xzf "$tar" -C "$(dirname "$dest")"
    rm -f "$tar"
}

fetch "https://github.com/bblanchon/ArduinoJson/archive/refs/tags/${JSON_TAG}.tar.gz" \
    "${CACHE}/ArduinoJson-${JSON_TAG#v}"
fetch "https://github.com/Seeed-Studio/Seeed_Arduino_rpcWiFi/archive/refs/tags/${WIFI_TAG}.tar.gz" \
    "${CACHE}/Seeed_Arduino_rpcWiFi-${WIFI_TAG#v}"

if [[ ! -d "${CACHE}/ArduinoCore-samd" ]]; then
    git clone --depth 1 https://github.com/Seeed-Studio/ArduinoCore-samd.git "${CACHE}/ArduinoCore-samd"
    git -C "${CACHE}/ArduinoCore-samd" fetch --depth 1 origin "${CORE_COMMIT}"
    git -C "${CACHE}/ArduinoCore-samd" checkout --detach "${CORE_COMMIT}"
fi

rm -rf "$BUILD"
mkdir -p "$BUILD/core" "$BUILD/sketch"
cp "${CACHE}/ArduinoCore-samd/cores/arduino/WString.cpp" "$BUILD/core/"
# String::remove slides the tail with strncpy. The ranges overlap, which is
# what that function does on the board. Host ASan rejects overlapping strncpy,
# so the build copy uses memmove, which yields the same tail.
sed -i 's/strncpy(writeTo, buffer + index + count,len - index);/memmove(writeTo, buffer + index + count, len - index);/' \
    "$BUILD/core/WString.cpp"
sed -i 's/if (begin > buffer) memcpy(buffer, begin, len);/if (begin > buffer) memmove(buffer, begin, len);/' \
    "$BUILD/core/WString.cpp"
cp "${CACHE}/ArduinoCore-samd/cores/arduino/Print.cpp" "$BUILD/core/"
cp "${CACHE}/ArduinoCore-samd/cores/arduino/Stream.cpp" "$BUILD/core/"
cp "${CACHE}/ArduinoCore-samd/cores/arduino/StreamString.cpp" "$BUILD/core/"
# Quoted includes in main.cpp resolve next to this symlink, so lesson_config.h
# supplies the http URL from the edge lesson without editing src/config.h.
ln -s "${SKETCH}/src/main.cpp" "$BUILD/sketch/main.cpp"
cp "${ROOT}/lesson_config.h" "$BUILD/sketch/config.h"

CXXFLAGS=(
    -std=c++17
    -g
    -O1
    -fno-omit-frame-pointer
    -fsanitize=address,undefined
    -fno-sanitize-recover=address,undefined
    -DARDUINO=10815
    -DARDUINOJSON_ENABLE_PROGMEM=0
    -I "${ROOT}/stubs"
    -I "${CACHE}/ArduinoCore-samd/cores/arduino"
    -I "${CACHE}/Seeed_Arduino_rpcWiFi-${WIFI_TAG#v}/src"
    -I "${CACHE}/ArduinoJson-${JSON_TAG#v}"
    -I "${CACHE}/ArduinoJson-${JSON_TAG#v}/src"
    -I "${SKETCH}/src"
)

SRCS=(
    "$BUILD/core/WString.cpp"
    "$BUILD/core/Print.cpp"
    "$BUILD/core/Stream.cpp"
    "$BUILD/core/StreamString.cpp"
    "${CACHE}/Seeed_Arduino_rpcWiFi-${WIFI_TAG#v}/src/HTTPClient.cpp"
    "${ROOT}/stubs/itoa.cpp"
    "${ROOT}/stubs/base64.cpp"
    "${ROOT}/stubs/WiFiClient.cpp"
    "${ROOT}/stubs/board.cpp"
    "$BUILD/sketch/main.cpp"
    "${ROOT}/test_classify.cpp"
)

g++ "${CXXFLAGS[@]}" "${SRCS[@]}" -o "$BUILD/classify_tests"

fail=0
run() {
    local name="$1"
    if "$BUILD/classify_tests" "$name"; then
        echo "PASS $name"
    else
        echo "FAIL $name"
        fail=1
    fi
}

run short_label
run long_label
run second_prediction
run long_label_fits_document
run http_error

exit "$fail"
