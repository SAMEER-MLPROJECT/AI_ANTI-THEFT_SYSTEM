## Signal injection is an aspiring feature that is currently at development phase
# METHODOLGY UNDER TESTING : CAPACITIVE COUPLING

# Active-Impedance Smart Grid Meter


This repository provides the edge-node (Household energy Meter) architecture that feeds multi-dimensional data into a decentralized Substation ledger, directly supporting an Isolation Forest and LSTM anomaly detection pipeline.

## ⚡ The Innovation: Beyond Passive Sensors, inspired by immune system of body



**This attempt purposes Active Time Domain Reflectometry (TDR) to the Smart Meter.**
1. **Signal Injection:** The Microntroller ( ESP32 IN MY CASE ) continuously injects a low-voltage, high-frequency (120kHz) signature signal onto the high-voltage AC live wire via a capacitive coupling circuit.
2. **Impedance Monitoring:** A reflected envelope detector reads the returning signal. 
3. **Physical Tamper Detection:** When an unauthorized connection is added to the power line via hooking, it changes the wire's geometry and impedance. This causes an immediate, measurable attenuation (drop) in the injected (120kHz signal), instantly alerting the ML pipeline of a physical tap.

## 🛠️ Hardware Architecture

### Required Components
* **ESP32 Development Board** (Handles DSP, PWM generation, and encrypted transmission)
* **ZMCT103C AC Current Transformer** (For passive load measurement only for demo later it will be modified to high end alternatives)
* **X2/Y2 Safety-Rated Capacitors** (Isolates high-voltage 230V AC microcontroller)
* **Op-Amp & Diode Envelope Detector** (For filtering)

### Schematic


```mermaid
graph LR
    ESP[ESP32] -->|Pin 25 PWM| Injector[Coupling Circuit]
    Injector -->|120kHz| Grid[AC Mains Wire]
    Grid -->|Reflected Signal| Detector[Envelope Detector]
    Detector -->|Pin 34 ADC| ESP
    Grid -.->|Induction| ZMCT[ZMCT103C Module]
    ZMCT -->|Pin 36 A0| ESP
