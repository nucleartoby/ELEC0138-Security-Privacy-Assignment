"""
OCR wrapper: integrates with pytesseract or paddleocr when available.
Provides: extract_text(cv2_image) -> { raw_text, fields, confidence }
"""
import cv2
import numpy as np

class OCRModel:
    def __init__(self):
        self.use_paddle = False
        try:
            from paddleocr import PaddleOCR
            self.ocr = PaddleOCR(use_angle_cls=True, lang='en')
            self.use_paddle = True
        except Exception:
            try:
                import pytesseract
                self.ocr = pytesseract
                self.use_paddle = False
            except Exception:
                self.ocr = None

    def extract_text(self, image_cv2):
        try:
            if self.use_paddle:
                result = self.ocr.ocr(image_cv2, cls=True)
                lines = [line[1][0] for line in result[0]] if result and len(result)>0 else []
                raw = "\n".join(lines)
                return {'raw_text': raw, 'lines': lines, 'confidence': None}
            else:
                # Use pytesseract if available
                try:
                    import pytesseract
                    gray = cv2.cvtColor(image_cv2, cv2.COLOR_BGR2GRAY) if len(image_cv2.shape)==3 else image_cv2
                    text = pytesseract.image_to_string(gray, config='--psm 6')
                    return {'raw_text': text, 'lines': text.splitlines(), 'confidence': None}
                except Exception as e:
                    return {'raw_text': '', 'lines': [], 'confidence': None, 'error': str(e)}
        except Exception as e:
            return {'raw_text': '', 'lines': [], 'confidence': None, 'error': str(e)}
