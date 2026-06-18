# Blockchain-Based Energy Theft Detection System

### Secure Smart Grid Monitoring using PBFT, Graph Analytics, and Machine Learning

![Status](https://img.shields.io/badge/Status-In--Development-orange.svg)
![Hardware](https://img.shields.io/badge/Hardware-STM8%20%7C%20Arduino%20Nano-blue.svg)
![Framework](https://img.shields.io/badge/Framework-Scikit--Learn%20%7C%20TensorFlow-green.svg)

A decentralized, tamper-proof, and low-latency architecture designed to eradicate electricity distribution malpractices such as line tapping, meter tampering, and internal data corruption. The framework implements a hierarchical security layer across Edge Microcontrollers, Local Substations utilizing Practical Byzantine Fault Tolerance (PBFT) consensus, and a centralized Machine Learning processing station.

---

## 📖 Table of Contents

* [System Architecture](#-system-architecture)
* [Cryptographic & Analytical Data Flow](#-cryptographic--analytical-data-flow)
* [Repository Directory Structure](#-repository-directory-structure)
* [Mathematical Foundations](#-mathematical-foundations)
* [Project Roadmap](#-project-roadmap--current-execution-status)

---

## 🏗️ System Architecture

The framework segregates operations into three distinct structural horizons to preserve computation bandwidth on edge nodes while maintaining aggressive real-time anomaly detection.

```mermaid
graph TD

    classDef edgeNode fill:#f9f,stroke:#333,stroke-width:2px;
    classDef ledgerNode fill:#bbf,stroke:#333,stroke-width:2px;
    classDef coreNode fill:#bfb,stroke:#333,stroke-width:2px;

    subgraph L1 [Level 1: Household Edge Telemetry]
        M1[Smart Meter 01]:::edgeNode -->|AES-128 / Nonce| S1
        M2[Smart Meter 02]:::edgeNode -->|AES-128 / Nonce| S1
        M3[Smart Meter 03]:::edgeNode -->|AES-128 / Nonce| S2
    end

    subgraph L2 [Level 2: Distributed Substation Ledger]
        S1[Substation Node A]:::ledgerNode <-->|PBFT Consensus| S2[Substation Node B]:::ledgerNode
        S1 -->|Louvain Community Detection| S1
    end

    subgraph L3 [Level 3: Centralized Analytics Station]
        S1 -->|Aggregated Block Relays| CC[Central Control Engine]:::coreNode
        S2 -->|Aggregated Block Relays| CC

        CC --> IF[Isolation Forest Anomaly Evaluator]:::coreNode
        CC --> LSTM[LSTM Predictive Maintenance Model]:::coreNode
    end
```

---

## 🔄 Cryptographic & Analytical Data Flow

Every ingestion ping goes through a chronological security handshake to guarantee non-repudiation, prevent replay attacks, and perform immediate anomaly scoring.

```mermaid
sequenceDiagram
    autonumber

    participant Meter as Smart Meter Node
    participant Substation as Local Substation Network
    participant Central as Central Processing Station

    Meter->>Substation: AES Encrypted Telemetry + Signature
    Note over Substation: Verify Signature & Nonce

    Substation->>Substation: PBFT Pre-Prepare
    Substation->>Substation: PBFT Prepare
    Substation->>Substation: PBFT Commit

    Substation->>Substation: Append Validated Ledger Block

    Substation->>Central: Forward Immutable Block Stream

    Central->>Central: Isolation Forest Analysis
    Central->>Central: LSTM Prediction Engine

    alt Anomaly Score > Threshold
        Central-->>Substation: Theft / Tampering Alert
    end
```

---

## 📂 Repository Directory Structure

```text
.
├── hardware_telemetry
│   ├── meter_ingest.ino
│   ├── aes_encrypt.h
│   └── anti_tamper.c
│
├── substation_blockchain
│   ├── pbft_mock.py
│   ├── ledger_manager.py
│   └── louvain_cluster.py
│
├── central_ml_models
│   ├── isolation_forest.py
│   └── lstm_predictive.py
│
├── data_simulations
│   ├── grid_data_generator.py
│   └── run_mock_pipeline.py
│
├── requirements.txt
└── README.md
```

---

## 🧮 Mathematical Foundations

### 1. Modularity Optimization (Louvain Graph Analysis)

To identify abnormal power diversion communities within localized sub-grids, modularity is computed as:

$$
Q=\frac{1}{2m}
\sum_{ij}
\left(
A_{ij}-\frac{k_i k_j}{2m}
\right)
\delta(c_i,c_j)
$$

Where:

* (A_{ij}) represents the energy flow between nodes (i) and (j)
* (k_i) is the degree sum of node (i)
* (m) is the total graph weight
* (\delta(c_i,c_j)) indicates community membership

---

### 2. Isolation Forest Anomaly Scoring

The anomaly score for a sample (x) is given by:

$$
s(x,n)=2^{-\frac{E(h(x))}{c(n)}}
$$

Where:

* (E(h(x))) is the average isolation path length
* (c(n)) is the normalization factor
* (s \to 1) indicates highly anomalous behavior

---

## 🗺️ Project Roadmap & Current Execution Status

### ✅ Phase 1: Deep Analytical Design & Mathematical Formulation

* Compiled hierarchical blockchain architecture.
* Designed graph-theoretic anomaly detection framework.
* Published complete system mechanics documentation.

### ✅ Phase 2: Digital Twin and AI Simulation Engine

* Developed synthetic grid telemetry generator.
* Implemented Isolation Forest experimentation pipeline.
* Validated anomaly detection on simulated theft scenarios.

### 🔄 Phase 3: Hardware Ingestion and Advanced Data Collection (In Progress)

* Developing memory-optimized firmware for low-cost microcontrollers.
* Integrating encrypted telemetry transmission.
* Refining real-time sensor aggregation modules.

### ⏳ Phase 4: Multi-Node Ledger Network Deployment

* Implement PBFT-enabled distributed substation nodes.
* Deploy ledger synchronization mechanisms.
* Perform network resilience and fault-tolerance testing.

---

## 🎯 Key Features

* Blockchain-secured energy telemetry
* PBFT-based distributed consensus
* Graph Theory powered anomaly localization
* Isolation Forest theft detection
* LSTM predictive maintenance forecasting
* Edge-to-cloud secure architecture
* Tamper-resistant audit trail
* Scalable smart-grid deployment model

---

## 🚀 Future Work

* Real-time dashboard visualization
* Federated learning integration
* Smart contract-based automated enforcement
* Edge AI deployment on embedded devices
* Large-scale smart city pilot deployment

---

## 📜 License

This project is intended for academic research, experimentation, and smart-grid security studies.
