import time
from counterfit_connection import CounterFitConnection
from counterfit_shims_grove.grove_light_sensor_v1_2 import GroveLightSensor
from counterfit_shims_grove.grove_led import GroveLed
import os
import paho.mqtt.client as mqtt
import json

CounterFitConnection.init('127.0.0.1', 5000)

light_sensor = GroveLightSensor(0)
led = GroveLed(5)

id = '<ID>'

client_telemetry_topic = id + '/telemetry'
client_name = id + 'nightlight_client'

mqtt_client = mqtt.Client(client_name)
mqtt_client.username_pw_set(os.environ['MQTT_USERNAME'], os.environ['MQTT_PASSWORD'])
mqtt_client.tls_set(ca_certs=os.environ.get('MQTT_CA_CERTS'))
mqtt_client.connect(os.environ['MQTT_BROKER'], 8883)

mqtt_client.loop_start()

print("MQTT connected!")

while True:
    light = light_sensor.light
    telemetry = json.dumps({'light' : light})

    print("Sending telemetry ", telemetry)

    mqtt_client.publish(client_telemetry_topic, telemetry)

    time.sleep(5)
