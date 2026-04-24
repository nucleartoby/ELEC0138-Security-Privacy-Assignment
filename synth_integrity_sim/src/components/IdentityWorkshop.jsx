import { useEffect, useState } from 'react'
import { motion as Motion } from 'framer-motion'
import { FileUp, PlayCircle, WandSparkles } from 'lucide-react'
import { SYNTHESIS_STEPS } from '../data/statusText.uk'

export function IdentityWorkshop({ sourceMode, onInjectPayload }) {
  const [fileName, setFileName] = useState('')
  const [synthesisRunning, setSynthesisRunning] = useState(false)
  const [synthesisProgress, setSynthesisProgress] = useState(0)
  const [stepText, setStepText] = useState(SYNTHESIS_STEPS[0])

  useEffect(() => {
    if (!synthesisRunning) {
      return undefined
    }

    const interval = window.setInterval(() => {
      setSynthesisProgress((prev) => {
        const next = Math.min(100, prev + 4)
        const stepIndex = Math.min(
          SYNTHESIS_STEPS.length - 1,
          Math.floor((next / 100) * SYNTHESIS_STEPS.length),
        )
        setStepText(SYNTHESIS_STEPS[stepIndex])
        if (next === 100) {
          window.clearInterval(interval)
          setSynthesisRunning(false)
        }
        return next
      })
    }, 180)

    return () => window.clearInterval(interval)
  }, [synthesisRunning])

  const canInject = synthesisProgress >= 100

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-attacker-border bg-attacker-panel p-2.5">
      <div className="mb-2 flex items-center gap-2">
        <WandSparkles className="h-4 w-4 text-attacker-accent" />
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-200">Identity Workshop</h3>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-1.5 overflow-hidden text-xs xl:grid-cols-2">
        <div className="rounded-lg border border-attacker-border bg-slate-950/30 p-2">
          <p className="mb-2 text-xs uppercase tracking-wide text-slate-400">1. Upload Stage</p>
          <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-slate-600 px-2 py-1 text-slate-300 hover:border-attacker-accent hover:text-white">
            <FileUp className="h-4 w-4" />
            <span>{fileName ? `Target ID loaded: ${fileName}` : 'Drop target ID photo or click to upload'}</span>
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(event) => setFileName(event.target.files?.[0]?.name ?? '')}
            />
          </label>
        </div>

        <div className="rounded-lg border border-attacker-border bg-slate-950/30 p-2">
          <p className="mb-2 text-xs uppercase tracking-wide text-slate-400">2. Synthesis Stage</p>
          <button
            type="button"
            disabled={synthesisRunning}
            onClick={() => {
              setSynthesisProgress(0)
              setStepText(SYNTHESIS_STEPS[0])
              setSynthesisRunning(true)
            }}
            className="mb-1.5 w-full rounded-md border border-attacker-accent/40 bg-attacker-accent/15 px-2 py-1 text-xs font-medium text-attacker-accent transition hover:bg-attacker-accent/25 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {synthesisRunning ? 'Neural mapping in progress…' : 'Run Neural Mapping'}
          </button>

          <div className="h-2 rounded-full bg-slate-700">
            <Motion.div
              className="h-2 rounded-full bg-attacker-accent"
              animate={{ width: `${synthesisProgress}%` }}
              transition={{ ease: 'easeInOut' }}
            />
          </div>
          <p className="mt-2 text-xs text-slate-400">{stepText}</p>
        </div>

        <div className="rounded-lg border border-attacker-border bg-slate-950/30 p-2 xl:col-span-2">
          <p className="mb-2 text-xs uppercase tracking-wide text-slate-400">3. Weaponisation Stage</p>
          {canInject ? (
            <video
              src="/payload.mp4"
              className="mb-1.5 h-16 w-full rounded-md object-contain bg-slate-950"
              autoPlay
              muted
              loop
              playsInline
            />
          ) : (
            <div className="mb-1.5 flex h-16 w-full items-center justify-center rounded-md border border-dashed border-slate-600 bg-slate-900/40 px-3 text-center text-xs text-slate-400">
              Payload preview locked until neural mapping completes.
            </div>
          )}
          <button
            type="button"
            disabled={!canInject}
            onClick={onInjectPayload}
            className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-attacker-accent px-2 py-1 text-xs font-semibold text-slate-900 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
          >
            <PlayCircle className="h-4 w-4" />
            Inject Payload to Virtual Camera
          </button>
          <p className="mt-1 text-[11px] text-slate-500">Current source: {sourceMode === 'payload' ? 'Injected payload stream' : 'Live webcam stream'}</p>
        </div>
      </div>
    </section>
  )
}
