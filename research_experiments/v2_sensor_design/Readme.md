# 🎯 Why I Chose the Goertzel Algorithm for Low-Current AC Measurement

## The Problem

One of the biggest challenges in this project was accurately measuring a very small AC current (~60mA) using a current sensor designed for currents up to 5A. 

At that scale, the actual signal becomes extremely small compared to the surrounding electrical noise. While the sensor could technically detect the current, obtaining stable and reliable readings was difficult because the measurement was heavily affected by mains interference, power supply ripple, ADC drift, and other environmental noise , Like in my case it detected the em radiation from the laptop charger

---

## Why Traditional Filtering Wasn't Enough

My initial approach was using conventional digital filtering techniques like moving averages and smoothing filters or using some low pass filter

These couldn't solve the real problem: the noise existed within the same frequency region as the signal I was trying to measure.

The current waveform that is needed exists at **50Hz**, and traditional filters had no reliable way to distinguish between the genuine 50Hz current and unwanted low-frequency interference.

As a result, the readings remained unstable at very low current levels.

---

## Why I Didn't Use FFT

The obvious solution was frequency-domain analysis using an FFT (Fast Fourier Transform).

An FFT can identify the energy present across the entire frequency spectrum, making it possible to isolate the 50Hz component. However, after evaluating the approach, I found it unnecessarily expensive for this application.

PROBLEM WITH FFT WRT LIMITED HARDWARE:

* Storing large sample buffers
* Higher RAM consumption
* Increased CPU usage
* Calculating hundreds of frequencies that are simply not needed

For a resource-constrained microcontroller like the ESP8266, this felt inefficient when my goal was only to measure a single frequency.

---

## The Goertzel Algorithm

Instead of analyzing the entire frequency spectrum like an FFT, Goertzel focuses on only one specific frequency. In my case, that frequency was **50Hz**.

As each ADC sample arrives, the algorithm continuously accumulates the energy associated with the target frequency. At the end of the sampling window, it calculates the magnitude of that frequency component directly.

This means the algorithm effectively answers a single question:

> How much 50Hz energy is present in the signal?

without wasting resources analyzing frequencies that are irrelevant to the measurement.

---

## Advantage of GOERTZEL Here

* **Excellent Noise Rejection** – Frequencies other than 50Hz contribute very little to the final result.
* **Minimal Memory Usage** – No large sample buffers are required.
* **Low CPU Overhead** – Only a few mathematical operations are performed per sample.
* **High Sampling Accuracy** – The microcontroller remains free to maintain a precise sampling rate.
* **Reliable Low-Current Detection** – Even currents as low as ~60mA can be measured consistently.

---




