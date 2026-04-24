import { Power, Shield } from 'lucide-react'

export function AttackControls({
  sourceMode,
  noiseEnabled,
  onNoiseToggle,
  onDisableInjection,
  onResetStageA,
}) {
  const webcamActive = sourceMode === 'webcam'

  return (
    <section className="rounded-xl border border-attacker-border bg-attacker-panel p-3">
      <div className="mb-2 flex items-center gap-2">
        <Shield className="h-4 w-4 text-attacker-accent" />
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-200">Real-time Attack Control</h3>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => onNoiseToggle(!noiseEnabled)}
          className="flex items-center justify-between rounded-md border border-slate-600 bg-slate-900/20 px-2.5 py-1.5 text-xs text-slate-300 transition hover:border-slate-500"
        >
          <span className="inline-flex items-center gap-2 font-medium">
            <Shield className="h-4 w-4" />
            Adversarial noise
          </span>
          <span
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition ${
              noiseEnabled ? 'bg-emerald-500' : 'bg-slate-600'
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition ${
                noiseEnabled ? 'translate-x-5' : 'translate-x-0.5'
              }`}
            />
          </span>
        </button>

        <button
          type="button"
          onClick={onDisableInjection}
          disabled={webcamActive}
          className="flex items-center justify-between rounded-md border border-slate-600 bg-slate-900/20 px-2.5 py-1.5 text-xs text-slate-300 transition hover:border-slate-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="inline-flex items-center gap-2 font-medium">
            <Power className="h-4 w-4" />
            Live webcam
          </span>
          <span
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition ${
              webcamActive ? 'bg-emerald-500' : 'bg-slate-600'
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition ${
                webcamActive ? 'translate-x-5' : 'translate-x-0.5'
              }`}
            />
          </span>
        </button>
      </div>

      <button
        type="button"
        onClick={onResetStageA}
        className="mt-2 w-full rounded-md border border-attacker-accent/50 bg-attacker-accent/15 px-2.5 py-1.5 text-xs font-medium text-attacker-accent transition hover:bg-attacker-accent/25"
      >
        Reset to Stage A
      </button>
    </section>
  )
}
