#!/usr/bin/env python3
"""
MQTT Publisher for fire detection system.
- Publishes sensor data and fire status.
- Publishes alerts to the dashboard.
"""

import paho.mqtt.client as mqtt
import json
import logging
import time
from config import CONFIG

class MQTTPublisher:
    def __init__(self):
        self.broker = CONFIG.get("MQTT_BROKER", "localhost")
        self.port = CONFIG.get("MQTT_PORT", 1883)
        self.user = CONFIG.get("MQTT_USER")
        self.password = CONFIG.get("MQTT_PASSWORD")
        self.fire_topic = CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status")
        self.sensor_topic = CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors")
        self.alert_topic = "fire_detection/alerts"
        self.client = None
        self.connected = False

    def connect(self):
        if not self.user or not self.password:
            logging.warning("MQTT credentials missing. Skipping MQTT.")
            return
        try:
            # Use new API to avoid deprecation warnings
            self.client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id="fire_mqtt_pub"
            )
            self.client.username_pw_set(self.user, self.password)
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            self.connected = True
            logging.info(f"MQTT connected to {self.broker}:{self.port}")
        except Exception as e:
            logging.error(f"MQTT connection failed: {e}")
            self.connected = False

    def publish_fire_status(self, fire_detected):
        if not self.connected:
            return
        status = "FIRE_DETECTED" if fire_detected else "SAFE"
        self.client.publish(self.fire_topic, status)
        logging.debug(f"MQTT published: {self.fire_topic} = {status}")

    def publish_sensor_data(self, temperature, gas_value):
        if not self.connected:
            return
        data = {
            "temperature": round(temperature, 1) if temperature is not None else None,
            "gas": gas_value,
            "timestamp": time.time()
        }
        self.client.publish(self.sensor_topic, json.dumps(data))
        logging.debug("MQTT sensor data published")

    def publish_alert(self, message, level):
        """
        Publish an alert to the dashboard.
        level: 1 = warning, 2 = fire, 0 = info
        """
        if not self.connected:
            logging.warning("MQTT not connected, cannot publish alert")
            return
        alert_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message
        }
        self.client.publish(self.alert_topic, json.dumps(alert_data))
        logging.debug(f"Alert published: level={level}, message={message}")

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
            logging.info("MQTT disconnected")

# import paho.mqtt.client as mqtt
# import json
# import logging
# from config import CONFIG

# class MQTTPublisher:
#     def __init__(self):
#         self.broker = CONFIG.get("MQTT_BROKER", "localhost")
#         self.port = CONFIG.get("MQTT_PORT", 1883)
#         self.user = CONFIG.get("MQTT_USER")
#         self.password = CONFIG.get("MQTT_PASSWORD")
#         self.fire_topic = CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status")
#         self.sensor_topic = CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors")
#         self.client = None
#         self.connected = False

#     def connect(self):
#         if not self.user or not self.password:
#             logging.warning("MQTT credentials missing. Skipping MQTT.")
#             return
#         try:
#             self.client = mqtt.Client()
#             self.client.username_pw_set(self.user, self.password)
#             self.client.connect(self.broker, self.port, 60)
#             self.client.loop_start()
#             self.connected = True
#             logging.info(f"MQTT connected to {self.broker}:{self.port}")
#         except Exception as e:
#             logging.error(f"MQTT connection failed: {e}")
#             self.connected = False

#     def publish_fire_status(self, fire_detected):
#         if not self.connected:
#             return
#         status = "FIRE_DETECTED" if fire_detected else "SAFE"
#         self.client.publish(self.fire_topic, status)
#         logging.debug(f"MQTT published: {self.fire_topic} = {status}")

#     def publish_sensor_data(self, temperature, gas_value):
#         if not self.connected:
#             return
#         data = {
#             "temperature": round(temperature, 1) if temperature is not None else None,
#             "gas": gas_value,
#             "timestamp": time.time()
#         }
#         self.client.publish(self.sensor_topic, json.dumps(data))
#         logging.debug("MQTT sensor data published")

#     def disconnect(self):
#         if self.client:
#             self.client.loop_stop()
#             self.client.disconnect()
#             self.connected = False
#             logging.info("MQTT disconnected")

# ----- v1 updated ------------------------

# import paho.mqtt.client as mqtt
# import json
# import logging
# import time          # <-- ADD THIS LINE
# from config import CONFIG

# class MQTTPublisher:
#     def __init__(self):
#         self.broker = CONFIG.get("MQTT_BROKER", "localhost")
#         self.port = CONFIG.get("MQTT_PORT", 1883)
#         self.user = CONFIG.get("MQTT_USER")
#         self.password = CONFIG.get("MQTT_PASSWORD")
#         self.fire_topic = CONFIG.get("MQTT_FIRE_TOPIC", "fire_detection/status")
#         self.sensor_topic = CONFIG.get("MQTT_SENSOR_TOPIC", "fire_detection/sensors")
#         self.client = None
#         self.connected = False

#     def connect(self):
#         if not self.user or not self.password:
#             logging.warning("MQTT credentials missing. Skipping MQTT.")
#             return
#         try:
#             self.client = mqtt.Client()
#             self.client.username_pw_set(self.user, self.password)
#             self.client.connect(self.broker, self.port, 60)
#             self.client.loop_start()
#             self.connected = True
#             logging.info(f"MQTT connected to {self.broker}:{self.port}")
#         except Exception as e:
#             logging.error(f"MQTT connection failed: {e}")
#             self.connected = False

#     def publish_fire_status(self, fire_detected):
#         if not self.connected:
#             return
#         status = "FIRE_DETECTED" if fire_detected else "SAFE"
#         self.client.publish(self.fire_topic, status)
#         logging.debug(f"MQTT published: {self.fire_topic} = {status}")

#     def publish_sensor_data(self, temperature, gas_value):
#         if not self.connected:
#             return
#         data = {
#             "temperature": round(temperature, 1) if temperature is not None else None,
#             "gas": gas_value,
#             "timestamp": time.time()   # now works
#         }
#         self.client.publish(self.sensor_topic, json.dumps(data))
#         logging.debug("MQTT sensor data published")

#     def disconnect(self):
#         if self.client:
#             self.client.loop_stop()
#             self.client.disconnect()
#             self.connected = False
#             logging.info("MQTT disconnected")