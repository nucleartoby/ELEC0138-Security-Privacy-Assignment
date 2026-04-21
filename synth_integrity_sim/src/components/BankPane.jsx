import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, LoaderCircle, ShieldAlert } from 'lucide-react'
import { motion as Motion } from 'framer-motion'
import { STATUS_LABELS } from '../data/statusText.uk'
import { detectFaceMeta, ensureFaceApiModels } from '../lib/faceApiService'
import { applyFgsmStylePerturbation } from '../lib/adversarialNoise'

const badgeStyles = {
  scanning: 'bg-slate-100 text-slate-700 border-slate-200',
  verified: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  spoofDetected: 'bg-rose-100 text-rose-700 border-rose-200',
  caution: 'bg-amber-100 text-amber-700 border-amber-200',
}

const badgeIcons = {
  scanning: LoaderCircle,
  verified: CheckCircle2,
  spoofDetected: ShieldAlert,
  caution: AlertTriangle,
}

export function BankPane({
  sourceMode,
  livenessState,
  noiseEnabled,
  detectionMeta,
  onDetectionMetaChange,
}) {
  const videoRef = useRef(null)
  const payloadVideoRef = useRef(null)
  const adversarialCanvasRef = useRef(null)
  const landmarkOverlayRef = useRef(null)
  const frameTickRef = useRef(0)
  const [cameraError, setCameraError] = useState('')

  useEffect(() => {
    let mounted = true
    let mediaStream

    async function initSources() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 390 },
            height: { ideal: 844 },
            facingMode: 'user',
            frameRate: { ideal: 24, max: 30 },
          },
          audio: false,
        })

        if (!mounted) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }

        mediaStream = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play().catch(() => {})
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to initialise camera'
        setCameraError(message)
        onDetectionMetaChange((prev) => ({ ...prev, error: message }))
        return
      }

      try {
        await ensureFaceApiModels()
        onDetectionMetaChange((prev) => ({ ...prev, modelReady: true, error: '' }))
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Face model initialisation failed'
        onDetectionMetaChange((prev) => ({ ...prev, error: message }))
      }
    }

    initSources()

    return () => {
      mounted = false
      mediaStream?.getTracks().forEach((track) => track.stop())
    }
  }, [onDetectionMetaChange])

  useEffect(() => {
    if (sourceMode !== 'webcam' || !videoRef.current) {
      return
    }

    videoRef.current.play().catch(() => {})
  }, [sourceMode])

  useEffect(() => {
    let rafId

    const drawAdversarialFrame = () => {
      const payload = payloadVideoRef.current
      const canvas = adversarialCanvasRef.current

      if (
        payload &&
        canvas &&
        payload.readyState >= 2 &&
        sourceMode === 'payload' &&
        noiseEnabled
      ) {
        const ctx = canvas.getContext('2d', { willReadFrequently: true })
        if (ctx) {
          if (canvas.width !== payload.videoWidth || canvas.height !== payload.videoHeight) {
            canvas.width = payload.videoWidth || 960
            canvas.height = payload.videoHeight || 540
          }

          ctx.drawImage(payload, 0, 0, canvas.width, canvas.height)
          const frame = ctx.getImageData(0, 0, canvas.width, canvas.height)
          const perturbed = applyFgsmStylePerturbation(frame, frameTickRef.current++)
          ctx.putImageData(perturbed, 0, 0)
        }
      }

      rafId = window.requestAnimationFrame(drawAdversarialFrame)
    }

    rafId = window.requestAnimationFrame(drawAdversarialFrame)

    return () => {
      window.cancelAnimationFrame(rafId)
    }
  }, [sourceMode, noiseEnabled])

  useEffect(() => {
    const overlay = landmarkOverlayRef.current
    const baseElement =
      sourceMode === 'payload' && noiseEnabled
        ? adversarialCanvasRef.current
        : sourceMode === 'payload'
          ? payloadVideoRef.current
          : videoRef.current

    if (!overlay || !baseElement) {
      return
    }

    const baseWidth =
      'videoWidth' in baseElement && baseElement.videoWidth
        ? baseElement.videoWidth
        : baseElement.width
    const baseHeight =
      'videoHeight' in baseElement && baseElement.videoHeight
        ? baseElement.videoHeight
        : baseElement.height

    if (!baseWidth || !baseHeight) {
      return
    }

    overlay.width = baseWidth
    overlay.height = baseHeight
    const ctx = overlay.getContext('2d')
    if (!ctx) {
      return
    }

    ctx.clearRect(0, 0, overlay.width, overlay.height)
    const points = detectionMeta.landmarkPoints ?? []
    if (!points.length) {
      return
    }

    ctx.fillStyle = 'rgba(239, 68, 68, 0.95)'
    ctx.strokeStyle = 'rgba(255, 220, 220, 0.95)'
    ctx.lineWidth = 0.8
    points.forEach(({ x, y }) => {
      ctx.beginPath()
      ctx.arc(x, y, 2.9, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    })
  }, [sourceMode, noiseEnabled, detectionMeta.landmarkPoints])

  useEffect(() => {
    let rafId

    const runDetection = async () => {
      const activeVideo =
        sourceMode === 'payload' && noiseEnabled
          ? adversarialCanvasRef.current
          : sourceMode === 'payload'
            ? payloadVideoRef.current
            : videoRef.current
      try {
        const nextMeta = await detectFaceMeta(activeVideo)
        onDetectionMetaChange((prev) => {
          const nextState = { ...prev, ...nextMeta, error: '' }

          if (sourceMode !== 'payload') {
            nextState.payloadPeakScore = null
            nextState.payloadPeakConfidence = 'None'
            return nextState
          }

          if (!nextMeta.hasFace || typeof nextMeta.liveLivenessScore !== 'number') {
            return nextState
          }

          const previousPeak = prev.payloadPeakScore
          if (previousPeak === null || nextMeta.liveLivenessScore > previousPeak) {
            nextState.payloadPeakScore = nextMeta.liveLivenessScore
            nextState.payloadPeakConfidence = nextMeta.liveConfidence ?? prev.payloadPeakConfidence
          }

          return nextState
        })
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Face detection unavailable'
        onDetectionMetaChange((prev) => ({ ...prev, error: message }))
      }
      rafId = window.setTimeout(runDetection, 650)
    }

    if (detectionMeta.modelReady) {
      runDetection()
    }

    return () => {
      window.clearTimeout(rafId)
    }
  }, [sourceMode, noiseEnabled, detectionMeta.modelReady, onDetectionMetaChange])

  const BadgeIcon = badgeIcons[livenessState.badge] ?? LoaderCircle

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden bg-bank-soft/70 p-3">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-base font-semibold text-bank-deep">Bank App View</h2>
        <span className="rounded-md border border-bank-border bg-white px-3 py-1 text-xs font-medium text-bank-deep">
          State {livenessState.stage}
        </span>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[1fr_170px] gap-3">
        <div className="mx-auto flex min-h-0 items-center justify-center">
          <div className="relative h-[min(100%,820px)] max-h-full w-auto max-w-full aspect-[390/844]">
            <div className="pointer-events-none absolute -left-1 top-24 h-14 w-1 rounded-l bg-slate-400/60" />
            <div className="pointer-events-none absolute -left-1 top-44 h-10 w-1 rounded-l bg-slate-400/50" />
            <div className="pointer-events-none absolute -right-1 top-36 h-16 w-1 rounded-r bg-slate-400/60" />

            <div className="relative h-full w-full rounded-[2.25rem] bg-slate-900 p-2.5 shadow-[0_20px_40px_rgba(15,23,42,0.38)]">
              <div className="relative h-full w-full overflow-hidden rounded-[1.9rem] border border-slate-700 bg-slate-950">
                <div className="pointer-events-none absolute left-1/2 top-2 z-20 h-6 w-28 -translate-x-1/2 rounded-full bg-black/80" />
                <div className="pointer-events-none absolute left-3 right-3 top-3 z-20 flex items-center justify-between text-[10px] font-medium text-slate-100">
                  <span>09:41</span>
                  <span>{sourceMode === 'payload' ? 'Virtual Cam' : '4G'}</span>
                </div>

                <video
                  ref={videoRef}
                  className={`h-full w-full object-cover ${sourceMode === 'webcam' ? 'opacity-100' : 'opacity-0'} transition-opacity duration-200`}
                  autoPlay
                  muted
                  playsInline
                />
                <video
                  ref={payloadVideoRef}
                  src="/payload.mp4"
                  className={`absolute inset-0 h-full w-full object-contain bg-slate-950 ${sourceMode === 'payload' ? 'opacity-100' : 'opacity-0'} transition-opacity duration-200`}
                  autoPlay
                  muted
                  loop
                  playsInline
                />
                <canvas
                  ref={adversarialCanvasRef}
                  className={`absolute inset-0 h-full w-full object-contain bg-slate-950 ${sourceMode === 'payload' && noiseEnabled ? 'opacity-100' : 'opacity-0'} transition-opacity duration-200`}
                />
                <canvas
                  ref={landmarkOverlayRef}
                  className="pointer-events-none absolute inset-0 h-full w-full object-contain"
                />

                {noiseEnabled && sourceMode === 'payload' && (
                  <div
                    className="pointer-events-none absolute inset-0 opacity-35 mix-blend-overlay"
                    style={{
                      backgroundImage:
                        'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.9) 1px, transparent 0), linear-gradient(120deg, rgba(48,255,170,0.2), rgba(255,255,255,0.08))',
                      backgroundSize: '3px 3px, 100% 100%',
                    }}
                  />
                )}
              </div>
            </div>
          </div>
        </div>

        <aside className="flex min-h-0 items-start">
          <div className="w-full rounded-xl border border-bank-border bg-white p-2 shadow-sm">
          <div className="mb-1 flex items-center justify-between text-xs font-medium text-slate-700">
            <span>Liveness Status</span>
            <span>{livenessState.score.toFixed(1)}%</span>
          </div>
          <div className="h-2 rounded-full bg-slate-200">
            <Motion.div
              className="h-2 rounded-full bg-bank-deep"
              animate={{ width: `${livenessState.score}%` }}
              transition={{ type: 'spring', stiffness: 70, damping: 22 }}
            />
          </div>
          <div className="mt-2 flex flex-col gap-1">
            <span
              className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${badgeStyles[livenessState.badge]}`}
            >
              <BadgeIcon className="h-3 w-3" />
              {STATUS_LABELS[livenessState.badge]}
            </span>
            <span className="rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-600">
              {livenessState.confidence}
            </span>
            <span className="rounded-md border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-[10px] text-indigo-700">
              Landmarks: {detectionMeta.landmarkCount ?? 0}
            </span>
            {detectionMeta.landmarksSummary && (
              <span className="rounded-md border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-[10px] text-indigo-700">
                Eye/Jaw: {detectionMeta.landmarksSummary.eyeToJawRatio}
              </span>
            )}
            {(cameraError || detectionMeta.error) && (
              <span className="rounded-md border border-rose-200 bg-rose-50 px-1.5 py-0.5 text-[10px] text-rose-700">
                {cameraError || detectionMeta.error}
              </span>
            )}
          </div>
          </div>
        </aside>
      </div>
    </section>
  )
}
