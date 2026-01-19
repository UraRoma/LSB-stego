# Adaptive LSB Steganography (Research Prototype)

## 📌 Overview

This repository contains a **research-oriented proof-of-concept** implementation of image steganography based on **LSB matching** with **key-driven pseudo-random embedding** and **local image complexity adaptation**.

The project is developed in the context of **Information Security research** and focuses on analyzing **covert data transmission techniques** and their detectability rather than providing a production-ready steganographic tool.

---

## 🎯 Goals of the Project

* Demonstrate a practical **covert channel** using lossless image formats
* Reduce statistical artifacts compared to naive LSB substitution
* Provide a flexible architecture for **steganalysis research**
* Serve as a baseline for experimenting with detection and defense methods

---

## 🔬 Threat Model & Security Context

This project models techniques commonly associated with covert communication and maps to the following **MITRE ATT&CK** techniques:

* **T1001.003 — Data Obfuscation: Steganography**
* **T1027 — Obfuscated / Encrypted Data**

The implementation is intended for **educational and defensive research purposes only**.

---

## ⚙️ Key Features

* Lossless image support: **BMP, PNG**
* Deterministic **key-based pseudo-random embedding**
* **Adaptive pixel selection** based on local image complexity
* **LSB matching (±1)** instead of direct bit replacement
* Modular design allowing easy replacement of PRNG or complexity metrics

---

## 🧠 Algorithm Overview

1. User password is converted into a 32-bit seed
2. A deterministic PRNG generates pseudo-random embedding positions
3. Only pixels with sufficient local complexity are selected
4. Message bits are embedded using **LSB matching**
5. The modified image is saved without lossy compression

---

## 🛠️ Implementation Details

* Language: **Python 3**
* Image processing: **Pillow**
* PRNG: Simple Linear Congruential Generator (LCG) — *used intentionally for MVP*
* Formats: BMP (preferred), PNG (lossless only)

> ⚠️ Cryptographically secure PRNGs are intentionally **not used** at this stage, as the project focuses on architectural evaluation rather than cryptographic strength.

---

## 🚀 Usage

### Requirements

```bash
pip install pillow
```

### Example

```bash
python stego.py
```

The example embeds and extracts a short test message using the same password and parameters.

---

## 📊 Limitations

* Proof-of-concept implementation
* Simplified PRNG (not cryptographically secure)
* No robustness against lossy recompression (e.g. JPEG)
* Limited experimental dataset

These limitations are **explicit design choices** aligned with the research scope of the project.

---

## 🔮 Future Work

* Replace LCG with cryptographically secure PRNG (HMAC-DRBG / ChaCha20)
* Integrate payload encryption
* Add automated steganalysis evaluation
* Extend support to compressed formats
* Benchmark against existing tools (Steghide, OpenStego)

---

## 📚 References

* MITRE ATT&CK Framework
* LSB Matching in Steganography
* Image Steganalysis Techniques

---

## ⚠️ Disclaimer

This project is intended **for educational and research purposes only**.
The author does not endorse or support malicious use of steganography.

---

## 👤 Author

Student project in Information Security
Poster session / academic defense

