/*
 * Project: Active-Impedance Smart Grid Meter
 * Architecture: ESP32 for now
 * Features: TRMS Current Sensing, Active 120kHz TDR Signal Injection, JSON Payload
 */

#include <WiFi.h>

const int PIN_CURRENT_SENSOR = 36; 
const int PIN_INJECTOR = 25;       
const int PIN_RECEIVER = 34;       

const String METER_ID = "UID-ESP32-99A1";
const int CARRIER_FREQ = 120000;     
const float CURRENT_CALIBRATION = 5.51; // After 13th consecutive test this is the sweet spot
const float NOISE_CLAMP = 0.04;      // Because light bulb i was using for test had this disturbance


float currentAmps = 0.0;
float baselineImpedanceSignal = 0.0;
float currentAttenuationPct = 0.0;
bool isCalibrated = false;


unsigned long lastRmsUpdate = 0;
unsigned long lastImpedanceUpdate = 0;
unsigned long lastNetworkUpdate = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PIN_CURRENT_SENSOR, INPUT);
  pinMode(PIN_RECEIVER, INPUT);

  // Initialize 120kHz PWM only for test purpose it would be determined later after i get an RTI for permissible frequency
  ledcSetup(0, CARRIER_FREQ, 8);
  ledcAttachPin(PIN_INJECTOR, 0);
  ledcWrite(0, 127); // 50% Duty Cycle
  
  Serial.println("Calibrating Wrt Line Impedance Baseline...");
  delay(3000); 
  
  unsigned long total = 0;
  for(int i=0; i<100; i++) {
    total += analogRead(PIN_RECEIVER);
    delay(2);
  }
  baselineImpedanceSignal = (float)total / 100.0;
  isCalibrated = true;
  
  Serial.printf("Baseline Established: %.2f mV\n", baselineImpedanceSignal);
}

void loop() {
  unsigned long currentMillis = millis();

  
  if (currentMillis - lastRmsUpdate >= 100) {
    lastRmsUpdate = currentMillis;
    currentAmps = calculateTrueRMS(100); 
  }

  
  if (currentMillis - lastImpedanceUpdate >= 500 && isCalibrated) {
    lastImpedanceUpdate = currentMillis;
    
    float rawSignal = readAverageImpedance(20);
    currentAttenuationPct = ((baselineImpedanceSignal - rawSignal) / baselineImpedanceSignal) * 100.0;
    
    // Safety clamp for negative attenuation (noise)
    if (currentAttenuationPct < 0) currentAttenuationPct = 0.0; 
  }

  // TASK 3: Output/Transmit Data (Every 2000ms)
  if (currentMillis - lastNetworkUpdate >= 2000) {
    lastNetworkUpdate = currentMillis;
    transmitMachineLearningPayload();
  }
}

// 
float calculateTrueRMS(int samples) {
  unsigned long sumSq = 0;
  for (int i = 0; i < samples; i++) {
    int raw = analogRead(PIN_CURRENT_SENSOR) - 2048; // Center 12-bit ADC
    sumSq += (raw * raw);
  }
  float rmsAdc = sqrt((float)sumSq / samples);
  float amps = (rmsAdc / 4096.0 * 3.3) * CURRENT_CALIBRATION;
  return (amps > NOISE_CLAMP) ? amps : 0.0;
}

float readAverageImpedance(int samples) {
  unsigned long total = 0;
  for(int i = 0; i < samples; i++) {
    total += analogRead(PIN_RECEIVER);
    delay(1);
  }
  return (float)total / samples;
}


void transmitMachineLearningPayload() {
  
  String payload = "{";
  payload += "\"meter_id\":\"" + METER_ID + "\",";
  payload += "\"passive_features\":{\"current_amps\":" + String(currentAmps, 3) + "},";
  payload += "\"active_features\":{\"baseline_mv\":" + String(baselineImpedanceSignal, 1) + ",";
  payload += "\"attenuation_pct\":" + String(currentAttenuationPct, 2) + "}";
  payload += "}";

  Serial.println(payload);
  // TODO: Add HTTP/MQTT POST request and HMAC signing here
}
