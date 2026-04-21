# Synth-Integrity

`Synth-Integrity` is a React + Vite proof-of-concept built for a cybersecurity presentation.  
It demonstrates how a biometric onboarding journey can look under normal conditions, payload injection, and adversarial perturbation.

This is an academic demo, not a production security product.

## Demo flow

The UI is split into two panes:

- **Attacker Dashboard (left)**  
  Includes the 3-step Identity Workshop (upload, synthesis, weaponisation) and live controls.

- **Bank App View (right)**  
  A mobile-style onboarding viewport with face detection, landmark overlay, and liveness status.

## Current behaviour

- **Stage A (webcam):** live webcam feed, normal detection loop.
- **Stage C (payload injected):** feed switches to `public/payload.mp4`.
- **Stage D (payload + adversarial noise):** FGSM-style perturbation layer is applied to the payload path.
- **Reset to Stage A:** returns to webcam mode and clears payload peak state.

### Liveness scoring

- Scores are derived from live face-api signals (face confidence + landmark-driven heuristics).
- In payload mode, the UI uses **peak-hold scoring** (highest observed value) to stabilise demo output.
- Confidence labels and review states are mapped in `src/lib/livenessEngine.js`.

### Face landmarks

- Landmarks are detected with `face-api.js` and rendered on-screen as red points for clarity.
- Landmark count and a small summary metric are shown in the status card.

## Real vs simulated parts

### Real

- Webcam capture via `getUserMedia`
- Payload source switching
- Face detection + landmark extraction with `face-api.js`
- Model loading from `public/models`

### Simulated / approximated

- Attack narrative and state transitions for presentation
- Adversarial bypass behaviour (FGSM-style approximation, not full white-box training/inference)

## Stack

- React (Vite)
- Tailwind CSS
- Framer Motion
- Lucide React
- face-api.js

## Run locally

```bash
npm install
npm run dev
```

Other commands:

```bash
npm run lint
npm run build
```

## Key files

- `src/App.jsx` — top-level orchestration and stage/reset logic
- `src/components/AttackerPane.jsx` — attacker-side layout
- `src/components/IdentityWorkshop.jsx` — upload/synthesis/weaponisation flow
- `src/components/AttackControls.jsx` — adversarial toggle, webcam toggle, reset action
- `src/components/BankPane.jsx` — mobile emulator, media pipeline, landmark overlay
- `src/lib/faceApiService.js` — model loading and live detection metadata
- `src/lib/livenessEngine.js` — stage/status/confidence mapping
- `src/lib/adversarialNoise.js` — perturbation rendering helper
- `public/models/` — face-api model assets
- `public/payload.mp4` — payload demo clip
