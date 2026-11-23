"""Camera uploads from the edge fruit detector must not be readable in cleartext.

The lesson tells the student to point each client at
``http://<IP address or name>/image`` and the samples post the camera buffer to
that URL. These tests follow that instruction against a local listener.

They fail while the JPEG bytes are present on the cleartext TCP connection, and
pass once the client sends the image only inside TLS (Wio Terminal must also
validate the server certificate). No product source is modified here.

Not an upload path, so not executed: the IoT Edge deployment manifest and the
virtual-machine port-80 instructions only publish the classifier. They do not
send a camera buffer.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LESSON = REPO / "4-manufacturing" / "lessons" / "3-run-fruit-detector-edge"
PI_APP = LESSON / "code-classify" / "pi" / "fruit-quality-detector" / "app.py"
VIRTUAL_APP = (
    LESSON
    / "code-classify"
    / "virtual-iot-device"
    / "fruit-quality-detector"
    / "app.py"
)
WIO_MAIN = (
    LESSON
    / "code-classify"
    / "wio-terminal"
    / "fruit-quality-detector"
    / "src"
    / "main.cpp"
)
WIO_CONFIG = (
    LESSON
    / "code-classify"
    / "wio-terminal"
    / "fruit-quality-detector"
    / "src"
    / "config.h"
)

# Seeed Arduino rpcWiFi 1.0.5 HTTPClient.h: HTTP_TCP_BUFFER_SIZE.
HTTP_TCP_BUFFER_SIZE = 1460

# Larger than one HTTPClient write chunk so the replay has to loop, as
# HTTPClient::sendRequest does, and still reassemble to the original buffer.
_MARKER = b"EDGE-CAMERA-JPEG-PAYLOAD"
JPEG = b"\xff\xd8" + (_MARKER * 80) + b"\xff\xd9"


class CleartextListener:
    """Accept one TCP connection and record the bytes that arrive before TLS."""

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.port = self._sock.getsockname()[1]
        self.captured = b""
        self.connected = False
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        self._sock.settimeout(8)
        try:
            conn, _addr = self._sock.accept()
        except socket.timeout:
            return
        self.connected = True
        try:
            conn.settimeout(1.0)
            data = b""
            while True:
                try:
                    chunk = conn.recv(65536)
                except socket.timeout:
                    break
                if not chunk:
                    break
                data += chunk
                if _http_request_complete(data):
                    break
            self.captured = data
            body = b'{"predictions":[{"tagName":"ripe","probability":0.5}]}'
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: "
                + str(len(body)).encode("ascii")
                + b"\r\nConnection: close\r\n\r\n"
                + body
            )
            try:
                conn.sendall(response)
            except OSError:
                pass
        finally:
            conn.close()

    def close(self):
        self._thread.join(timeout=10)
        self._sock.close()


def _http_request_complete(data: bytes) -> bool:
    header_end = data.find(b"\r\n\r\n")
    if header_end < 0:
        return False
    header = data[:header_end].decode("iso-8859-1", "replace")
    match = re.search(r"(?im)^Content-Length:\s*(\d+)\s*$", header)
    if not match:
        return False
    return len(data) >= header_end + 4 + int(match.group(1))


def classifier_url_from_lesson(markdown: Path, host: str, port: int) -> str:
    """The URL the lesson tells the student to put in the prediction client."""
    text = markdown.read_text(encoding="utf-8")
    match = re.search(r"The URL for the Image Classifier is `([^`]+)`", text)
    if match:
        template = match.group(1)
    else:
        curl = re.search(r"--request POST '([^']+)'", text)
        if not curl:
            raise AssertionError(f"no classifier URL in {markdown}")
        template = curl.group(1)
    if "<IP address or name>" not in template:
        raise AssertionError(f"classifier URL template lost its host placeholder: {template}")
    return template.replace("<IP address or name>", f"{host}:{port}")


def _retarget(url: str, host: str, port: int) -> str:
    """Keep the scheme and path the sample already chose; aim the host at the listener."""
    match = re.match(r"^(https?)://[^/]+(.*)$", url)
    if not match:
        return url
    scheme, path = match.group(1), match.group(2) or "/image"
    return f"{scheme}://{host}:{port}{path}"


def configure_prediction_url(source: str, lesson_url: str, host: str, port: int) -> str:
    """Perform the replacement the lesson tells the student to make.

    A placeholder is replaced with the lesson's classifier URL. A sample that
    already contains an http or https URL keeps that scheme.
    """
    pattern = re.compile(
        r"""^(?P<indent>\s*)prediction_url\s*=\s*(?P<q>['\"])(?P<value>.*?)(?P=q)\s*$""",
        re.M,
    )
    match = pattern.search(source)
    if not match:
        raise AssertionError("prediction_url assignment missing from sample")
    value = match.group("value")
    if value.startswith("http://") or value.startswith("https://"):
        chosen = _retarget(value, host, port)
    else:
        chosen = lesson_url
    replacement = (
        f"{match.group('indent')}prediction_url = {match.group('q')}{chosen}{match.group('q')}"
    )
    return source[: match.start()] + replacement + source[match.end() :]


def _install_camera_stubs(jpeg: bytes) -> None:
    camera_mod = types.ModuleType("picamera")

    class PiCamera:
        def __init__(self):
            self.resolution = None
            self.rotation = 0

        def capture(self, stream, fmt):
            assert fmt == "jpeg"
            stream.write(jpeg)

    camera_mod.PiCamera = PiCamera
    sys.modules["picamera"] = camera_mod

    shims = types.ModuleType("counterfit_shims_picamera")
    shims.PiCamera = PiCamera
    sys.modules["counterfit_shims_picamera"] = shims

    connection = types.ModuleType("counterfit_connection")

    class CounterFitConnection:
        @staticmethod
        def init(host, port):
            return None

    connection.CounterFitConnection = CounterFitConnection
    sys.modules["counterfit_connection"] = connection


def _clear_proxy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if "proxy" in name.lower():
            monkeypatch.delenv(name, raising=False)


def run_python_uploader(app_path: Path, lesson_markdown: Path, jpeg: bytes, listener: CleartextListener, monkeypatch: pytest.MonkeyPatch):
    lesson_url = classifier_url_from_lesson(lesson_markdown, "127.0.0.1", listener.port)
    source = configure_prediction_url(
        app_path.read_text(encoding="utf-8"),
        lesson_url,
        "127.0.0.1",
        listener.port,
    )
    _install_camera_stubs(jpeg)
    _clear_proxy_env(monkeypatch)
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)
    work = Path(tempfile.mkdtemp(prefix="fruit-upload-"))
    previous = os.getcwd()
    os.chdir(work)
    error = None
    try:
        exec(compile(source, str(app_path), "exec"), {"__name__": "__main__"})
    except Exception as exc:  # the sample has no handler; refusal raises
        error = exc
    finally:
        os.chdir(previous)
    listener.close()
    return error


def assert_jpeg_not_cleartext(listener: CleartextListener, jpeg: bytes, error: BaseException | None, where: str) -> None:
    if jpeg in listener.captured:
        preview = listener.captured[:120]
        pytest.fail(
            f"{where} sent the camera buffer on a cleartext TCP connection "
            f"(connected={listener.connected}, first bytes={preview!r}, error={error!r})"
        )
    if not listener.connected:
        if isinstance(error, (ImportError, ModuleNotFoundError, NameError, SyntaxError)):
            raise error
        if error is None:
            pytest.fail(f"{where} returned without connecting and without refusing the upload")
        return
    # A connection that does not contain the image is TLS (or a refusal after connect).


@pytest.mark.parametrize(
    "app_path",
    [PI_APP, VIRTUAL_APP],
    ids=["pi", "virtual-iot-device"],
)
def test_python_camera_upload_is_not_cleartext(app_path: Path, monkeypatch: pytest.MonkeyPatch):
    listener = CleartextListener()
    error = run_python_uploader(
        app_path,
        LESSON / "single-board-computer.md",
        JPEG,
        listener,
        monkeypatch,
    )
    assert_jpeg_not_cleartext(listener, JPEG, error, str(app_path.relative_to(REPO)))


def _wio_uses_tls_client(source: str) -> bool:
    declared = re.search(r"(?m)^\s*WiFiClientSecure\s+client\s*;", source) is not None
    included = re.search(r'#include\s*[<"]WiFiClientSecure\.h[>"]', source) is not None
    plain = re.search(r"(?m)^\s*WiFiClient\s+client\s*;", source) is not None
    return declared and included and not plain


def _wio_sets_ca_cert(source: str) -> bool:
    return re.search(r"\bclient\.setCACert\s*\(", source) is not None


def _wio_prediction_url(host: str, port: int) -> str:
    config = WIO_CONFIG.read_text(encoding="utf-8")
    match = re.search(r'PREDICTION_URL\s*=\s*"([^"]*)"', config)
    if not match:
        raise AssertionError("PREDICTION_URL missing from Wio config.h")
    value = match.group(1)
    if value.startswith("http://") or value.startswith("https://"):
        return _retarget(value, host, port)
    return classifier_url_from_lesson(LESSON / "wio-terminal.md", host, port)


def _http_client_post(host: str, port: int, url: str, payload: bytes, tls: bool) -> None:
    """Replay HTTPClient::POST for the client class the sample constructs.

    Plain WiFiClient::write sends the header and the payload with send() and no
    TLS. WiFiClientSecure::write passes the same bytes to send_ssl_data, so this
    replay keeps them inside a TLS record. The replay follows begin(), addHeader(),
    sendRequest(), and sendHeader() from Seeed Arduino rpcWiFi 1.0.5: protocol and
    port from the URL, Content-Length before the header, then the body in
    HTTP_TCP_BUFFER_SIZE chunks.
    """
    parsed = re.match(r"^(https?)://([^/:]+)(?::(\d+))?(/.*)?$", url)
    if not parsed:
        raise RuntimeError(f"HTTPClient::begin rejects {url!r}")
    scheme, url_host, url_port, uri = parsed.groups()
    if scheme not in ("http", "https"):
        raise RuntimeError(f"HTTPClient::begin rejects scheme {scheme!r}")
    port_num = int(url_port) if url_port else (443 if scheme == "https" else 80)
    uri = uri or "/"
    header = f"POST {uri} HTTP/1.1\r\nHost: {url_host}"
    if port_num not in (80, 443):
        header += f":{port_num}"
    header += "\r\nUser-Agent: WioTerminalHTTPClient\r\nConnection: keep-alive\r\n"
    header += "Accept-Encoding: identity;q=1,chunked;q=0.1,*;q=0\r\n"
    header += "Content-Type: application/octet-stream\r\n"
    header += f"Content-Length: {len(payload)}\r\n\r\n"

    raw = socket.create_connection((host, port), timeout=5)
    try:
        if tls:
            context = __import__("ssl").create_default_context()
            try:
                wrapped = context.wrap_socket(raw, server_hostname=url_host)
            except __import__("ssl").SSLError:
                return
            raw = wrapped
        raw.sendall(header.encode("latin1"))
        for pos in range(0, len(payload), HTTP_TCP_BUFFER_SIZE):
            chunk = payload[pos : pos + HTTP_TCP_BUFFER_SIZE]
            sent = raw.send(chunk)
            if sent != len(chunk):
                raw.sendall(chunk[sent:])
    finally:
        raw.close()


def test_wio_camera_upload_is_not_cleartext():
    source = WIO_MAIN.read_text(encoding="utf-8")
    if "httpClient.POST" not in source or "classifyImage" not in source:
        pytest.fail("Wio classifyImage POST path is missing")
    tls = _wio_uses_tls_client(source)
    listener = CleartextListener()
    url = _wio_prediction_url("127.0.0.1", listener.port)
    error = None
    try:
        _http_client_post("127.0.0.1", listener.port, url, JPEG, tls)
    except Exception as exc:
        error = exc
    listener.close()
    assert_jpeg_not_cleartext(listener, JPEG, error, "wio-terminal classifyImage")
    if not _wio_sets_ca_cert(source):
        pytest.fail(
            "Wio Wi-Fi client does not call client.setCACert, so the TLS handshake "
            "is not pinned to a certificate the device trusts"
        )


@pytest.mark.parametrize(
    "markdown",
    [
        LESSON / "README.md",
        LESSON / "translations" / "README.bn.md",
    ],
    ids=["readme-curl", "readme-bn-curl"],
)
def test_lesson_curl_upload_is_not_cleartext(markdown: Path, tmp_path: Path):
    listener = CleartextListener()
    url = classifier_url_from_lesson(markdown, "127.0.0.1", listener.port)
    image = tmp_path / "frame.jpg"
    image.write_bytes(JPEG)
    completed = subprocess.run(
        [
            "curl",
            "--silent",
            "--show-error",
            "--max-time",
            "5",
            "--location",
            "--request",
            "POST",
            url,
            "--header",
            "Content-Type: image/png",
            "--data-binary",
            f"@{image}",
        ],
        check=False,
        capture_output=True,
    )
    listener.close()
    error = None
    if completed.returncode != 0:
        error = RuntimeError(completed.stderr.decode("utf-8", "replace") or f"curl exit {completed.returncode}")
    assert_jpeg_not_cleartext(listener, JPEG, error, f"curl in {markdown.relative_to(REPO)}")
