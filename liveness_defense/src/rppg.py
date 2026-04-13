"""
rPPG (Remote Photoplethysmography) Signal Processing Module

This module provides functions for processing video-based heart rate signals
extracted from skin regions. It includes filtering, correlation analysis,
and motion artifact detection for passive liveness verification.
"""

from scipy.signal import welch, detrend, butter, filtfilt
from scipy.stats import median_abs_deviation
import numpy as np


def detrend_signal(signal, window_size=15):
    """
    Remove linear trend from signal to improve analysis.

    Args:
        signal: Input signal array
        window_size: Window size for detrending (unused in current implementation)

    Returns:
        numpy.ndarray: Detrended signal
    """
    signal = np.array(signal, dtype=np.float64)
    if len(signal) < 2:
        return signal
    return detrend(signal, type='linear')  # removes linear trend cleanly


def bandpass_filter(signal, fps, low=0.7, high=4.0):
    """
    Apply bandpass filter to isolate heart rate frequency band (0.7-4.0 Hz).

    Args:
        signal: Input signal array
        fps: Sampling frequency in Hz
        low: Low cutoff frequency (default: 0.7 Hz)
        high: High cutoff frequency (default: 4.0 Hz)

    Returns:
        numpy.ndarray: Bandpass filtered signal
    """
    signal = detrend_signal(signal)
    if fps is None or fps < 2 * high:  # can't filter above Nyquist
        return signal
    nyq = fps / 2
    b, a = butter(2, [low / nyq, high / nyq], btype='band')
    return filtfilt(b, a, signal, method='gust')  # gust avoids edge issues


def compute_correlation(sig1, sig2, fps_est):
    """
    Compute correlation between two filtered signals.

    Args:
        sig1: First signal array
        sig2: Second signal array
        fps_est: Estimated sampling frequency

    Returns:
        float: Correlation coefficient (-1 to 1)
    """
    if len(sig1) < 30 or len(sig2) < 30:
        return 0.0

    sig1 = bandpass_filter(sig1, fps_est)
    sig2 = bandpass_filter(sig2, fps_est)

    std1, std2 = np.std(sig1), np.std(sig2)
    if std1 < 1e-6 or std2 < 1e-6:
        return 0.0

    corr = np.corrcoef(sig1, sig2)[0, 1]
    return 0.0 if np.isnan(corr) else float(corr)


def estimate_fps(times):
    """
    Estimate frames per second from timestamp array.

    Args:
        times: Array of timestamps

    Returns:
        float or None: Estimated FPS, None if insufficient data
    """
    if len(times) < 2:
        return None
    duration = times[-1] - times[0]
    if duration <= 0:
        return None
    return (len(times) - 1) / duration


def compute_std(signal, fps):
    """
    Compute standard deviation of bandpass filtered signal.

    Args:
        signal: Input signal array
        fps: Sampling frequency

    Returns:
        float: Standard deviation
    """
    if len(signal) < 2:
        return 0.0
    return float(np.std(bandpass_filter(signal, fps)))


def compute_mad(signal, fps):
    """
    Compute median absolute deviation of bandpass filtered signal.

    Args:
        signal: Input signal array
        fps: Sampling frequency

    Returns:
        float: Median absolute deviation
    """
    if len(signal) < 2:
        return 0.0
    return float(median_abs_deviation(bandpass_filter(signal, fps)))


def compute_psd_and_snr(signal, fps):
    """
    Compute power spectral density and signal-to-noise ratio in heart rate band.

    Args:
        signal: Input signal array
        fps: Sampling frequency

    Returns:
        tuple: (peak_frequency, peak_power, snr_db)
    """
    if len(signal) < 32 or fps is None:
        return 0.0, 0.0, 0.0

    filtered = bandpass_filter(signal, fps)
    freqs, psd = welch(filtered, fs=fps, nperseg=min(len(filtered), 64))

    pulse_band = (freqs >= 0.7) & (freqs <= 4.0)
    if not np.any(pulse_band):
        return 0.0, 0.0, 0.0

    band_psd = psd[pulse_band]
    band_freqs = freqs[pulse_band]
    peak_idx = np.argmax(band_psd)
    signal_power = band_psd[peak_idx]
    noise_power = np.sum(psd) - signal_power + 1e-6

    return float(band_freqs[peak_idx]), float(signal_power), float(10 * np.log10(signal_power / noise_power))


def has_motion_artifact(signal, threshold=8.0):
    """
    Detect motion artifacts in signal using statistical outlier detection.

    Args:
        signal: Input signal array
        threshold: MAD multiplier for outlier detection (default: 8.0)

    Returns:
        bool: True if motion artifact detected
    """
    signal = np.array(signal, dtype=np.float64)
    if len(signal) < 2:
        return False
    diff = np.abs(np.diff(signal))
    mad = median_abs_deviation(diff)
    median = np.median(diff)
    return bool(np.any(diff > median + threshold * mad))
    return float(median_abs_deviation(bandpass_filter(signal, fps)))

def compute_psd_and_snr(signal, fps):
    """
    Compute power spectral density and signal-to-noise ratio in heart rate band.

    Args:
        signal: Input signal array
        fps: Sampling frequency

    Returns:
        tuple: (peak_frequency, peak_power, snr_db)
    """
    if len(signal) < 32 or fps is None:
        return 0.0, 0.0, 0.0
    
    filtered = bandpass_filter(signal, fps)
    freqs, psd = welch(filtered, fs=fps, nperseg=min(len(filtered), 64))
    
    pulse_band = (freqs >= 0.7) & (freqs <= 4.0)
    if not np.any(pulse_band):
        return 0.0, 0.0, 0.0

    band_psd = psd[pulse_band]
    band_freqs = freqs[pulse_band]
    peak_idx = np.argmax(band_psd)
    signal_power = band_psd[peak_idx]
    noise_power = np.sum(psd) - signal_power + 1e-6

    return float(band_freqs[peak_idx]), float(signal_power), float( 10 * np.log10(signal_power / noise_power))

def has_motion_artifact(signal, threshold=8.0):
    """
    Detect motion artifacts in signal using statistical outlier detection.

    Args:
        signal: Input signal array
        threshold: MAD multiplier for outlier detection (default: 8.0)

    Returns:
        bool: True if motion artifact detected
    """
    signal = np.array(signal, dtype=np.float64)
    if len(signal) < 2:
        return False
    diff = np.abs(np.diff(signal))
    mad = median_abs_deviation(diff)
    median = np.median(diff)
    return bool(np.any(diff > median + threshold * mad))