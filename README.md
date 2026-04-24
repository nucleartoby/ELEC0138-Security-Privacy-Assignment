# ELEC0138 — Security & Privacy Assignment

UCL ELEC0138 final assignment exploring DDoS mitigation and biometric liveness attacks/defences. Four components: a defended API gateway, a network simulator, a biometric attack demo, and a deep-learning liveness defence.

---

## Repository Structure

```
ELEC0138-Security-Privacy-Assignment/
├── DDoS_defence_model/      # Multi-layer DDoS defence middleware + Flask API
├── ddos_sim/                # NS3-based network simulation framework
├── synth_integrity_sim/     # React demo: deepfake liveness attack simulation
└── liveness_defense/        # PyTorch: liveness detection defence model
```

---

## 1. DDoS Defence Model

`DDoS_defence_model/` — A proof-of-concept Flask API gateway with a 5-layer DDoS defence middleware protecting a mock fintech service. Achieves ~99.9% block rate with <4 ms added latency under tested conditions.

### Defence Layers

| Layer | Mechanism | Threshold |
|-------|-----------|-----------|
| 1 | IP Blocklist (static + dynamic) | Manual or auto-triggered |
| 2 | Reputation Tracker (score decay) | Block ≥100 pts, auto-block ≥60 pts |
| 3 | Token Bucket (per-IP rate limit) | 20 token burst, 5 tokens/s refill |
| 4 | Sliding Window Detector | 80 requests / 10 s |
| 5 | ML Anomaly Detector (IsolationForest) | 5% contamination threshold |

The ML detector ([ml_detector.py](DDoS_defence_model/ml_detector.py)) extracts per-IP features: request rate, mean/stddev inter-arrival time, path diversity, and burst ratio.

### Attack Variants Tested

- **Variant A** — Single-source burst (50 threads, 1 IP)
- **Variant B** — Sustained flood (15 threads, long duration)
- **Variant C** — Distributed botnet (40 threads, 20 spoofed IPs)
- **Variant D** — Slow drip (100 bots at 1 req/s)
- **Variant E** — Mixed burst/idle across multiple endpoints

### Quick Start

```bash
cd DDoS_defence_model
pip install flask waitress scikit-learn numpy matplotlib requests

# Terminal 1 — unprotected baseline (port 5001)
python protected_server.py --no-defence --port 5001

# Terminal 2 — protected server (port 5000)
python protected_server.py

# Terminal 3 — run benchmark (vulnerable vs defended)
python benchmark.py --threads 50 --duration 15

# Run all 5 attack variants
python experiments.py --target http://localhost:5000 --duration 10

# Measure latency overhead under normal load
python latency_benchmark.py --target http://localhost:5000
```

### Key Files

| File | Purpose |
|------|---------|
| [defence_engine.py](DDoS_defence_model/defence_engine.py) | Orchestrates all 5 defence layers |
| [ml_detector.py](DDoS_defence_model/ml_detector.py) | IsolationForest anomaly detector |
| [protected_server.py](DDoS_defence_model/protected_server.py) | Flask app with mock fintech endpoints |
| [attack_client.py](DDoS_defence_model/attack_client.py) | HTTP flood generator (threading + spoofed IPs) |
| [benchmark.py](DDoS_defence_model/benchmark.py) | Before/after throughput comparison |
| [experiments.py](DDoS_defence_model/experiments.py) | Runs all 5 attack variants, outputs CSV/MD |
| [latency_benchmark.py](DDoS_defence_model/latency_benchmark.py) | p50/p95/p99 latency under normal load |

---

## 2. DDoS Network Simulator

`ddos_sim/` — NS3-based simulation framework for evaluating DDoS attack scenarios in a realistic network topology using Docker-containerised nodes.

### Requirements

- NS3
- Docker
- Python 3
- Conda (see `environment.yml`)

### Quick Start

```bash
cd ddos_sim
bash install.sh
conda env create -f environment.yml
conda activate ddosim
python main.py --config ddosim_config.yaml
```

---

## 3. Synthetic Identity / Liveness Attack Simulation

`synth_integrity_sim/` — React web app demonstrating how a deepfake pipeline can bypass biometric liveness detection in a fintech onboarding flow.

### Features

- Live webcam feed with real-time face detection (face-api.js)
- Facial landmark overlay
- **Payload injection mode** — switches camera feed to a pre-recorded video
- **Adversarial noise layer** — FGSM-style perturbation simulation rendered over the feed
- Attacker dashboard with 3-step Identity Workshop (upload → synthesis → weaponise)
- Side-by-side attacker and bank-app views with live confidence scoring

### Quick Start

```bash
cd synth_integrity_sim
npm install
npm run dev       # dev server at http://localhost:5173
npm run build     # production build
```

### Key Files

| File | Purpose |
|------|---------|
| [src/App.jsx](synth_integrity_sim/src/App.jsx) | Top-level layout and state |
| [src/components/AttackerPane.jsx](synth_integrity_sim/src/components/AttackerPane.jsx) | Attack controls |
| [src/components/IdentityWorkshop.jsx](synth_integrity_sim/src/components/IdentityWorkshop.jsx) | Upload / synthesis / weaponise flow |
| [src/components/BankPane.jsx](synth_integrity_sim/src/components/BankPane.jsx) | Mobile bank emulator + media pipeline |
| [src/lib/livenessEngine.js](synth_integrity_sim/src/lib/livenessEngine.js) | Stage/status/confidence mapping |
| [src/lib/adversarialNoise.js](synth_integrity_sim/src/lib/adversarialNoise.js) | Perturbation rendering |

> **Note:** The adversarial bypass is a visual approximation for presentation purposes, not a trained white-box attack.

---

## 4. Liveness Detection Defence

`liveness_defense/` — PyTorch-based defence system for biometric liveness detection, combining challenge-response, rPPG heart-rate sensing, and a denoising autoencoder for adversarial robustness.

### Key Modules

| File | Purpose |
|------|---------|
| [src/model.py](liveness_defense/src/model.py) | Neural network classifier architecture |
| [src/train_classifier.py](liveness_defense/src/train_classifier.py) | Classifier training pipeline |
| [src/train_denoiser.py](liveness_defense/src/train_denoiser.py) | Denoising autoencoder training |
| [src/inference.py](liveness_defense/src/inference.py) | Runtime inference engine |
| [src/rppg.py](liveness_defense/src/rppg.py) | Remote photoplethysmography (heart-rate liveness) |
| [src/challenge.py](liveness_defense/src/challenge.py) | Challenge-response (blink / mouth movement) |
| [src/extract_features.py](liveness_defense/src/extract_features.py) | Landmark + rPPG feature extraction |

### Requirements

```bash
cd liveness_defense
pip install torch torchvision opencv-python mediapipe numpy scipy scikit-learn pywavelets pandas matplotlib
python src/train_classifier.py
python src/inference.py
```

---

## Dependencies Summary

| Component | Stack |
|-----------|-------|
| DDoS_defence_model | Python 3, Flask, Waitress, scikit-learn, NumPy, Matplotlib |
| ddos_sim | Python 3, NS3, Docker, Conda |
| synth_integrity_sim | React 19, Vite, Tailwind CSS, face-api.js, Framer Motion |
| liveness_defense | Python 3, PyTorch, OpenCV, MediaPipe, PyWavelets |
