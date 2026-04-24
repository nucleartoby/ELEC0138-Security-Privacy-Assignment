import { useMemo, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { BankPane } from './components/BankPane'
import { AttackerPane } from './components/AttackerPane'
import { resolveLivenessState } from './lib/livenessEngine'

function App() {
  const [sourceMode, setSourceMode] = useState('webcam')
  const [noiseEnabled, setNoiseEnabled] = useState(false)
  const [detectionMeta, setDetectionMeta] = useState({
    hasFace: false,
    modelReady: false,
    landmarkCount: 0,
    landmarksSummary: null,
    landmarkPoints: [],
    liveLivenessScore: 0,
    liveConfidence: 'None',
    payloadPeakScore: null,
    payloadPeakConfidence: 'None',
    error: '',
  })

  const effectiveLiveScore =
    sourceMode === 'payload'
      ? (detectionMeta.payloadPeakScore ?? detectionMeta.liveLivenessScore)
      : detectionMeta.liveLivenessScore
  const effectiveLiveConfidence =
    sourceMode === 'payload' && detectionMeta.payloadPeakScore !== null
      ? detectionMeta.payloadPeakConfidence
      : detectionMeta.liveConfidence

  const livenessState = useMemo(
    () =>
      resolveLivenessState({
        sourceMode,
        noiseEnabled,
        hasFace: detectionMeta.hasFace,
        liveLivenessScore: effectiveLiveScore,
        liveConfidence: effectiveLiveConfidence,
      }),
    [
      sourceMode,
      noiseEnabled,
      detectionMeta.hasFace,
      effectiveLiveScore,
      effectiveLiveConfidence,
    ],
  )

  const resetToStageA = () => {
    setSourceMode('webcam')
    setNoiseEnabled(false)
    setDetectionMeta((prev) => ({
      ...prev,
      payloadPeakScore: null,
      payloadPeakConfidence: 'None',
      error: '',
    }))
  }

  return (
    <main className="min-h-screen bg-slate-100 px-4 py-4 text-slate-900 lg:px-6">
      <div className="mx-auto flex h-[calc(100vh-2rem)] max-h-[1080px] w-full max-w-[1880px] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-pane">
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-bank-deep" />
            <h1 className="text-lg font-semibold tracking-tight text-bank-deep">Synth-Integrity</h1>
          </div>
          <p className="text-sm text-slate-600">Biometric Onboarding Liveness Injection PoC</p>
        </header>
        <section className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-2">
          <AttackerPane
            sourceMode={sourceMode}
            noiseEnabled={noiseEnabled}
            livenessState={livenessState}
            onInjectPayload={() => {
              setDetectionMeta((prev) => ({
                ...prev,
                payloadPeakScore: null,
                payloadPeakConfidence: 'None',
              }))
              setSourceMode('payload')
            }}
            onDisableInjection={() => {
              resetToStageA()
            }}
            onNoiseToggle={setNoiseEnabled}
            onResetStageA={resetToStageA}
          />
          <BankPane
            sourceMode={sourceMode}
            livenessState={livenessState}
            noiseEnabled={noiseEnabled}
            detectionMeta={detectionMeta}
            onDetectionMetaChange={setDetectionMeta}
          />
        </section>
      </div>
    </main>
  )
}

export default App
