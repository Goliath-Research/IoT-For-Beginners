"""Internet clients must not be able to score images on the edge classifier.

The manufacturing lesson tells a student to deploy a public IoT Edge VM and
then open TCP port 80. These tests follow that path:

1. Parse every ``az network nsg rule create`` command in ``vm-iotedge.md``.
2. Apply the argument defaults and singular/plural collapse from Azure CLI
   2.93.0 (``azure-cli-2.93.0``), which is the CLI a student installs when the
   lesson does not pin one. ``--destination-port-range`` is accepted as an
   unambiguous abbreviation of ``--destination-port-ranges`` because knack
   0.14.0 leaves argparse ``allow_abbrev`` at its default.
3. Combine the resulting rule with the security rules created by
   ``Azure/iotedge-vm-deploy`` tag ``1.2.0`` ``edgeDeploy.json`` (the template
   URI in the lesson) and with the default inbound rules Azure adds to every
   network security group.
4. Decide whether an address that is not the student's, and is outside the
   template virtual network, can open a new TCP connection to the published
   host port.
5. If it can, POST an image with no prediction key to the Custom Vision Linux
   export's ``/image`` route (the container the lesson builds and publishes).

The test fails while that POST returns ripe and unripe scores.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import ipaddress
import json
import re
import shlex
import socket
import unittest
from pathlib import Path

from flask import Flask, jsonify, request
from knack.arguments import CaseInsensitiveList
from PIL import Image
from werkzeug.serving import get_sockaddr, select_address_family

REPO = Path(__file__).resolve().parents[1]
LESSON = REPO / "4-manufacturing/lessons/3-run-fruit-detector-edge"
VM_GUIDE = LESSON / "vm-iotedge.md"
MANIFESTS = (
    LESSON / "code-deployment/deployment/deployment.json",
    LESSON / "README.md",
    LESSON / "translations/README.bn.md",
)

# Azure/iotedge-vm-deploy 1.2.0 edgeDeploy.json. The lesson passes this URI
# and does not override allowSsh (default true) or the address space.
EDGE_DEPLOY_URI = (
    "https://raw.githubusercontent.com/Azure/iotedge-vm-deploy/1.2.0/edgeDeploy.json"
)
TEMPLATE_VNET = ipaddress.ip_network("10.0.0.0/16")
TEMPLATE_SSH_RULE = {
    "name": "default-allow-22",
    "priority": 1000,
    "access": "Allow",
    "direction": "Inbound",
    "protocol": "Tcp",
    "sourceAddressPrefix": "*",
    "sourcePortRange": "*",
    "destinationAddressPrefix": "*",
    "destinationPortRange": "22",
}

# Default inbound rules Azure adds to every NSG. Clients store "all addresses"
# as * ; the service stores the same match as 0.0.0.0/0.
DEFAULT_INBOUND_RULES = (
    {
        "name": "AllowVNetInBound",
        "priority": 65000,
        "access": "Allow",
        "direction": "Inbound",
        "protocol": "*",
        "sourceAddressPrefix": "VirtualNetwork",
        "sourcePortRange": "0-65535",
        "destinationAddressPrefix": "VirtualNetwork",
        "destinationPortRange": "0-65535",
    },
    {
        "name": "AllowAzureLoadBalancerInBound",
        "priority": 65001,
        "access": "Allow",
        "direction": "Inbound",
        "protocol": "*",
        "sourceAddressPrefix": "AzureLoadBalancer",
        "sourcePortRange": "0-65535",
        "destinationAddressPrefix": "0.0.0.0/0",
        "destinationPortRange": "0-65535",
    },
    {
        "name": "DenyAllInBound",
        "priority": 65500,
        "access": "Deny",
        "direction": "Inbound",
        "protocol": "*",
        "sourceAddressPrefix": "0.0.0.0/0",
        "sourcePortRange": "0-65535",
        "destinationAddressPrefix": "0.0.0.0/0",
        "destinationPortRange": "0-65535",
    },
)

# Not a virtual-network address and not named anywhere in the lesson.
ATTACKER = ipaddress.ip_address("198.51.100.23")
ATTACKER_PORT = 54321

# 1x1 PNG. The export route opens the body with PIL before scoring.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xf0"
    b"\x50\x0f\x00\x04\x85\x01\x80\x84\xa9\x8c!\x00\x00\x00\x00IEND\xaeB`\x82"
)

# azure-cli 2.93.0 NSGRuleCreate schema defaults. Singular --*-range flags
# are unregistered; the plural flags carry the defaults.
_PROTOCOL = {"*": "*", "Ah": "Ah", "Esp": "Esp", "Icmp": "Icmp", "Tcp": "Tcp", "Udp": "Udp"}
_ACCESS = {"Allow": "Allow", "Deny": "Deny"}
_DIRECTION = {"Inbound": "Inbound", "Outbound": "Outbound"}
_WILDCARDS = {"*", "any", "internet", "0.0.0.0/0"}


def _canonical(enum, value):
    """AAZArgEnum.__getitem__ when enum_case_sensitive is false."""
    for key, item in enum.items():
        if item == value or key == value or key.lower() == value.lower():
            return item
    raise AssertionError("unrecognized value %r for %s" % (value, sorted(enum)))


def _enum_type(enum):
    def convert(value):
        return _canonical(enum, value)

    return convert


def _nsg_parser():
    parser = argparse.ArgumentParser(allow_abbrev=True, exit_on_error=False)
    parser.add_argument("--name", "-n", required=True)
    parser.add_argument("--nsg-name", required=True)
    parser.add_argument("--resource-group", "-g", required=True)
    parser.add_argument("--priority", required=True, type=int)
    parser.add_argument(
        "--access",
        default="Allow",
        type=_enum_type(_ACCESS),
        choices=CaseInsensitiveList(list(_ACCESS)),
    )
    parser.add_argument(
        "--protocol",
        default="*",
        type=_enum_type(_PROTOCOL),
        choices=CaseInsensitiveList(list(_PROTOCOL)),
    )
    parser.add_argument(
        "--direction",
        default="Inbound",
        type=_enum_type(_DIRECTION),
        choices=CaseInsensitiveList(list(_DIRECTION)),
    )
    parser.add_argument("--destination-port-ranges", nargs="+", default=["80"])
    parser.add_argument("--destination-address-prefixes", nargs="+", default=["*"])
    parser.add_argument("--source-address-prefixes", nargs="+", default=["*"])
    parser.add_argument("--source-port-ranges", nargs="+", default=["*"])
    return parser


def _collapse(values):
    """NSGRuleCreate.pre_operations -> _handle_plural_or_singular.

    A single value is stored in the singular property. Azure CLI 2.93 records
    that shape: one destination port becomes destinationPortRange, and the
    plural list is empty.
    """
    if values is None:
        return None, None
    if len(values) > 1:
        return None, list(values)
    if len(values) == 1:
        return values[0], None
    return None, None


def rule_from_cli(argv):
    args = _nsg_parser().parse_args(argv)
    source_address, source_addresses = _collapse(args.source_address_prefixes)
    dest_address, dest_addresses = _collapse(args.destination_address_prefixes)
    source_port, source_ports = _collapse(args.source_port_ranges)
    dest_port, dest_ports = _collapse(args.destination_port_ranges)
    rule = {
        "name": args.name,
        "priority": args.priority,
        "access": args.access,
        "direction": args.direction,
        "protocol": args.protocol,
    }
    if source_address is not None:
        rule["sourceAddressPrefix"] = source_address
    if source_addresses is not None:
        rule["sourceAddressPrefixes"] = source_addresses
    if dest_address is not None:
        rule["destinationAddressPrefix"] = dest_address
    if dest_addresses is not None:
        rule["destinationAddressPrefixes"] = dest_addresses
    if source_port is not None:
        rule["sourcePortRange"] = source_port
    if source_ports is not None:
        rule["sourcePortRanges"] = source_ports
    if dest_port is not None:
        rule["destinationPortRange"] = dest_port
    if dest_ports is not None:
        rule["destinationPortRanges"] = dest_ports
    return rule


def nsg_commands(markdown):
    """Shell commands in the VM guide that create an NSG rule."""
    commands = []
    for block in re.findall(r"```sh\n(.*?)```", markdown, flags=re.S):
        text = block.replace("\\\n", " ")
        text = text.replace("<nsg name>", "nsg-from-lesson")
        if "az network nsg rule create" not in text:
            continue
        argv = shlex.split(text)
        index = argv.index("create")
        commands.append(argv[index + 1 :])
    return commands


def lesson_rules(markdown):
    rules = [rule_from_cli(argv) for argv in nsg_commands(markdown)]
    if "allowSsh=false" not in markdown and EDGE_DEPLOY_URI in markdown:
        rules.append(dict(TEMPLATE_SSH_RULE))
    rules.extend(dict(rule) for rule in DEFAULT_INBOUND_RULES)
    return rules


def _values(rule, singular, plural):
    many = rule.get(plural)
    if many:
        return list(many)
    one = rule.get(singular)
    if one is None:
        return []
    return [one]


def _port_matches(spec, port):
    if spec in ("*", "0-65535"):
        return True
    if "-" in spec:
        start, end = spec.split("-", 1)
        return int(start) <= port <= int(end)
    return int(spec) == port


def _prefix_matches(prefix, address):
    token = prefix.strip()
    lowered = token.lower()
    if lowered in _WILDCARDS:
        return True
    if lowered == "virtualnetwork":
        return address in TEMPLATE_VNET
    if lowered == "azureloadbalancer":
        return False
    try:
        network = ipaddress.ip_network(token, strict=False)
    except ValueError:
        return False
    return address in network


def _protocol_matches(rule_protocol, protocol):
    if rule_protocol in ("*", "Any"):
        return True
    return rule_protocol.lower() == protocol.lower()


def nsg_allows(rules, source, destination, source_port, dest_port, protocol):
    """First matching inbound rule wins. Lower priority numbers are first."""
    ordered = sorted(rules, key=lambda rule: rule["priority"])
    for rule in ordered:
        if rule["direction"] != "Inbound":
            continue
        if not _protocol_matches(rule["protocol"], protocol):
            continue
        if not any(
            _prefix_matches(item, source)
            for item in _values(rule, "sourceAddressPrefix", "sourceAddressPrefixes")
        ):
            continue
        if not any(
            _prefix_matches(item, destination)
            for item in _values(rule, "destinationAddressPrefix", "destinationAddressPrefixes")
        ):
            continue
        source_ports = _values(rule, "sourcePortRange", "sourcePortRanges")
        dest_ports = _values(rule, "destinationPortRange", "destinationPortRanges")
        if not any(_port_matches(item, source_port) for item in source_ports):
            continue
        if not any(_port_matches(item, dest_port) for item in dest_ports):
            continue
        return rule["access"] == "Allow"
    return False


def _image_classifier_options(document):
    modules = (
        document["content"]["modulesContent"]["$edgeAgent"]["properties.desired"]["modules"]
    )
    return json.loads(modules["ImageClassifier"]["settings"]["createOptions"])


def manifests_publishing_classifier():
    """Host bindings for container port 80 in every manifest the lesson deploys."""
    bindings = []
    deployment = json.loads(MANIFESTS[0].read_text())
    bindings.append((str(MANIFESTS[0].relative_to(REPO)), _image_classifier_options(deployment)))
    for path in MANIFESTS[1:]:
        text = path.read_text()
        for block in re.findall(r"```json\n(.*?)```", text, flags=re.S):
            if "ImageClassifier" not in block:
                continue
            bindings.append((str(path.relative_to(REPO)), _image_classifier_options(json.loads(block))))
    return bindings


def published_host_endpoints(create_options):
    """Host addresses and ports that receive container port 80.

    Moby v28.5.2 uses IPv4 0.0.0.0 when PortBinding.HostIP is empty
    (addPortMappings sets defHostIP to IPv4zero; configurePortBindingIPv4
    copies that default when HostIP is empty).
    """
    endpoints = []
    for binding in create_options.get("HostConfig", {}).get("PortBindings", {}).get("80/tcp", []):
        host_ip = binding.get("HostIp") or binding.get("HostIP") or ""
        host_port = int(binding["HostPort"])
        if host_ip in ("", "0.0.0.0", "::"):
            endpoints.append(("0.0.0.0", host_port))
        else:
            endpoints.append((host_ip, host_port))
    return endpoints


def predict_image(image):
    """Score an image. The export calls this with no credential check.

    The real predict.py runs the TensorFlow graph loaded from model.pb.
    This stand-in spends CPU on the bytes PIL decoded and returns the same
    ripe/unripe result shape the lesson prints.
    """
    raw = image.tobytes()
    digest = hashlib.sha256(raw).digest()
    for _ in range(20000):
        digest = hashlib.sha256(digest).digest()
    ripe = digest[0] / 255.0
    return {
        "created": "2021-07-05T21:44:39.573181",
        "id": "",
        "iteration": "",
        "predictions": [
            {
                "boundingBox": None,
                "probability": ripe,
                "tagId": "",
                "tagName": "ripe",
            },
            {
                "boundingBox": None,
                "probability": 1.0 - ripe,
                "tagId": "",
                "tagName": "unripe",
            },
        ],
        "project": "",
    }


def classifier_app():
    """Custom Vision Docker-Linux export app.py, the routes the lesson calls.

    The export listens with ``app.run(host='0.0.0.0', port=80)``. Flask 1.1.2
    passes that host to Werkzeug. No route reads a prediction key.
    """
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024

    @app.route("/")
    def index():
        return "CustomVision.ai model host harness"

    @app.route("/image", methods=["POST"])
    @app.route("/<project>/image", methods=["POST"])
    @app.route("/<project>/image/nostore", methods=["POST"])
    @app.route("/<project>/classify/iterations/<publishedName>/image", methods=["POST"])
    @app.route("/<project>/classify/iterations/<publishedName>/image/nostore", methods=["POST"])
    def predict_image_handler(project=None, publishedName=None):
        try:
            if "imageData" in request.files:
                image_data = request.files["imageData"]
            elif "imageData" in request.form:
                image_data = request.form["imageData"]
            else:
                image_data = io.BytesIO(request.get_data())
            image = Image.open(image_data)
            return jsonify(predict_image(image))
        except Exception as exc:  # noqa: BLE001 - export returns 500 on any failure
            return "Error processing image: %s" % exc, 500

    return app


class EdgeClassifierInboundExposureTest(unittest.TestCase):
    def test_cli_single_value_collapse_matches_azure_cli_2_93_recording(self):
        """The interpreter matches NetworkExtendedNSGScenarioTest in azure-cli 2.93.0.

        That recording creates a rule without a destination port and expects
        destinationPortRange 80 and sourceAddressPrefix *.
        """
        rule = rule_from_cli(
            [
                "--access",
                "allow",
                "--destination-address-prefixes",
                "10.0.0.0/24",
                "11.0.0.0/24",
                "--direction",
                "inbound",
                "--nsg-name",
                "nsg1",
                "-g",
                "rg",
                "--source-address-prefixes",
                "*",
                "-n",
                "rule1",
                "--source-port-ranges",
                "700-900",
                "1000-1100",
                "--priority",
                "1000",
            ]
        )
        self.assertEqual(rule["destinationPortRange"], "80")
        self.assertNotIn("destinationPortRanges", rule)
        self.assertEqual(rule["sourceAddressPrefix"], "*")
        self.assertNotIn("sourceAddressPrefixes", rule)
        self.assertEqual(rule["destinationAddressPrefixes"], ["10.0.0.0/24", "11.0.0.0/24"])
        self.assertEqual(rule["sourcePortRanges"], ["700-900", "1000-1100"])
        self.assertEqual(rule["access"], "Allow")
        self.assertEqual(rule["direction"], "Inbound")

    def test_internet_client_cannot_score_images_on_the_edge_classifier(self):
        guide = VM_GUIDE.read_text()
        if EDGE_DEPLOY_URI not in guide and "az deployment group create" not in guide:
            return
        if EDGE_DEPLOY_URI not in guide:
            # A replacement template was not part of the pinned 1.2.0 deployment
            # this test read, so it is not treated as a public address.
            return
        rules = lesson_rules(guide)

        family = select_address_family("0.0.0.0", 80)
        bound = get_sockaddr("0.0.0.0", 80, family)
        self.assertEqual(bound[0], "0.0.0.0")

        client = classifier_app().test_client()
        direct = client.post("/image", data=PNG, content_type="image/png")
        self.assertEqual(direct.status_code, 200, direct.get_data(as_text=True))
        direct_body = direct.get_json()
        tags = {item["tagName"] for item in direct_body["predictions"]}
        self.assertEqual(tags, {"ripe", "unripe"})

        exposed_ports = []
        for _path, options in manifests_publishing_classifier():
            for host_ip, host_port in published_host_endpoints(options):
                if host_ip == "0.0.0.0":
                    exposed_ports.append(host_port)
        self.assertIn(80, exposed_ports)

        destination = ipaddress.ip_address("10.0.0.4")
        reachable = [
            port
            for port in exposed_ports
            if nsg_allows(rules, ATTACKER, destination, ATTACKER_PORT, port, "tcp")
        ]
        if not reachable:
            return

        stolen = client.post(
            "/image",
            data=PNG,
            content_type="image/png",
            environ_base={"REMOTE_ADDR": str(ATTACKER)},
        )
        body = stolen.get_json(silent=True) or {}
        returned_tags = {item.get("tagName") for item in body.get("predictions", [])}
        self.assertFalse(
            stolen.status_code == 200 and returned_tags == {"ripe", "unripe"},
            "An address outside the template virtual network received ripe and "
            "unripe scores from POST /image with no prediction key. The port 80 "
            "NSG rule allows that address, and the classifier manifest publishes "
            "container port 80 on every host interface.",
        )


if __name__ == "__main__":
    unittest.main()
