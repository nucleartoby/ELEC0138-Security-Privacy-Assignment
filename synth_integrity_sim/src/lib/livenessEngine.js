const scoreConfig = {
  default: { badge: 'verified', issue: '' },
  inject: {
    badge: 'caution',
    issue: 'Digital Artifacts Detected',
  },
  adversarial: {
    badge: 'caution',
    issue: 'Adversarial perturbation active',
  },
  noFace: { score: 0, confidence: 'None', badge: 'scanning', issue: 'No face centred in viewfinder' },
}

export function resolveLivenessState({
  sourceMode,
  noiseEnabled,
  hasFace,
  liveLivenessScore,
  liveConfidence,
}) {
  if (!hasFace) {
    return {
      stage: 'A',
      ...scoreConfig.noFace,
    }
  }

  if (sourceMode === 'payload') {
    if (noiseEnabled) {
      const resolvedScore =
        typeof liveLivenessScore === 'number'
          ? liveLivenessScore
          : 0
      const resolvedConfidence = liveConfidence ?? 'None'
      const resolvedBadge = resolvedScore >= 75 ? 'verified' : 'caution'
      return {
        stage: 'D',
        ...scoreConfig.adversarial,
        score: resolvedScore,
        confidence: resolvedConfidence,
        badge: resolvedBadge,
        issue: resolvedBadge === 'verified' ? '' : scoreConfig.adversarial.issue,
      }
    }

    return {
      stage: 'C',
      ...scoreConfig.inject,
      score: typeof liveLivenessScore === 'number' ? liveLivenessScore : 0,
      confidence: liveConfidence ?? 'None',
    }
  }

  return {
    stage: 'A',
    ...scoreConfig.default,
    score: typeof liveLivenessScore === 'number' ? liveLivenessScore : 0,
    confidence: liveConfidence ?? 'None',
  }
}
