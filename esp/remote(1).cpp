#include <WiFi.h>
#include <PubSubClient.h>

// --- WiFi Credentials ---
const char* ssid = "XIII";
const char* wifi_password = "Danny1258";

// --- MQTT Broker (Raspberry Pi) ---
const char* mqtt_server = "192.168.1.xxx";   // Replace with your Pi's IP
const int mqtt_port = 1883;
const char* mqtt_user = "fireuser";
const char* mqtt_password = "your_chosen_password";

// --- Topics ---
const char* fire_topic = "fire_detection/status";
const char* sensor_topic = "fire_detection/sensors";

// --- Pin definitions (change as needed) ---
const int BUZZER_PIN = 12;    // GPIO12 (or any PWM pin)
const int LED_PIN = 13;       // Built-in LED on many ESP32 boards

WiFiClient espClient;
PubSubClient client(espClient);

// MQTT callback – processes incoming messages
void callback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  if (String(topic) == fire_topic) {
    if (message == "FIRE_DETECTED") {
      Serial.println("🔥 FIRE ALERT! Activating buzzer & LED.");
      digitalWrite(LED_PIN, HIGH);
      tone(BUZZER_PIN, 2000);   // 2 kHz tone
    } else if (message == "SAFE") {
      Serial.println("✅ System safe. Deactivating alarms.");
      digitalWrite(LED_PIN, LOW);
      noTone(BUZZER_PIN);
    }
  }
  else if (String(topic) == sensor_topic) {
    Serial.print("📊 Sensor data: ");
    Serial.println(message);
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("ESP32_FireMonitor", mqtt_user, mqtt_password)) {
      Serial.println("connected");
      // Subscribe to topics
      client.subscribe(fire_topic);
      client.subscribe(sensor_topic);
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retry in 5 seconds");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Connect to Wi-Fi
  WiFi.begin(ssid, wifi_password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected, IP: " + WiFi.localIP().toString());

  // Configure MQTT
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();
}