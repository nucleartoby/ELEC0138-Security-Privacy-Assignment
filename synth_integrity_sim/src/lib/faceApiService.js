import * as faceapi from 'face-api.js'

let modelsLoaded = false
let previousFaceCenter = null
let previousEyeToJawRatio = null

export async function ensureFaceApiModels() {
  if (modelsLoaded) {
    return true
  }

  const modelPath = '/models'
  await Promise.all([
    faceapi.nets.tinyFaceDetector.loadFromUri(modelPath),
    faceapi.nets.faceLandmark68Net.loadFromUri(modelPath),
  ])

  modelsLoaded = true
  return true
}

export async function detectFaceMeta(videoElement) {
  if (!videoElement || videoElement.readyState < 2) {
    return {
      hasFace: false,
      landmarkCount: 0,
      landmarksSummary: null,
      landmarkPoints: [],
      liveLivenessScore: 0,
      liveConfidence: 'None',
    }
  }

  const detection = await faceapi
    .detectSingleFace(videoElement, new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.35 }))
    .withFaceLandmarks()

  if (!detection) {
    previousFaceCenter = null
    previousEyeToJawRatio = null
    return {
      hasFace: false,
      landmarkCount: 0,
      landmarksSummary: null,
      landmarkPoints: [],
      liveLivenessScore: 0,
      liveConfidence: 'None',
    }
  }

  const landmarks = detection.landmarks
  const points = landmarks.positions ?? []
  const jaw = landmarks.getJawOutline()
  const leftEye = landmarks.getLeftEye()
  const rightEye = landmarks.getRightEye()

  const jawWidth = Math.abs((jaw.at(-1)?.x ?? 0) - (jaw.at(0)?.x ?? 0))
  const eyeDistance = Math.abs((rightEye[0]?.x ?? 0) - (leftEye[3]?.x ?? 0))
  const eyeToJawRatio = jawWidth > 0 ? eyeDistance / jawWidth : 0
  const detectionScore = detection.detection.score ?? 0
  const landmarkCoverage = Math.min(points.length / 68, 1)

  const center = points.length
    ? points.reduce(
        (acc, point) => ({ x: acc.x + point.x / points.length, y: acc.y + point.y / points.length }),
        { x: 0, y: 0 },
      )
    : { x: 0, y: 0 }

  let motionSignal = 0
  if (previousFaceCenter && jawWidth > 0) {
    const dx = center.x - previousFaceCenter.x
    const dy = center.y - previousFaceCenter.y
    const normalizedMotion = Math.sqrt(dx * dx + dy * dy) / jawWidth
    motionSignal = Math.min(normalizedMotion * 5.5, 1)
  }
  previousFaceCenter = center
  let expressionSignal = 0
  if (previousEyeToJawRatio !== null) {
    expressionSignal = Math.min(Math.abs(eyeToJawRatio - previousEyeToJawRatio) * 12, 1)
  }
  previousEyeToJawRatio = eyeToJawRatio

  const score01 = Math.min(
    Math.max(
      detectionScore * 0.68 + motionSignal * 0.18 + landmarkCoverage * 0.1 + expressionSignal * 0.04,
      0,
    ),
    1,
  )
  const liveLivenessScore = Number((score01 * 100).toFixed(1))
  const liveConfidence =
    liveLivenessScore >= 75 ? 'High' : liveLivenessScore >= 45 ? 'Medium' : 'Low'

  return {
    hasFace: true,
    landmarkCount: points.length,
    landmarksSummary: {
      jawWidth: Number(jawWidth.toFixed(1)),
      eyeDistance: Number(eyeDistance.toFixed(1)),
      eyeToJawRatio: Number(eyeToJawRatio.toFixed(3)),
    },
    landmarkPoints: points.map((point) => ({ x: point.x, y: point.y })),
    liveLivenessScore,
    liveConfidence,
  }
}
