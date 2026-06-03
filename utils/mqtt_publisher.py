import paho.mqtt.client as mqtt
import json
import logging
from config import CONFIG

class MQTTPublisher:
    def __init__(self):
        self.broker = CONFIG["MQTT_BROKER"]
        self.port = CONFIG["MQTT_PORT"]
        self.user = CONFIG["MQTT_USER"]
        self.password = CONFIG["MQTT_PASSWORD"]
        self.fire_topic = CONFIG["MQTT_FIRE_TOPIC"]
        self.sensor_topic = CONFIG["MQTT_SENSOR_TOPIC"]
        self.client = None
        self.connected = False

    def connect(self):
        try:
            self.client = mqtt.Client()
            self.client.username_pw_set(self.user, self.password)
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            self.connected = True
            logging.info("MQTT connected to broker")
        except Exception as e:
            logging.error(f"MQTT connection failed: {e}")
            self.connected = False

    def publish_fire_status(self, fire_detected):
        """Publish 'FIRE_DETECTED' or 'SAFE' to the fire topic."""
        if not self.connected:
            return
        status = "FIRE_DETECTED" if fire_detected else "SAFE"
        self.client.publish(self.fire_topic, status)
        logging.debug(f"MQTT published: {self.fire_topic} = {status}")

    def publish_sensor_data(self, temperature, gas_value):
        """Publish JSON with temperature and gas."""
        if not self.connected:
            return
        data = {
            "temperature": round(temperature, 1) if temperature is not None else None,
            "gas": gas_value,
            "timestamp": None   # We'll add time in main.py
        }
        self.client.publish(self.sensor_topic, json.dumps(data))
        logging.debug("MQTT sensor data published")

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logging.info("MQTT disconnected")