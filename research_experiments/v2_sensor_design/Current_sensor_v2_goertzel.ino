/*
 * Advanced Goertzel Algorithm for ZMCT103C AC Current Sensing
 * Isolates a specific target frequency (e.g.50Hz in india ) and rejects all other noise.
 */

const int SENSOR_PIN = A0;


const float TARGET_FREQ = 50.0;         
const float SAMPLING_FREQ = 1000.0;     
const int N_SAMPLES = 100;              


const unsigned long SAMPLE_INTERVAL_US = 1000000UL / SAMPLING_FREQ; 


float coeff;
float Q1 = 0.0;
float Q2 = 0.0;
int sampleCount = 0;
unsigned long lastSampleTime = 0;

float calibrationFactor = 0.045; 
const float NOISE_CLAMP = 0.03;         // Ignore results below 30mA as per my experiments it had a capacitor problem 

void setup() {
  Serial.begin(115200);
  pinMode(SENSOR_PIN, INPUT);

  
  float k = round((N_SAMPLES * TARGET_FREQ) / SAMPLING_FREQ);
  float omega = (2.0 * PI * k) / N_SAMPLES;
  coeff = 2.0 * cos(omega);

  Serial.print("Goertzel Initialized. Coefficient: ");
  Serial.println(coeff, 4);
  
  
  for(int i = 0; i < 10; i++) analogRead(SENSOR_PIN);
}

void loop() {
  unsigned long currentMicros = micros();

  
  if (currentMicros - lastSampleTime >= SAMPLE_INTERVAL_US) {
    lastSampleTime += SAMPLE_INTERVAL_US; // Keep timing extremely rigid
    
    
    float currentSample = (float)analogRead(SENSOR_PIN) - 512.0;

    
    float Q0 = (coeff * Q1) - Q2 + currentSample;
    Q2 = Q1;
    Q1 = Q0;
    
    sampleCount++;

    
    if (sampleCount >= N_SAMPLES) {
      
      
      float magnitude = sqrt((Q1 * Q1) + (Q2 * Q2) - (Q1 * Q2 * coeff));

      
      float rawRMS = magnitude / N_SAMPLES;
      float calculatedAmps = rawRMS * calibrationFactor;

      if (calculatedAmps < NOISE_CLAMP) {
        calculatedAmps = 0.0;
      }

      
      Serial.print("Magnitude: ");
      Serial.print(magnitude, 1);
      Serial.print(" | Amps (Target Freq Only): ");
      Serial.println(calculatedAmps, 3);

      
      Q1 = 0.0;
      Q2 = 0.0;
      sampleCount = 0;
    }
  }
  
  // Your other non-blocking code can go here. 
  // Ensure nothing blocks the loop for longer than SAMPLE_INTERVAL_US (1ms)!
}
