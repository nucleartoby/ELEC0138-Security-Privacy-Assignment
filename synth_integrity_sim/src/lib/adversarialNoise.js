const clampChannel = (value) => Math.max(0, Math.min(255, value))

export const FGSM_SIM_EPSILON = 2.8

export function applyFgsmStylePerturbation(imageData, frameIndex, epsilon = FGSM_SIM_EPSILON) {
  const { data, width, height } = imageData

  for (let pixel = 0; pixel < width * height; pixel += 1) {
    const base = pixel * 4
    const x = pixel % width
    const y = (pixel / width) | 0

    const pseudoGradient =
      Math.sin((x + frameIndex * 0.17) * 0.11) +
      Math.cos((y - frameIndex * 0.13) * 0.07) +
      Math.sin((x + y) * 0.05)
    const sign = pseudoGradient >= 0 ? 1 : -1

    data[base] = clampChannel(data[base] + sign * epsilon * 0.4)
    data[base + 1] = clampChannel(data[base + 1] - sign * epsilon * 0.25)
    data[base + 2] = clampChannel(data[base + 2] + sign * epsilon * 0.15)
  }

  return imageData
}
