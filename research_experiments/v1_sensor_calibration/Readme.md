
```mermaid
graph TD
    %% High-Voltage Side
    subgraph AC_Mains [AC Power Line]
        Wire[AC Load Wire]
    end

    %% Sensor Module Block
    subgraph Sensor_Module [ZMCT103C Module]
        VCC_In[VCC]
        GND_In[GND]
        OUT_Pin[OUT]
    end

    %% Low Pass Filter Block
    subgraph Noise_Filter [Hardware RC Filter]
        R1[1kΩ Resistor]
        C1[0.1µF Capacitor]
    end

    %% Microcontroller Block
    subgraph MCU [ESP8266 Board]
        3V3_Pin[3V3 Rail]
        GND_Pin[GND Rail]
        A0_Pin[Analog A0]
    end

    %% Physical Interaction
    Wire -. passes through .-> Sensor_Module

    %% Power Connections
    3V3_Pin ==>|3.3V Power| VCC_In
    GND_In --- GND_Pin

    %% Signal Flow with Filter
    OUT_Pin --> R1
    R1 --> A0_Pin
    A0_Pin --- C1
    C1 --- GND_Pin

    %% Styling
    style AC_Mains fill:#ffdde1,stroke:#721c24,stroke-width:2px
    style Sensor_Module fill:#d4edda,stroke:#155724,stroke-width:2px
    style Noise_Filter fill:#fff3cd,stroke:#856404,stroke-width:2px
    style MCU fill:#cce5ff,stroke:#004085,stroke-width:2px
