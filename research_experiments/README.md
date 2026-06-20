```mermaid
graph LR
    %% Style Definitions
    classDef esp fill:#1a73e8,stroke:#0d47a1,stroke-width:2px,color:#fff;
    classDef sensor fill:#34a853,stroke:#1b5e20,stroke-width:2px,color:#fff;
    classDef filter fill:#fbbc05,stroke:#f57f17,stroke-width:2px,color:#000;

    %% Nodes
    ESP[ESP8266 NodeMCU / D1 Mini]:::esp
    ZMCT[ZMCT103C Sensor Module]:::sensor
    R1[1kΩ Resistor]:::filter
    C1[0.1µF Capacitor]:::filter
    GND[GND Rail]

    %% Connections
    ZMCT -->|VCC| ESP
    ZMCT -->|GND| GND
    ESP -->|GND| GND
    
    ZMCT -->|OUT| R1
    R1 -->|Filtered Signal| ESP
    R1 -->|Node A0| C1
    C1 -->|Dumps Noise| GND

    %% Layout styling
    subgraph Hardware RC Filter
    R1
    C1
    end
