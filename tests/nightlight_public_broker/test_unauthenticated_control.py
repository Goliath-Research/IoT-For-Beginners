"""Unauthenticated public-broker control of the nightlight and soil relay.

The samples connect to test.mosquitto.org port 1883, which that host documents
as MQTT without encryption or authentication, and on which unauthenticated
clients may publish every topic. These tests stand that listener in with
mosquitto 2.0.18 on 127.0.0.1: allow_anonymous true and no acl_file, which
accepts a CONNECT with no username and allows every non-$ topic. The sample
process resolves only that hostname to the local broker. Nothing is sent to
test.mosquitto.org.

An anonymous second client then publishes the command (or telemetry) the
attack uses. The actuator must not change, and the server must not publish a
command. The tests fail while the samples honor those messages.

Not executed here (named so they are not mistaken for covered paths):
- Wio Terminal firmware (PubSubClient callback, WiFi, and the board)
- Lesson snapshots that only connect or only publish
  (code-mqtt, code-telemetry, code-server) and the other lessons that use the
  same public broker for temperature or GPS
"""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import paho.mqtt.client as mqtt

REPO = Path(__file__).resolve().parents[2]
STUBS = Path(__file__).resolve().parent / "pi_stubs"
PUBLIC_BROKER = "test.mosquitto.org"
BROKER_PORT = 1883

NIGHTLIGHT_PI = REPO / "1-getting-started/lessons/4-connect-internet/code-commands/pi/nightlight/app.py"
NIGHTLIGHT_VIRTUAL = REPO / "1-getting-started/lessons/4-connect-internet/code-commands/virtual-device/nightlight/app.py"
NIGHTLIGHT_SERVER = REPO / "1-getting-started/lessons/4-connect-internet/code-commands/server/app.py"
NIGHTLIGHT_WIO_MAIN = REPO / "1-getting-started/lessons/4-connect-internet/code-commands/wio-terminal/nightlight/src/main.cpp"
NIGHTLIGHT_WIO_CONFIG = REPO / "1-getting-started/lessons/4-connect-internet/code-commands/wio-terminal/nightlight/src/config.h"

SOIL_PI = REPO / "2-farm/lessons/3-automated-plant-watering/code-mqtt/pi/soil-moisture-sensor/app.py"
SOIL_VIRTUAL = REPO / "2-farm/lessons/3-automated-plant-watering/code-mqtt/virtual-device/soil-moisture-sensor/app.py"
SOIL_SERVER = REPO / "2-farm/lessons/3-automated-plant-watering/code-mqtt/server/app.py"
SOIL_WIO_MAIN = REPO / "2-farm/lessons/3-automated-plant-watering/code-mqtt/wio-terminal/soil-moisture-sensor/src/main.cpp"
SOIL_WIO_CONFIG = REPO / "2-farm/lessons/3-automated-plant-watering/code-mqtt/wio-terminal/soil-moisture-sensor/src/config.h"

PYTHON_APPS = (
    NIGHTLIGHT_PI,
    NIGHTLIGHT_VIRTUAL,
    NIGHTLIGHT_SERVER,
    SOIL_PI,
    SOIL_VIRTUAL,
    SOIL_SERVER,
)

LAUNCHER = r"""
import os
import runpy
import socket

_real = socket.getaddrinfo

def getaddrinfo(host, port, *args, **kwargs):
    # The sample names the public broker. Deliver that TCP connection to the
    # local stand-in. Any other host is refused so this test cannot reach
    # the network.
    if host == "test.mosquitto.org":
        return _real("127.0.0.1", port, *args, **kwargs)
    if host in ("127.0.0.1", "localhost", "::1"):
        return _real(host, port, *args, **kwargs)
    raise OSError("refusing non-local connection to %s:%s" % (host, port))

socket.getaddrinfo = getaddrinfo
runpy.run_path(os.environ["SAMPLE_APP"], run_name="__main__")
"""

_broker = None
_broker_log = None


def device_id(path):
    text = Path(path).read_text(encoding="utf-8")
    match = re.search(r"^id\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
    if match is None:
        raise AssertionError("no device id assignment in %s" % path)
    return match.group(1)


def topic(path, suffix):
    return device_id(path) + suffix


class ActuatorSite(BaseHTTPRequestHandler):
    """HTTP surface the CounterFit shims call.

    counterfit_connection 0.1.0.dev5 posts /connect and /actuator_value and
    gets /sensor_value. Values are recorded for the test.
    """

    values = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else b""
        parsed = urlparse(self.path)
        if parsed.path == "/actuator_value":
            port = parse_qs(parsed.query).get("port", ["?"])[0]
            try:
                payload = json.loads(body.decode() or "{}")
            except json.JSONDecodeError:
                payload = {}
            ActuatorSite.values.append((str(port), payload.get("value")))
        self._reply(b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/sensor_value":
            self._reply(json.dumps({"value": 800}).encode())
            return
        self._reply(b"{}")

    def _reply(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def start_broker():
    global _broker, _broker_log
    log_dir = tempfile.mkdtemp(prefix="nightlight-broker-")
    config_path = os.path.join(log_dir, "mosquitto.conf")
    log_path = os.path.join(log_dir, "mosquitto.log")
    with open(config_path, "w", encoding="utf-8") as handle:
        handle.write(
            "\n".join(
                [
                    "listener %d 127.0.0.1" % BROKER_PORT,
                    "allow_anonymous true",
                    "persistence false",
                    "log_dest file %s" % log_path,
                    "connection_messages true",
                    "log_type all",
                    "",
                ]
            )
        )
    _broker_log = log_path
    _broker = subprocess.Popen(
        ["/usr/sbin/mosquitto", "-c", config_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 5
    last_error = None
    while time.time() < deadline:
        if _broker.poll() is not None:
            err = _broker.stderr.read().decode(errors="replace")
            raise RuntimeError("mosquitto exited: %s" % err)
        try:
            sock = socket.create_connection(("127.0.0.1", BROKER_PORT), timeout=0.2)
            sock.close()
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.05)
    raise RuntimeError("broker did not accept connections: %s" % last_error)


def stop_broker():
    global _broker
    if _broker is None or _broker.poll() is not None:
        return
    _broker.send_signal(signal.SIGTERM)
    try:
        _broker.wait(timeout=3)
    except subprocess.TimeoutExpired:
        _broker.kill()
        _broker.wait(timeout=3)


def broker_log():
    if not _broker_log or not os.path.exists(_broker_log):
        return ""
    with open(_broker_log, encoding="utf-8", errors="replace") as handle:
        return handle.read()


class SampleProcess:
    def __init__(self, app_path, gpio_log, pythonpath):
        self.app_path = str(app_path)
        self.gpio_log = gpio_log
        self.pythonpath = pythonpath
        self.proc = None
        self.stdout_path = None
        self.stderr_path = None
        self._stdout = None
        self._stderr = None
        self._launcher = None

    def start(self):
        launcher = tempfile.NamedTemporaryFile("w", suffix="-launch.py", delete=False)
        launcher.write(LAUNCHER)
        launcher.close()
        self._launcher = launcher.name
        self.stdout_path = tempfile.NamedTemporaryFile(prefix="sample-out-", delete=False).name
        self.stderr_path = tempfile.NamedTemporaryFile(prefix="sample-err-", delete=False).name
        self._stdout = open(self.stdout_path, "w", encoding="utf-8")
        self._stderr = open(self.stderr_path, "w", encoding="utf-8")
        env = os.environ.copy()
        env["SAMPLE_APP"] = self.app_path
        env["NIGHTLIGHT_GPIO_LOG"] = self.gpio_log
        env["PYTHONPATH"] = self.pythonpath + os.pathsep + env.get("PYTHONPATH", "")
        self.proc = subprocess.Popen(
            [sys.executable, self._launcher],
            stdout=self._stdout,
            stderr=self._stderr,
            env=env,
            start_new_session=True,
        )

    def output(self):
        self._stdout.flush()
        self._stderr.flush()
        with open(self.stdout_path, encoding="utf-8", errors="replace") as handle:
            stdout = handle.read()
        with open(self.stderr_path, encoding="utf-8", errors="replace") as handle:
            stderr = handle.read()
        return stdout, stderr

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.proc.wait(timeout=3)
        if self._stdout:
            self._stdout.close()
        if self._stderr:
            self._stderr.close()
        if self._launcher and os.path.exists(self._launcher):
            os.unlink(self._launcher)


class AnonymousClient:
    """MQTT client that never sets a username or password."""

    def __init__(self, client_id):
        self.client = mqtt.Client(client_id)
        self.messages = []
        self.client.on_message = self._on_message

    def _on_message(self, client, userdata, message):
        self.messages.append((message.topic, bytes(message.payload)))

    def connect(self):
        result = self.client.connect("127.0.0.1", BROKER_PORT, keepalive=30)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise AssertionError("anonymous client connect returned %s" % result)
        self.client.loop_start()

    def subscribe(self, topic_name):
        result, _mid = self.client.subscribe(topic_name, qos=0)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise AssertionError("subscribe returned %s" % result)

    def publish(self, topic_name, payload):
        info = self.client.publish(topic_name, payload, qos=0, retain=False)
        info.wait_for_publish(timeout=2)

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()


class UnauthenticatedBrokerTests(unittest.TestCase):
    gpio_log = None

    @classmethod
    def setUpClass(cls):
        start_broker()
        cls.gpio_dir = tempfile.mkdtemp(prefix="gpio-log-")

    @classmethod
    def tearDownClass(cls):
        stop_broker()

    def setUp(self):
        self.gpio_log = os.path.join(self.gpio_dir, "%s.log" % self.id().split(".")[-1])
        with open(self.gpio_log, "w", encoding="utf-8"):
            pass
        ActuatorSite.values = []
        self.sample = None
        self.attacker = None
        self.http = None

    def tearDown(self):
        if self.sample is not None:
            self.sample.stop()
        if self.attacker is not None:
            self.attacker.close()
        if self.http is not None:
            self.http.shutdown()
            self.http.server_close()

    def start_counterfit(self):
        self.http = ThreadingHTTPServer(("127.0.0.1", 5000), ActuatorSite)
        thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        thread.start()

    def start_sample(self, app_path, virtual):
        pythonpath = "" if virtual else str(STUBS)
        self.sample = SampleProcess(app_path, self.gpio_log, pythonpath)
        self.sample.start()

    def gpio_writes(self):
        with open(self.gpio_log, encoding="utf-8") as handle:
            return [line.strip() for line in handle if line.strip()]

    def assert_no_actuation(self, detail):
        stdout, stderr = self.sample.output()
        writes = self.gpio_writes()
        actuator = list(ActuatorSite.values)
        alive = self.sample.proc.poll() is None
        if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
            self.fail("sample failed to import:\n%s" % stderr)
        if writes or actuator:
            self.fail(
                "anonymous client drove the actuator\nwrites=%s\nactuator=%s\nstdout=%s\nstderr=%s\nbroker=%s"
                % (writes, actuator, stdout, stderr, broker_log())
            )
        if not alive:
            allowed = (
                "ConnectionRefusedError",
                "OSError",
                "SSLError",
                "certificate",
                "MQTT",
                "Not authorized",
                "refusing non-local",
            )
            if "Traceback" in stderr and not any(token in stderr for token in allowed):
                self.fail("sample exited before it could be tested:\n%s\n%s" % (stderr, detail))

    def wait_until_subscribed(self, topic_name):
        start = len(broker_log())
        deadline = time.time() + 5
        while time.time() < deadline:
            if self.sample.proc.poll() is not None:
                return False
            chunk = broker_log()[start:]
            if "SUBSCRIBE" in chunk and topic_name in chunk:
                return True
            time.sleep(0.05)
        return False

    def attack_commands(self, app_path, virtual, payloads):
        if virtual:
            self.start_counterfit()
        self.start_sample(app_path, virtual)
        command_topic = topic(app_path, "/commands")
        subscribed = self.wait_until_subscribed(command_topic)
        if self.sample.proc.poll() is None and not subscribed:
            stdout, stderr = self.sample.output()
            self.fail(
                "sample stayed connected but never subscribed to %s\nstdout=%s\nstderr=%s\nbroker=%s"
                % (command_topic, stdout, stderr, broker_log())
            )
        self.attacker = AnonymousClient("anonymous-attacker")
        self.attacker.connect()
        for payload in payloads:
            self.attacker.publish(command_topic, json.dumps(payload))
        time.sleep(1.5)
        self.assert_no_actuation("command topic %s" % command_topic)

    def test_pi_nightlight_anonymous_command_does_not_drive_led(self):
        self.attack_commands(
            NIGHTLIGHT_PI,
            virtual=False,
            payloads=[{"led_on": True}, {"led_on": False}],
        )

    def test_virtual_nightlight_anonymous_command_does_not_drive_led(self):
        self.attack_commands(
            NIGHTLIGHT_VIRTUAL,
            virtual=True,
            payloads=[{"led_on": True}, {"led_on": False}],
        )

    def test_pi_soil_anonymous_command_does_not_drive_relay(self):
        self.attack_commands(
            SOIL_PI,
            virtual=False,
            payloads=[{"relay_on": True}, {"relay_on": False}],
        )

    def test_virtual_soil_anonymous_command_does_not_drive_relay(self):
        self.attack_commands(
            SOIL_VIRTUAL,
            virtual=True,
            payloads=[{"relay_on": True}, {"relay_on": False}],
        )

    def test_pi_nightlight_anonymous_subscriber_does_not_receive_telemetry(self):
        self.attacker = AnonymousClient("anonymous-subscriber")
        self.attacker.connect()
        telemetry_topic = topic(NIGHTLIGHT_PI, "/telemetry")
        self.attacker.subscribe(telemetry_topic)
        time.sleep(0.3)
        self.start_sample(NIGHTLIGHT_PI, virtual=False)
        deadline = time.time() + 5
        while time.time() < deadline and not self.attacker.messages:
            time.sleep(0.1)
        self.assert_no_actuation("telemetry topic %s" % telemetry_topic)
        self.assertEqual(
            self.attacker.messages,
            [],
            "anonymous subscriber received telemetry %s" % self.attacker.messages,
        )

    def _assert_server_ignores_telemetry(self, server_path, payload):
        self.attacker = AnonymousClient("anonymous-telemetry")
        self.attacker.connect()
        command_topic = topic(server_path, "/commands")
        telemetry_topic = topic(server_path, "/telemetry")
        self.attacker.subscribe(command_topic)
        time.sleep(0.3)
        self.start_sample(server_path, virtual=False)
        subscribed = self.wait_until_subscribed(telemetry_topic)
        if self.sample.proc.poll() is None and not subscribed:
            stdout, stderr = self.sample.output()
            self.fail(
                "server stayed connected but never subscribed to %s\nstdout=%s\nstderr=%s\nbroker=%s"
                % (telemetry_topic, stdout, stderr, broker_log())
            )
        self.attacker.publish(telemetry_topic, json.dumps(payload))
        deadline = time.time() + 3
        while time.time() < deadline and not self.attacker.messages:
            time.sleep(0.1)
        stdout, stderr = self.sample.output()
        if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
            self.fail(stderr)
        self.assertEqual(
            self.attacker.messages,
            [],
            "server published a command for anonymous telemetry %s\nstdout=%s\nstderr=%s\nbroker=%s"
            % (self.attacker.messages, stdout, stderr, broker_log()),
        )

    def test_nightlight_server_anonymous_telemetry_does_not_publish_command(self):
        self._assert_server_ignores_telemetry(NIGHTLIGHT_SERVER, {"light": 0})

    def test_soil_server_anonymous_telemetry_does_not_publish_command(self):
        self._assert_server_ignores_telemetry(SOIL_SERVER, {"soil_moisture": 900})

    def test_samples_do_not_use_the_public_broker_without_credentials(self):
        for path in PYTHON_APPS:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                PUBLIC_BROKER,
                text,
                "%s still names the public broker" % path,
            )
            self.assertIn(
                "username_pw_set(",
                text,
                "%s never sets MQTT credentials" % path,
            )
            self.assertTrue(
                "tls_set(" in text or "tls_set_context(" in text,
                "%s never enables TLS" % path,
            )
        for main, config in (
            (NIGHTLIGHT_WIO_MAIN, NIGHTLIGHT_WIO_CONFIG),
            (SOIL_WIO_MAIN, SOIL_WIO_CONFIG),
        ):
            main_text = main.read_text(encoding="utf-8")
            config_text = config.read_text(encoding="utf-8")
            self.assertNotIn(PUBLIC_BROKER, config_text, "%s still names the public broker" % config)
            self.assertNotIn(PUBLIC_BROKER, main_text, "%s still names the public broker" % main)
            self.assertIsNotNone(
                re.search(r"client\.connect\([^;\n]*,", main_text),
                "%s connects with no username argument" % main,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
