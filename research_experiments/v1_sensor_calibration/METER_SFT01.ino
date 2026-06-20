

#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <math.h>
#include <SPI.h>

const int   SENSOR_PIN = A0;
const float VREF       = 5.0;
const int   ADC_RES    = 1024;
LiquidCrystal_I2C lcd(0x27, 16, 2);

const unsigned long OFFSET_SAMPLES = 300;
const unsigned long RMS_WINDOW_MS  = 1000;

float CALIBRATION_FACTOR = 10.0;  // <-- adjust after calibration
const float NOISE_FLOOR_MV = 2.0;
const float NOISE_CURRENT_THRESHOLD = 0.03; 


// --- smoothing helper ---
float median3(float a, float b, float c){
  if ((a <= b && b <= c) || (c <= b && b <= a)) return b;
  if ((b <= a && a <= c) || (c <= a && a <= b)) return a;
  return c;
}

inline int readADCSettled(uint8_t pin){
  analogRead(pin);
  delayMicroseconds(80);
  return analogRead(pin);
}

void setup() {
  Serial.begin(115200);
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print("CRYPTETHERA");
  delay(1000);
  lcd.clear();
  
}

float readMeterCurrent() {
  unsigned long sumOff = 0;
  for (unsigned long i = 0; i < OFFSET_SAMPLES; i++){
    sumOff += readADCSettled(SENSOR_PIN);
    delayMicroseconds(150);
  }
  const float offsetADC = (float)sumOff / (float)OFFSET_SAMPLES;
  const float offsetV   = offsetADC * (VREF / ADC_RES);

  unsigned long start = millis();
  double sumSq = 0.0;
  unsigned long samples = 0;
  while (millis() - start < RMS_WINDOW_MS){
    int raw = readADCSettled(SENSOR_PIN);
    float centeredCounts = raw - offsetADC;
    float centeredVolts  = centeredCounts * (VREF / ADC_RES);
    sumSq += (double)centeredVolts * (double)centeredVolts;
    samples++;
    delayMicroseconds(300);
  }

  float Vrms = (samples > 0) ? sqrt(sumSq / (double)samples) : 0.0;
  float Vrms_mV = Vrms * 1000.0;

  if (Vrms_mV < NOISE_FLOOR_MV) Vrms = 0.0;

  float Irms = Vrms * CALIBRATION_FACTOR;

  if (Irms < NOISE_CURRENT_THRESHOLD) {
  Irms = 0.0;
}


  static float last1 = 0.0, last2 = 0.0;
  float dispA = median3(last2, last1, Irms);
  last2 = last1; last1 = Irms;

  lcd.clear();
  lcd.setCursor(0,0);
  lcd.print("I: ");
  char buf[16];
  dtostrf(dispA, 1, 4, buf);
  lcd.print(buf);
  lcd.print(" A");

  lcd.setCursor(0,1);
  lcd.print("Off:");
  lcd.print(offsetV, 3);
  lcd.print("V");

  return Irms;
}

void loop() {
  float meter_irms = readMeterCurrent();
  Serial.println(meter_irms, 3);  
  delay(800); 
}
