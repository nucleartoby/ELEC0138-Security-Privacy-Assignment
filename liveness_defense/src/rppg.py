"""
rPPG Signal Processing Module — Sync_rPPG Method

Implements the preprocessing and feature-extraction pipeline from:
  "Utilizing rPPG Signal Synchronization and Deep Learning Techniques
   for Deepfake Video Detection"  (Susi et al., IEEE Access 2025)

Sync_rPPG Algorithm 1 pipeline (per-cheek):
  1. Average green-channel pixels  →  raw rPPG signal  S_t
  2. Detrend   : S'_t = S_t − LowPass(S_t)          (remove illumination drift)
  3. Bandpass  : Butterworth 0.7–4.0 Hz              (isolate HR band)
  4. DWT       : wavedec(S'_t, 'db4')                (multi-scale decomposition)
  5. Features  : SNR, PSD (Welch), MAD, STD, PCC     (from DWT approx. coeffs)

Cross-cheek PCC is the primary deepfake discriminator:
  real  → PCC ≈ 0.72  (bilateral blood-flow symmetry)
  fake  → PCC ≈ 0.08  (generative models fail to synchronise physiology)
"""

from scipy.signal import welch, detrend, butter, filtfilt
import pywt
import numpy as np

# ── Constants ─────────────────────────────────────────────────────────────────
HR_LOW      = 0.7   # Hz  (42 BPM)
HR_HIGH     = 4.0   # Hz (240 BPM)
DWT_WAVELET = 'db4' # Daubechies-4  (per Sync_rPPG paper)
DWT_LEVEL   = 3     # Decomposition level; auto-reduced for short signals


# ── Preprocessing ─────────────────────────────────────────────────────────────

def detrend_signal(signal, fps=None):
    """
    Remove low-frequency baseline drift.

    Sync_rPPG method:  S'_t = S_t − LowPass(S_t)
    A Butterworth low-pass (~0.4 Hz) is used to estimate the slow baseline
    caused by subject movement or illumination change, then subtracted.

    Falls back to scipy linear detrend when fps is unavailable.

    Args:
        signal : array-like raw rPPG signal
        fps    : sampling frequency (Hz); enables low-pass subtraction

    Returns:
        numpy.ndarray: baseline-removed signal
    """
    signal = np.array(signal, dtype=np.float64)
    if len(signal) < 4:
        return signal
    if fps is not None and fps > 1.0:
        nyq    = fps / 2.0
        cutoff = min(0.4 / nyq, 0.98)          # ~0.4 Hz low-pass for baseline
        b, a   = butter(3, cutoff, btype='low')
        baseline = filtfilt(b, a, signal, method='gust')
        return signal - baseline
    return detrend(signal, type='linear')       # linear fallback


def bandpass_filter(signal, fps, low=HR_LOW, high=HR_HIGH):
    """
    Butterworth bandpass filter — isolate heart-rate band (0.7–4.0 Hz).

    Applied after detrending in the Sync_rPPG pipeline.
    Also retained as a standalone function for visualisation / debugging.

    Args:
        signal : array-like signal (detrended)
        fps    : sampling frequency (Hz)
        low    : low  cut-off (Hz), default 0.7
        high   : high cut-off (Hz), default 4.0

    Returns:
        numpy.ndarray: bandpass-filtered signal
    """
    signal = np.array(signal, dtype=np.float64)
    if fps is None or fps < 2 * high:
        return signal
    nyq  = fps / 2.0
    b, a = butter(2, [low / nyq, high / nyq], btype='band')
    return filtfilt(b, a, signal, method='gust')


def apply_dwt(signal, wavelet=DWT_WAVELET, level=DWT_LEVEL):
    """
    Discrete Wavelet Transform with Daubechies-4 wavelet (Sync_rPPG Eq. 2).

      x(t) = Σ_m  c_m · ψ_m(t)

    Decomposes the filtered rPPG signal into multi-scale frequency components.
    Returns the approximation coefficients c_A (dominant low-frequency content).

    The decomposition level is automatically reduced when the signal is short
    to guarantee at least 8 approximation coefficients.

    Args:
        signal  : bandpass-filtered rPPG signal
        wavelet : mother wavelet (default 'db4')
        level   : decomposition depth  (default 3)

    Returns:
        numpy.ndarray: DWT approximation coefficients (cA at requested level)
    """
    signal = np.array(signal, dtype=np.float64)
    # Reduce level if signal too short to keep ≥ 8 approximation coefficients
    actual_level = level
    while actual_level > 1 and len(signal) / (2 ** actual_level) < 8:
        actual_level -= 1
    # Also respect PyWavelets' hard ceiling for this signal length
    max_level    = pywt.dwt_max_level(len(signal), wavelet)
    actual_level = min(actual_level, max_level)

    coeffs = pywt.wavedec(signal, wavelet=wavelet, level=actual_level)
    return np.array(coeffs[0], dtype=np.float64)   # cA = approximation


def preprocess_rppg(signal, fps):
    """
    Full Sync_rPPG preprocessing pipeline for one cheek signal.

    Steps:
      1. Detrend via low-pass subtraction
      2. Butterworth bandpass (0.7–4.0 Hz)
      3. DWT with db4 → approximation coefficients

    This is the canonical input representation for all quality-metric
    computations in this module.

    Args:
        signal : raw green-channel time series (list or ndarray)
        fps    : estimated sampling frequency (Hz)

    Returns:
        numpy.ndarray: DWT approximation coefficients
    """
    signal = np.array(signal, dtype=np.float64)
    if len(signal) < 16:
        return signal.copy()
    detrended = detrend_signal(signal, fps)
    filtered  = bandpass_filter(detrended, fps)
    return apply_dwt(filtered)


def estimate_fps(times):
    """
    Estimate frames per second from a timestamp array.

    Args:
        times: array of frame timestamps (seconds)

    Returns:
        float or None: estimated FPS, None if < 2 timestamps
    """
    if len(times) < 2:
        return None
    duration = times[-1] - times[0]
    if duration <= 0:
        return None
    return (len(times) - 1) / duration


# ── Quality Metrics (all computed on DWT approximation coefficients) ───────────

def compute_correlation(sig1, sig2, fps_est):
    """
    Pearson Correlation Coefficient (PCC) between left and right cheek
    DWT approximation coefficients  (Sync_rPPG Eq. 7).

      PCC = Σ(Xi − X̄)(Yi − Ȳ) / [√Σ(Xi−X̄)² · √Σ(Yi−Ȳ)²]

    Primary deepfake discriminator:
      real  → PCC ≈ 0.72  (coherent bilateral physiology)
      fake  → PCC ≈ 0.08  (generative models cannot synchronise rPPG)

    Args:
        sig1    : raw green-channel signal, left  cheek
        sig2    : raw green-channel signal, right cheek
        fps_est : estimated sampling frequency (Hz)

    Returns:
        float: Pearson correlation coefficient in [-1, 1]
    """
    if len(sig1) < 30 or len(sig2) < 30:
        return 0.0

    c1 = preprocess_rppg(sig1, fps_est)
    c2 = preprocess_rppg(sig2, fps_est)

    min_len = min(len(c1), len(c2))
    if min_len < 4:
        return 0.0
    c1, c2 = c1[:min_len], c2[:min_len]

    std1, std2 = np.std(c1), np.std(c2)
    if std1 < 1e-8 or std2 < 1e-8:
        return 0.0

    corr = np.corrcoef(c1, c2)[0, 1]
    return 0.0 if np.isnan(corr) else float(corr)


def compute_std(signal, fps):
    """
    Standard deviation of DWT approximation coefficients  (Sync_rPPG Eq. 6).

      SD = √[ (1/N) Σ (S_i − S̄)² ]

    Lower SD → stable physiological signal (real).
    Higher SD → irregular fluctuations characteristic of deepfakes.

    Args:
        signal : raw green-channel signal
        fps    : sampling frequency (Hz)

    Returns:
        float: standard deviation of DWT approximation coefficients
    """
    if len(signal) < 16:
        return 0.0
    return float(np.std(preprocess_rppg(signal, fps)))


def compute_mad(signal, fps):
    """
    Mean Absolute Deviation of DWT approximation coefficients
    (Sync_rPPG Eq. 5 — mean-based, not median-based).

      MAD = (1/N) Σ |S_i − S̄|

    Higher MAD → significant variability / lack of physiological coherence
    (characteristic of motion artefacts or synthetic content).

    Args:
        signal : raw green-channel signal
        fps    : sampling frequency (Hz)

    Returns:
        float: mean absolute deviation of DWT approximation coefficients
    """
    if len(signal) < 16:
        return 0.0
    coeffs = preprocess_rppg(signal, fps)
    return float(np.mean(np.abs(coeffs - np.mean(coeffs))))


def compute_psd_and_snr(signal, fps):
    """
    Power Spectral Density (Welch's method) and SNR from DWT coefficients
    (Sync_rPPG Eqs. 3–4).

    PSD  = |F{x(t)}|²  via Welch averaging on DWT approximation coefficients.

    SNR  = 10·log10(P_signal / P_noise)
      P_signal = peak power within the HR band
      P_noise  = mean power in remaining frequencies,
                 excluding ±0.1 Hz around the dominant peak.

    Fake videos lack identifiable physiological frequency components,
    producing flat or anomalous PSD profiles.

    Args:
        signal : raw green-channel signal
        fps    : sampling frequency (Hz)

    Returns:
        tuple: (peak_freq_hz, peak_psd_power, snr_db)
    """
    if len(signal) < 32 or fps is None:
        return 0.0, 0.0, 0.0

    coeffs = preprocess_rppg(signal, fps)
    if len(coeffs) < 4:
        return 0.0, 0.0, 0.0

    # Infer effective sampling rate from DWT downsampling ratio
    downsample = len(signal) / max(len(coeffs), 1)
    dwt_fps    = fps / max(downsample, 1.0)
    dwt_nyq    = dwt_fps / 2.0

    freqs, psd = welch(coeffs, fs=dwt_fps, nperseg=min(len(coeffs), 32))

    # Heart-rate band clipped to frequencies representable at this DWT rate
    hr_high_eff = min(HR_HIGH, dwt_nyq * 0.95)
    pulse_band  = (freqs >= HR_LOW) & (freqs <= hr_high_eff)
    if not np.any(pulse_band):
        pulse_band = freqs > 0              # fallback: all positive frequencies
    if not np.any(pulse_band):
        return 0.0, 0.0, 0.0

    band_psd   = psd[pulse_band]
    band_freqs = freqs[pulse_band]
    peak_idx   = np.argmax(band_psd)
    peak_freq  = float(band_freqs[peak_idx])
    signal_pow = float(band_psd[peak_idx])

    # Noise: mean PSD across all bins, excluding ±0.1 Hz around dominant peak
    excl_mask  = (freqs >= peak_freq - 0.1) & (freqs <= peak_freq + 0.1)
    noise_mask = ~excl_mask & (freqs > 0)
    if np.any(noise_mask):
        noise_pow = float(np.mean(psd[noise_mask])) + 1e-9
    else:
        noise_pow = float(np.mean(psd)) + 1e-9

    snr_db = float(10.0 * np.log10(signal_pow / noise_pow + 1e-9))
    return peak_freq, signal_pow, snr_db


def has_motion_artifact(signal, threshold=12.0):
    """
    Detect motion artefacts in the raw rPPG signal via statistical outlier
    detection on frame-to-frame differences.

    Uses mean absolute deviation (consistent with Sync_rPPG's MAD definition)
    to identify frames with implausibly large colour jumps.

    Args:
        signal    : raw green-channel signal (pre-DWT, pre-filter)
        threshold : MAD multiplier for outlier gate (default 12.0)

    Returns:
        bool: True if a motion artefact is detected
    """
    signal = np.array(signal, dtype=np.float64)
    if len(signal) < 2:
        return False
    diff   = np.abs(np.diff(signal))
    mad    = np.mean(np.abs(diff - np.mean(diff)))  # mean-based MAD
    median = np.median(diff)
    return bool(np.any(diff > median + threshold * mad))
