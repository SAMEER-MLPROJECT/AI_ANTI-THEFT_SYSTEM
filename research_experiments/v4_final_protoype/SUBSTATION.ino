/*
 * CRYPTETHERA - Substation Gateway Node MVP
 * Hardware: ESP32
 * Features: Wi-Fi AP, TCP Server, HMAC-SHA256 Verification, TO AVOID Replay Attack 
 */

#include <WiFi.h>
#include <bearssl/bearssl.h>


const char* AP_SSID = "CRYPTETHERA_GRID";
const char* AP_PASS = "samsung2025";
WiFiServer server(8080); 


const char* SECRET_KEY = "Sup3rS3cr3tHmacK3y!9982"; 


const int PIN_SUB_CURRENT = 34; 


const float CURRENT_CALIBRATION = 5.54;  // 13TH EXPERIMENT ON 01/10/2025
const float NOISE_CLAMP = 0.04;


uint32_t lastKnownBootId = 0;
uint32_t highestSequenceNum = 0;


float latestMeterIrms = 0.0;
float latestAttenuation = 0.0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SUB_CURRENT, INPUT);

  
  Serial.println("\nStarting Substation Gateway AP...");
  WiFi.softAP(AP_SSID, AP_PASS);
  IPAddress myIP = WiFi.softAPIP();
  Serial.print("Gateway IP address: ");
  Serial.println(myIP); 

  server.begin();
  Serial.println("TCP Server started on port 8080");
}

void loop() {
  WiFiClient client = server.available();

  if (client) {
    // If a meter node connects, read its packets
    while (client.connected() && client.available()) {
      String incomingPacket = client.readStringUntil('\n');
      incomingPacket.trim();
      
      if (incomingPacket.length() > 0) {
        processIncomingPacket(incomingPacket);
      }
    }
  }

  
  static unsigned long lastStreamTime = 0;
  if (millis() - lastStreamTime >= 1000) {
    lastStreamTime = millis();
    
    
    float sub_irms = calculateTrueRMS(PIN_SUB_CURRENT, 100);
    
    
    float residual = sub_irms - latestMeterIrms;
    if (abs(residual) < NOISE_CLAMP) residual = 0.0;

  
    if (latestAttenuation > 15.0) {
       residual += 5.0; // Massive artificial discrepancy
    }

    
    Serial.print("SUBSTATION,");
    Serial.print(millis());
    Serial.print(",");
    Serial.print(sub_irms, 3);
    Serial.print(",");
    Serial.print(residual, 3);
    Serial.print(",");
    Serial.println(latestMeterIrms, 3);
  }
}


void processIncomingPacket(String packet) {
  // Packet format is "{"id":"M001","irms":1.25,"att":2.4,"boot_id":123,"seq":1}|abc123hash..."
  int separatorIndex = packet.lastIndexOf('|');
  if (separatorIndex == -1) return; // Malformed packet

  String payload = packet.substring(0, separatorIndex);
  String incomingHash = packet.substring(separatorIndex + 1);

  
  if (!verifySignature(payload, incomingHash)) {
    Serial.println("SECURITY ALERT: Invalid Signature! Packet Tampered.");
    return; // Drop packet
  }

  // BAAD MEIN EDIT NO.15 BEFORE PRESENTATION
  float meterIrms = extractJsonFloat(payload, "\"irms\":");
  float attenuation = extractJsonFloat(payload, "\"att\":");
  uint32_t bootId = (uint32_t)extractJsonFloat(payload, "\"boot_id\":");
  uint32_t seqNum = (uint32_t)extractJsonFloat(payload, "\"seq\":");

  // 3. VERIFY FRESHNESS (Replay Attack Prevention)
  if (bootId != lastKnownBootId) {
    // New Session Started (Meter rebooted)
    lastKnownBootId = bootId;
    highestSequenceNum = seqNum;
  } else {
    // Existing Session
    if (seqNum <= highestSequenceNum) {
      Serial.println("SECURITY ALERT: Replay Attack Detected! Sequence Number too low.");
      return; // Drop packet
    }
    highestSequenceNum = seqNum; // Update highest seen
  }

  
  latestMeterIrms = meterIrms;
  latestAttenuation = attenuation;
}


bool verifySignature(String payload, String incomingHash) {
  br_hmac_key_context kc;
  br_hmac_context ctx;
  br_hmac_key_init(&kc, &br_sha256_vtable, SECRET_KEY, strlen(SECRET_KEY));
  br_hmac_init(&ctx, &kc, 0);
  br_hmac_update(&ctx, payload.c_str(), payload.length());
  
  uint8_t mac[32];
  br_hmac_out(&ctx, mac);
  
  String calculatedHash = "";
  for (int i = 0; i < 32; i++) {
    char hexString[3];
    sprintf(hexString, "%02x", mac[i]);
    calculatedHash += hexString;
  }

  return (calculatedHash.equalsIgnoreCase(incomingHash));
}


float extractJsonFloat(String json, String key) {
  int startIndex = json.indexOf(key) + key.length();
  if (startIndex < key.length()) return 0.0;
  int endIndex = json.indexOf(',', startIndex);
  if (endIndex == -1) endIndex = json.indexOf('}', startIndex);
  return json.substring(startIndex, endIndex).toFloat();
}

float calculateTrueRMS(int pin, int samples) {
  unsigned long sumSq = 0;
  for (int i = 0; i < samples; i++) {
    int raw = analogRead(pin) - 2048; 
    sumSq += (raw * raw);
  }
  float rmsAdc = sqrt((float)sumSq / samples);
  float amps = (rmsAdc / 4096.0 * 3.3) * CURRENT_CALIBRATION;
  return (amps > NOISE_CLAMP) ? amps : 0.0;
}
