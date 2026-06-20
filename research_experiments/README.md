
```mermaid
graph LR
    %% Style Definitions for Component Types
    classDef active fill:#2b2b2b,stroke:#111,stroke-width:2px,color:#fff;
    classDef passive fill:#f5f5f5,stroke:#424242,stroke-width:1px,color:#000;
    classDef net fill:#ea4335,stroke:#b31412,stroke-width:1px,color:#fff;

    %% ESP8266 Component & Pins
    subgraph ESP8266 [ESP8266 Board]
        Pin_3V3([3V3])
        Pin_GND1([GND])
        Pin_A0([Pin A0])
    end
    class ESP8266 active;

    %% ZMCT103C Component & Pins
    subgraph ZMCT[ZMCT103C Module]
        Pin_VCC([VCC])
        Pin_GND2([GND])
        Pin_OUT([OUT])
    end
    class ZMCT active;

    %% Passive Components (Terminal Level)
    subgraph R1 [Resistor 1kΩ]
        R1_T1[t1]
        R1_T2[t2]
    end
    class R1 passive;

    subgraph C1 [Capacitor 0.1µF]
        C1_Pos[t1]
        C1_Neg[t2]
    end
    class C1 passive;

    %% Power Rail Routing
    Pin_3V3 ----> Pin_VCC
    Pin_GND1 --- Node_GND((GND NET)):::net
    Pin_GND2 --- Node_GND
    
    %% Actual Circuit Signal Path Routing
    Pin_OUT ===> R1_T1
    R1_T2 ===> Node_A0_Net((Analog Net)):::net
    Node_A0_Net ===> Pin_A0
    
    %% Filter Shunt to Ground
    Node_A0_Net --- C1_Pos
    C1_Neg --- Node_GND
