#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "XIII";
const char* password = "Danny1258";

WebServer server(80);

void handleRoot() {
  String html = "<!DOCTYPE html><html><head><title>Fire System</title></head><body>";
  html += "<h1>Fire Detection System</h1>";
  html += "<p>System Status: ACTIVE</p>";
  html += "<p>Last Check: " + String(millis() / 1000) + " seconds</p>";
  html += "</body></html>";
  server.send(200, "text/html", html);
}

void setup() {
  Serial.begin(115200);
  WiFi.softAP(ssid, password);
  Serial.print("ESP32 Access Point IP: ");
  Serial.println(WiFi.softAPIP()); // 192.168.4.1
  server.on("/", handleRoot);
  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  server.handleClient();
}