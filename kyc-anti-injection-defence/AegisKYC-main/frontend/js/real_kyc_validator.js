/**
 * Real AI Validation Integration for KYC Complete
 * Uses actual OCR, face detection, and liveness detection
 */

class RealKYCValidator {
    constructor() {
        this.apiBase = '/api/validation';
        this.verificationId = null;
        this.userId = null;
    }

    /**
     * Set verification and user IDs for automatic status tracking
     */
    setContext(verificationId, userId) {
        this.verificationId = verificationId;
        this.userId = userId;
    }

    /**
     * Validate identity document with REAL OCR
     */
    async validateIdentityDocument(base64Image, documentType) {
        try {
            const response = await fetch(`${this.apiBase}/validate-document`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    document_image: base64Image,
                    document_type: documentType.toUpperCase(),
                    verification_id: this.verificationId,
                    user_id: this.userId
                })
            });

            const result = await response.json();
            return result;
        } catch (error) {
            console.error('Document validation error:', error);
            return {
                success: false,
                error: error.message,
                overall_score: 0
            };
        }
    }

    /**
     * Extract PAN details with real OCR
     */
    async extractPANDetails(base64Image) {
        try {
            const response = await fetch(`${this.apiBase}/extract-pan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document_image: base64Image })
            });

            return await response.json();
        } catch (error) {
            console.error('PAN extraction error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Extract Aadhaar details with QR + OCR
     */
    async extractAadhaarDetails(base64Image) {
        try {
            const response = await fetch(`${this.apiBase}/extract-aadhaar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document_image: base64Image })
            });

            return await response.json();
        } catch (error) {
            console.error('Aadhaar extraction error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Extract Passport details with MRZ + OCR
     */
    async extractPassportDetails(base64Image) {
        try {
            const response = await fetch(`${this.apiBase}/extract-passport`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document_image: base64Image })
            });

            return await response.json();
        } catch (error) {
            console.error('Passport extraction error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Extract Driving License details with OCR
     */
    async extractDLDetails(base64Image) {
        try {
            const response = await fetch(`${this.apiBase}/extract-dl`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document_image: base64Image })
            });

            return await response.json();
        } catch (error) {
            console.error('DL extraction error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Verify selfie with REAL face detection
     */
    async verifySelfie(selfieBase64, documentPhotoBase64 = null) {
        try {
            const response = await fetch(`${this.apiBase}/verify-selfie`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    selfie_image: selfieBase64,
                    document_photo: documentPhotoBase64,
                    verification_id: this.verificationId,
                    user_id: this.userId
                })
            });

            return await response.json();
        } catch (error) {
            console.error('Selfie verification error:', error);
            return {
                success: false,
                error: error.message,
                overall_score: 0
            };
        }
    }

    /**
     * Verify video liveness with REAL eye tracking
     */
    async verifyLiveness(videoFrames, expectedGestures = ['blink', 'look_left', 'look_right']) {
        try {
            const response = await fetch(`${this.apiBase}/verify-liveness`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    video_frames: videoFrames,
                    expected_gestures: expectedGestures,
                    verification_id: this.verificationId,
                    user_id: this.userId
                })
            });

            return await response.json();
        } catch (error) {
            console.error('Liveness verification error:', error);
            return {
                success: false,
                error: error.message,
                liveness_score: 0
            };
        }
    }

    /**
     * Cross-verify name across documents
     */
    async crossVerifyName(names) {
        try {
            const response = await fetch(`${this.apiBase}/cross-verify-name`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ names })
            });

            return await response.json();
        } catch (error) {
            console.error('Name verification error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Cross-verify DOB across documents
     */
    async crossVerifyDOB(dobs) {
        try {
            const response = await fetch(`${this.apiBase}/cross-verify-dob`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dobs })
            });

            return await response.json();
        } catch (error) {
            console.error('DOB verification error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Detect image blur
     */
    async detectBlur(imageBase64) {
        try {
            const response = await fetch(`${this.apiBase}/detect-blur`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageBase64 })
            });

            return await response.json();
        } catch (error) {
            console.error('Blur detection error:', error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Display extracted data in UI
     */
    displayExtractedData(containerId, extractedData) {
        const container = document.getElementById(containerId);
        if (!container || !extractedData) return;

        let html = '<div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-4">';
        html += '<h4 class="font-bold text-blue-900 mb-3">📄 Extracted Data (Real OCR):</h4>';
        html += '<div class="grid gap-2 text-sm">';

        for (const [key, value] of Object.entries(extractedData)) {
            if (value && key !== 'extraction_method' && key !== 'document_type') {
                const displayKey = key.replace(/_/g, ' ').toUpperCase();
                html += `
                    <div class="flex justify-between items-center bg-white p-2 rounded">
                        <span class="font-semibold text-slate-700">${displayKey}:</span>
                        <span class="text-slate-900">${value}</span>
                    </div>
                `;
            }
        }

        html += '</div></div>';
        container.innerHTML = html;
    }

    /**
     * Display verification scores
     */
    displayVerificationScores(containerId, scores) {
        const container = document.getElementById(containerId);
        if (!container || !scores) return;

        const getScoreColor = (score) => {
            if (score >= 80) return 'text-green-600';
            if (score >= 60) return 'text-yellow-600';
            return 'text-red-600';
        };

        let html = '<div class="bg-slate-50 border border-slate-200 rounded-lg p-4 mt-4">';
        html += '<h4 class="font-bold text-slate-900 mb-3">📊 Verification Scores:</h4>';
        html += '<div class="space-y-2">';

        for (const [key, value] of Object.entries(scores)) {
            if (typeof value === 'number') {
                const displayKey = key.replace(/_/g, ' ').toUpperCase();
                const colorClass = getScoreColor(value);
                html += `
                    <div class="flex justify-between items-center">
                        <span class="text-sm font-semibold text-slate-700">${displayKey}:</span>
                        <span class="text-lg font-bold ${colorClass}">${value}%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div class="bg-blue-600 h-2 rounded-full transition-all" style="width: ${value}%"></div>
                    </div>
                `;
            }
        }

        html += '</div></div>';
        container.innerHTML = html;
    }
}

// Export for use in kyc_complete.html
window.RealKYCValidator = RealKYCValidator;
