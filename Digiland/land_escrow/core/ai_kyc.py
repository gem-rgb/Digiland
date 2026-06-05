import contextlib
import hashlib
import hmac
import logging
import os
import re
import shutil
import tempfile
import threading
import traceback
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from core.models import AuditLog, KYCProfile

logger = logging.getLogger(__name__)

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    logger.warning("OpenCV (cv2) and NumPy are not installed; AI KYC features will be disabled.")

try:
    import pytesseract
except ImportError:
    pytesseract = None  # type: ignore[assignment]
    logger.warning("pytesseract is not installed; OCR features will be disabled.")

try:
    from deepface import DeepFace
except Exception as exc:  # pragma: no cover - optional dependency
    DeepFace = None
    logger.warning("DeepFace is unavailable; using OpenCV fallbacks: %s", exc)


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-msvideo"}
MAX_FILE_SIZE_MB = 12
MAX_VIDEO_SECONDS = 20
MIN_ID_IMAGE_WIDTH = 800
MIN_ID_IMAGE_HEIGHT = 500
MIN_SELFIE_IMAGE_WIDTH = 640
MIN_SELFIE_IMAGE_HEIGHT = 480
OCR_CONFIDENCE_THRESHOLD = 55.0
BLUR_WARNING_THRESHOLD = 70.0
BLUR_REJECTION_THRESHOLD = 35.0
LIVENESS_THRESHOLD = 0.65
FACE_MATCH_THRESHOLD = 0.85
DUPLICATE_FACE_THRESHOLD = 0.90

FACE_CASCADE = None
EYE_CASCADE = None

if cv2 is not None:
    try:
        FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        EYE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
        if FACE_CASCADE.empty():  # pragma: no cover - environment specific
            logger.warning("OpenCV frontal face cascade could not be loaded")
    except Exception as exc:
        logger.warning("Failed to load OpenCV cascade classifiers: %s", exc)
        FACE_CASCADE = None
        EYE_CASCADE = None


def calculate_cosine_similarity(vec1, vec2):
    vec1 = np.asarray(vec1, dtype=np.float32).flatten()
    vec2 = np.asarray(vec2, dtype=np.float32).flatten()
    dot_product = float(np.dot(vec1, vec2))
    norm1 = float(np.linalg.norm(vec1))
    norm2 = float(np.linalg.norm(vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


def _hash_secret():
    secret = getattr(settings, "KYC_ID_HASH_SALT", None) or getattr(settings, "SECRET_KEY", "digiland-kyc")
    return str(secret).encode("utf-8")


def hash_identifier(identifier):
    if not identifier:
        return None
    return hmac.new(_hash_secret(), str(identifier).encode("utf-8"), hashlib.sha256).hexdigest()


def _normalize_text(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _normalize_id_number(value):
    return re.sub(r"\s+", "", str(value or "").strip()).upper()


def _parse_date_candidate(candidate):
    if not candidate:
        return None

    cleaned = candidate.strip().replace(",", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _is_video_type(content_type, name=""):
    content_type = (content_type or "").lower()
    name = (name or "").lower()
    return (
        content_type in ALLOWED_VIDEO_TYPES
        or content_type.startswith("video/")
        or name.endswith((".mp4", ".mov", ".webm", ".avi", ".mkv"))
    )


def _is_image_type(content_type, name=""):
    content_type = (content_type or "").lower()
    name = (name or "").lower()
    return (
        content_type in ALLOWED_IMAGE_TYPES
        or content_type.startswith("image/")
        or name.endswith((".jpg", ".jpeg", ".png", ".webp"))
    )


@contextlib.contextmanager
def _source_path(source):
    if isinstance(source, (str, os.PathLike)):
        candidate = os.fspath(source)
        if os.path.exists(candidate):
            yield candidate
            return

    path = getattr(source, "path", None)
    if path:
        try:
            if os.path.exists(path):
                yield path
                return
        except Exception:
            pass

    suffix = Path(getattr(source, "name", "upload.bin")).suffix or ".bin"
    temp_path = None
    file_obj = None
    try:
        if hasattr(source, "storage") and getattr(source, "name", None):
            file_obj = source.storage.open(source.name, "rb")
        elif hasattr(source, "open"):
            source.open("rb")
            file_obj = source
        elif hasattr(source, "read"):
            file_obj = source
        else:
            raise ValueError("Unsupported uploaded file object")

        if hasattr(file_obj, "seek"):
            try:
                file_obj.seek(0)
            except Exception:
                pass

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            shutil.copyfileobj(file_obj, temp_file)
            temp_path = temp_file.name

        yield temp_path
    finally:
        try:
            if file_obj is not None and file_obj is not source and hasattr(file_obj, "close"):
                file_obj.close()
        except Exception:
            pass
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                logger.warning("Failed to clean up temp KYC file: %s", temp_path)


def _load_image(path):
    image = cv2.imread(path)
    if image is None:
        raise ValueError(f"Unable to decode image: {path}")
    return image


def _blur_score(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _detect_faces(image):
    if FACE_CASCADE.empty():
        return []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(60, 60),
    )
    return [tuple(map(int, face)) for face in faces]


def _largest_box(boxes):
    if not boxes:
        return None
    return max(boxes, key=lambda box: box[2] * box[3])


def _crop_face(image, box, padding=0.20):
    x, y, w, h = box
    pad_x = int(w * padding)
    pad_y = int(h * padding)
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(image.shape[1], x + w + pad_x)
    y2 = min(image.shape[0], y + h + pad_y)
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return crop


def _frame_indexes(frame_count, limit=6):
    if frame_count <= 0:
        return list(range(limit))
    if frame_count <= limit:
        return list(range(frame_count))
    return sorted({int((frame_count - 1) * i / max(limit - 1, 1)) for i in range(limit)})


def _video_samples(path, limit=6):
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        return []

    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        samples = []
        for frame_index in _frame_indexes(frame_count, limit=limit):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue

            boxes = _detect_faces(frame)
            box = _largest_box(boxes)
            crop = _crop_face(frame, box) if box else frame
            sharpness = _blur_score(crop)
            eye_count = 0
            if box and not EYE_CASCADE.empty():
                gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                eye_count = len(
                    EYE_CASCADE.detectMultiScale(
                        gray_crop,
                        scaleFactor=1.1,
                        minNeighbors=4,
                        minSize=(14, 14),
                    )
                )

            samples.append(
                {
                    "frame_index": frame_index,
                    "frame": frame,
                    "box": box,
                    "crop": crop,
                    "sharpness": sharpness,
                    "eye_count": eye_count,
                }
            )
        return samples
    finally:
        capture.release()


def _best_face_crop_from_image(image):
    boxes = _detect_faces(image)
    box = _largest_box(boxes)
    if not box:
        return None
    return _crop_face(image, box)


def _best_face_crop_from_video(path):
    best_sample = None
    for sample in _video_samples(path):
        if sample["box"] is None:
            continue
        score = sample["sharpness"] + (sample["box"][2] * sample["box"][3]) / 1000.0
        if best_sample is None or score > best_sample["score"]:
            best_sample = {
                "score": score,
                "crop": sample["crop"],
            }
    return best_sample["crop"] if best_sample else None


def _fallback_face_embedding(face_image):
    if face_image is None or face_image.size == 0:
        return None

    gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (64, 128))
    gray = cv2.equalizeHist(gray)

    hog = cv2.HOGDescriptor()
    features = hog.compute(gray)
    if features is None:
        return None

    vector = features.flatten().astype(np.float32)
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        return None
    return vector / norm


def _deepface_embedding(path):
    if DeepFace is None:
        return None

    try:
        result = DeepFace.represent(
            img_path=path,
            model_name="Facenet512",
            enforce_detection=False,
        )
    except Exception as exc:
        logger.info("DeepFace represent failed, falling back to OpenCV embedding: %s", exc)
        return None

    if isinstance(result, dict):
        result = [result]

    for item in result or []:
        if isinstance(item, dict) and item.get("embedding") is not None:
            return np.asarray(item["embedding"], dtype=np.float32)
        if isinstance(item, (list, tuple, np.ndarray)):
            return np.asarray(item, dtype=np.float32)

    return None


def _require_cv2():
    """Return an error dict if cv2/numpy are not available."""
    if cv2 is None or np is None:
        return {
            "error": "OpenCV (cv2) and NumPy are required for AI KYC but are not installed. "
                     "Install opencv-python-headless and numpy to enable this feature.",
        }
    return None


def extract_face_embedding(media_source):
    if _require_cv2():
        return None
    with _source_path(media_source) as path:
        if _is_video_type(getattr(media_source, "content_type", ""), getattr(media_source, "name", path)):
            crop = _best_face_crop_from_video(path)
            if crop is not None:
                embedding = _fallback_face_embedding(crop)
                if embedding is not None:
                    return embedding
            return _deepface_embedding(path)

        image = _load_image(path)
        crop = _best_face_crop_from_image(image)
        if crop is not None:
            embedding = _fallback_face_embedding(crop)
            if embedding is not None:
                return embedding
        return _deepface_embedding(path)


def _extract_id_number(text):
    text = text or ""
    candidates = [
        r"\b\d{7,9}\b",
        r"\b[A-Z]\d{7}[A-Z]?\b",
    ]

    for pattern in candidates:
        match = re.search(pattern, text.upper())
        if match:
            return match.group(0)
    return None


def _extract_full_name(lines):
    name_labels = ("full name", "given names", "given name", "surname", "name")
    for line in lines:
        lower = line.lower()
        if any(label in lower for label in name_labels):
            candidate = re.sub(r"(?i).*(full name|given names?|surname|name)[:\s\-]*", "", line).strip()
            candidate = re.sub(r"[^A-Za-z\s]", "", candidate).strip()
            if len(candidate.split()) >= 2:
                return " ".join(part.capitalize() for part in candidate.split())

    for line in lines:
        candidate = re.sub(r"[^A-Za-z\s]", "", line).strip()
        if 2 <= len(candidate.split()) <= 5 and len(candidate) >= 5:
            return " ".join(part.capitalize() for part in candidate.split())
    return None


def _extract_date_from_lines(lines, keywords):
    for line in lines:
        lower = line.lower()
        if any(keyword in lower for keyword in keywords):
            dates = re.findall(
                r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})",
                line,
            )
            for candidate in dates:
                parsed = _parse_date_candidate(candidate)
                if parsed:
                    return parsed

    return None


def _infer_document_kind(text, doc_type="id_document"):
    if doc_type == "title_deed":
        return "title_deed"

    lower = (text or "").lower()
    if "title deed" in lower or "certificate of title" in lower or "registered proprietor" in lower:
        return "title_deed"
    if "passport" in lower:
        return "passport"
    if "driving licence" in lower or "driving license" in lower:
        return "driver_license"
    if "national identity card" in lower or "identity card" in lower or "id no" in lower or "id number" in lower:
        return "national_id"
    return "unknown"


def _template_keywords(doc_kind):
    return {
        "national_id": [
            "republic of kenya",
            "national identity card",
            "identity card",
            "id no",
            "id number",
        ],
        "passport": [
            "passport",
            "republic of kenya",
            "passport no",
            "passport number",
        ],
        "driver_license": [
            "driving licence",
            "driving license",
            "license no",
            "licence no",
        ],
        "title_deed": [
            "title deed",
            "certificate of title",
            "land registry",
            "registered proprietor",
            "ministry of lands",
        ],
    }.get(doc_kind, [])


def _template_match_score(text, doc_kind):
    keywords = _template_keywords(doc_kind)
    if not keywords:
        return 0.0, []

    lower = (text or "").lower()
    matches = [keyword for keyword in keywords if keyword in lower]
    return len(matches) / float(len(keywords)), matches


def _ocr_text_and_confidence(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    gray = cv2.equalizeHist(gray)
    config = "--oem 3 --psm 6"

    text = pytesseract.image_to_string(gray, config=config)
    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT, config=config)

    confidence_values = []
    for value in data.get("conf", []):
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        if score >= 0:
            confidence_values.append(score)

    confidence = float(sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0
    return text, confidence, gray


def validate_kyc_submission(id_front_file, selfie_file):
    if _require_cv2():
        return {"valid": False, "errors": ["OpenCV is not installed; KYC validation is unavailable."], "warnings": [], "id_front": {}, "selfie": {}}
    errors = []
    warnings = []
    id_meta = _validate_media_file(
        id_front_file,
        allow_video=False,
        min_width=MIN_ID_IMAGE_WIDTH,
        min_height=MIN_ID_IMAGE_HEIGHT,
        max_video_seconds=None,
        label="government ID",
    )
    selfie_meta = _validate_media_file(
        selfie_file,
        allow_video=True,
        min_width=MIN_SELFIE_IMAGE_WIDTH,
        min_height=MIN_SELFIE_IMAGE_HEIGHT,
        max_video_seconds=MAX_VIDEO_SECONDS,
        label="selfie",
    )

    for meta in (id_meta, selfie_meta):
        errors.extend(meta.get("errors", []))
        warnings.extend(meta.get("warnings", []))

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "id_front": id_meta,
        "selfie": selfie_meta,
    }


def _validate_media_file(uploaded_file, *, allow_video, min_width, min_height, max_video_seconds, label):
    if uploaded_file is None:
        return {"valid": False, "errors": [f"{label} is required"], "warnings": [], "media_type": "missing"}

    content_type = getattr(uploaded_file, "content_type", "") or ""
    file_name = getattr(uploaded_file, "name", "")
    file_size = getattr(uploaded_file, "size", 0) or 0
    size_mb = file_size / (1024 * 1024)
    errors = []
    warnings = []

    if size_mb > MAX_FILE_SIZE_MB:
        errors.append(f"{label} is too large. Keep uploads at or below {MAX_FILE_SIZE_MB} MB.")

    media_type = "unknown"
    if _is_image_type(content_type, file_name):
        media_type = "image"
    elif _is_video_type(content_type, file_name):
        media_type = "video"
    else:
        errors.append(f"{label} must be an image" + (" or short video." if allow_video else "."))

    if media_type == "video" and not allow_video:
        errors.append(f"{label} must be an image.")

    metadata = {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "media_type": media_type,
        "content_type": content_type,
        "size_mb": round(size_mb, 2),
        "name": file_name,
    }

    if errors:
        return metadata

    try:
        with _source_path(uploaded_file) as path:
            if media_type == "image":
                image = _load_image(path)
                height, width = image.shape[:2]
                blur = _blur_score(image)
                metadata.update(
                    {
                        "width": width,
                        "height": height,
                        "blur_score": round(blur, 2),
                    }
                )
                if width < min_width or height < min_height:
                    errors.append(
                        f"{label.capitalize()} resolution is too low. Use at least {min_width}x{min_height}."
                    )
                if blur < BLUR_REJECTION_THRESHOLD:
                    errors.append(f"{label.capitalize()} appears too blurry.")
                elif blur < BLUR_WARNING_THRESHOLD:
                    warnings.append(f"{label.capitalize()} looks slightly blurry.")
            else:
                capture = cv2.VideoCapture(path)
                if not capture.isOpened():
                    errors.append(f"{label.capitalize()} video could not be read.")
                else:
                    try:
                        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
                        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                        duration = frame_count / fps if fps else 0
                        metadata.update(
                            {
                                "width": width,
                                "height": height,
                                "duration_seconds": round(duration, 2),
                            }
                        )
                        if width < min_width or height < min_height:
                            errors.append(
                                f"{label.capitalize()} video resolution is too low. Use at least {min_width}x{min_height}."
                            )
                        if max_video_seconds and duration > max_video_seconds:
                            errors.append(
                                f"{label.capitalize()} video is too long. Keep it under {max_video_seconds} seconds."
                            )
                    finally:
                        capture.release()
    except Exception as exc:
        errors.append(f"{label.capitalize()} validation failed: {exc}")

    metadata["errors"] = errors
    metadata["warnings"] = warnings
    metadata["valid"] = not errors
    return metadata


def analyze_document_file(source, *, expected_id_number=None, expected_full_name=None, parcel_number=None, doc_type="id_document"):
    if _require_cv2():
        return {
            "status": "FLAGGED_FOR_REVIEW",
            "is_valid": False,
            "reason": "OpenCV is not installed; document analysis is unavailable.",
            "reasons": ["OpenCV is not installed."],
            "warnings": [],
            "tamper_flags": [],
            "ocr_confidence": 0.0,
            "blur_score": 0.0,
            "edge_density": 0.0,
            "template_score": 0.0,
            "template_matches": [],
            "document_kind": "unknown",
            "raw_text": "",
            "extracted": {},
            "id_number_hash": None,
        }
    with _source_path(source) as path:
        image = _load_image(path)
        height, width = image.shape[:2]
        blur = _blur_score(image)
        text, ocr_confidence, gray = _ocr_text_and_confidence(image)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        document_kind = _infer_document_kind(text, doc_type=doc_type)
        template_score, template_matches = _template_match_score(text, document_kind)
        extracted_id_number = _extract_id_number(text)
        extracted_full_name = _extract_full_name(lines)
        date_of_birth = _extract_date_from_lines(lines, ["date of birth", "dob", "birth date", "born"])
        expiry_date = _extract_date_from_lines(lines, ["expiry date", "expiry", "expires", "valid until", "expiration date"])

        reasons = []
        warnings = []
        tamper_flags = []

        if width < MIN_ID_IMAGE_WIDTH or height < MIN_ID_IMAGE_HEIGHT:
            reasons.append(f"Image resolution is too low for reliable verification ({width}x{height}).")

        if blur < BLUR_REJECTION_THRESHOLD:
            reasons.append("Document image is too blurry.")
        elif blur < BLUR_WARNING_THRESHOLD:
            warnings.append("Document image is slightly blurry.")

        if ocr_confidence < OCR_CONFIDENCE_THRESHOLD:
            reasons.append("OCR confidence is below the verification threshold.")
        elif ocr_confidence < OCR_CONFIDENCE_THRESHOLD + 8:
            warnings.append("OCR confidence is borderline and may need manual review.")

        if template_score < 0.40:
            reasons.append("Document template does not match a supported government format.")
        elif template_score < 0.70:
            warnings.append("Document template match is weak.")

        if not lines:
            reasons.append("No readable text was extracted from the document.")

        if expected_id_number:
            if not extracted_id_number:
                reasons.append("Could not extract the ID number from the document.")
            elif _normalize_id_number(extracted_id_number) != _normalize_id_number(expected_id_number):
                reasons.append("OCR ID number does not match the registered identity.")

        if expected_full_name and extracted_full_name:
            expected_name = _normalize_text(expected_full_name)
            extracted_name = _normalize_text(extracted_full_name)
            if expected_name and extracted_name and expected_name not in extracted_name and extracted_name not in expected_name:
                warnings.append("Document name does not closely match the account name.")

        if parcel_number and _normalize_text(parcel_number) not in _normalize_text(text):
            reasons.append("Parcel number was not found on the title deed.")

        if document_kind in {"passport", "driver_license"} and not expiry_date:
            reasons.append("Expiry date is missing from the document.")

        if expiry_date and expiry_date < timezone.localdate():
            reasons.append("Document is expired.")

        edge_density = float(np.count_nonzero(cv2.Canny(gray, 80, 180)) / gray.size)
        if edge_density < 0.008:
            tamper_flags.append("Low edge detail detected")

        if not extracted_full_name:
            warnings.append("Full name could not be confidently extracted.")

        status = "APPROVED"
        reason = "Document verification passed."

        if reasons:
            status = "REJECTED"
            reason = reasons[0]
        elif warnings:
            status = "FLAGGED_FOR_REVIEW"
            reason = warnings[0]

        id_number_hash = hash_identifier(extracted_id_number or expected_id_number)

        return {
            "status": status,
            "is_valid": status == "APPROVED",
            "reason": reason,
            "reasons": reasons,
            "warnings": warnings,
            "tamper_flags": tamper_flags,
            "ocr_confidence": round(float(ocr_confidence), 2),
            "blur_score": round(float(blur), 2),
            "edge_density": round(edge_density, 4),
            "template_score": round(float(template_score), 2),
            "template_matches": template_matches,
            "document_kind": document_kind,
            "raw_text": text,
            "extracted": {
                "id_number": extracted_id_number,
                "full_name": extracted_full_name,
                "date_of_birth": date_of_birth,
                "expiry_date": expiry_date,
            },
            "id_number_hash": id_number_hash,
        }


def extract_id_data(image_path):
    result = analyze_document_file(image_path, doc_type="id_document")
    return {
        "raw_text": result.get("raw_text", ""),
        "id_number": result.get("extracted", {}).get("id_number"),
        "full_name": result.get("extracted", {}).get("full_name"),
        "date_of_birth": result.get("extracted", {}).get("date_of_birth"),
        "expiry_date": result.get("extracted", {}).get("expiry_date"),
        "ocr_confidence": result.get("ocr_confidence", 0.0),
        "document_kind": result.get("document_kind", "unknown"),
        "id_number_hash": result.get("id_number_hash"),
    }


def analyse_liveness_file(source):
    if _require_cv2():
        return {"score": 0.0, "is_live": False, "reason": "OpenCV is not installed; liveness analysis unavailable.", "media_type": "unknown", "frames_scanned": 0, "details": {}}
    with _source_path(source) as path:
        media_name = getattr(source, "name", path)
        content_type = getattr(source, "content_type", "")
        if _is_video_type(content_type, media_name):
            samples = _video_samples(path)
            face_samples = [sample for sample in samples if sample.get("box") is not None]
            if not samples:
                return {
                    "score": 0.0,
                    "is_live": False,
                    "reason": "Unable to read selfie video.",
                    "media_type": "video",
                    "frames_scanned": 0,
                    "details": {},
                }

            if not face_samples:
                return {
                    "score": 0.0,
                    "is_live": False,
                    "reason": "No face was detected in the selfie video.",
                    "media_type": "video",
                    "frames_scanned": len(samples),
                    "details": {"frames_with_face": 0},
                }

            detection_rate = len(face_samples) / float(len(samples))
            sharpness_values = [sample["sharpness"] for sample in face_samples]
            eye_counts = [sample["eye_count"] for sample in face_samples]
            centers = [
                (sample["box"][0] + sample["box"][2] / 2.0, sample["box"][1] + sample["box"][3] / 2.0)
                for sample in face_samples
            ]

            motion_score = 0.0
            if len(face_samples) > 1:
                frame_diffs = []
                previous = None
                for sample in face_samples:
                    crop = sample["crop"]
                    if crop is None:
                        continue
                    resized = cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (64, 64))
                    if previous is not None:
                        frame_diffs.append(float(np.mean(cv2.absdiff(previous, resized)) / 255.0))
                    previous = resized
                if frame_diffs:
                    motion_score = min(1.0, float(sum(frame_diffs) / len(frame_diffs)))

            blink_bonus = 0.0
            if max(eye_counts) >= 2 and min(eye_counts) <= 1:
                blink_bonus = 0.15

            if len(centers) > 1:
                center_moves = []
                for index in range(1, len(centers)):
                    prev_x, prev_y = centers[index - 1]
                    curr_x, curr_y = centers[index]
                    center_moves.append(((curr_x - prev_x) ** 2 + (curr_y - prev_y) ** 2) ** 0.5)
                motion_score = min(1.0, motion_score + (sum(center_moves) / len(center_moves) / 120.0))

            sharpness_score = min(1.0, float(sum(sharpness_values) / len(sharpness_values) / 100.0))
            score = 0.35 + (0.30 * detection_rate) + (0.20 * motion_score) + blink_bonus + (0.10 * sharpness_score)
            score = max(0.0, min(1.0, score))

            details = {
                "detection_rate": round(detection_rate, 3),
                "motion_score": round(motion_score, 3),
                "sharpness_score": round(sharpness_score, 3),
                "eye_counts": eye_counts,
            }
            return {
                "score": round(score, 3),
                "is_live": score >= LIVENESS_THRESHOLD,
                "reason": "Selfie video passed liveness checks."
                if score >= LIVENESS_THRESHOLD
                else "Selfie video liveness confidence is below threshold.",
                "media_type": "video",
                "frames_scanned": len(samples),
                "details": details,
            }

        image = _load_image(path)
        boxes = _detect_faces(image)
        box = _largest_box(boxes)
        if not box:
            return {
                "score": 0.0,
                "is_live": False,
                "reason": "No face was detected in the selfie image.",
                "media_type": "image",
                "frames_scanned": 1,
                "details": {},
            }

        crop = _crop_face(image, box)
        blur = _blur_score(crop)
        face_ratio = (box[2] * box[3]) / float(image.shape[0] * image.shape[1])
        eye_count = 0
        if not EYE_CASCADE.empty():
            gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            eye_count = len(
                EYE_CASCADE.detectMultiScale(
                    gray_crop,
                    scaleFactor=1.1,
                    minNeighbors=4,
                    minSize=(14, 14),
                )
            )

        score = 0.45
        if blur >= BLUR_WARNING_THRESHOLD:
            score += 0.18
        elif blur >= BLUR_REJECTION_THRESHOLD:
            score += 0.08
        if 0.08 <= face_ratio <= 0.60:
            score += 0.10
        if eye_count >= 1:
            score += 0.10
        if blur > 120:
            score += 0.07
        if blur < BLUR_REJECTION_THRESHOLD:
            score -= 0.20

        score = max(0.0, min(1.0, score))
        return {
            "score": round(score, 3),
            "is_live": score >= LIVENESS_THRESHOLD,
            "reason": "Selfie image passed liveness checks."
            if score >= LIVENESS_THRESHOLD
            else "Selfie image liveness confidence is below threshold.",
            "media_type": "image",
            "frames_scanned": 1,
            "details": {
                "blur_score": round(float(blur), 2),
                "face_ratio": round(float(face_ratio), 3),
                "eye_count": eye_count,
            },
        }


def detect_liveness(media_source):
    return analyse_liveness_file(media_source).get("score", 0.0)


def _update_profile_audit(profile, status, reason, metadata):
    audit_log = dict(profile.audit_log or {})
    audit_log["status"] = status
    audit_log["reason"] = reason
    audit_log["updated_at"] = timezone.now().isoformat()
    audit_log["metadata"] = metadata or {}

    history = list(audit_log.get("history", []))
    history.append(
        {
            "timestamp": timezone.now().isoformat(),
            "status": status,
            "reason": reason,
            "metadata": metadata or {},
        }
    )
    audit_log["history"] = history[-20:]

    if status == "LOCKED":
        audit_log["fraud_reason"] = reason

    profile.audit_log = audit_log


def _apply_final_status(profile, status, reason, metadata=None, *, lock_user=False):
    metadata = metadata or {}
    profile.status = status
    _update_profile_audit(profile, status, reason, metadata)

    extracted = metadata.get("extracted", {})
    if extracted:
        if extracted.get("id_number"):
            profile.id_number = extracted.get("id_number")
        if extracted.get("full_name"):
            profile.full_name = extracted.get("full_name")
        if extracted.get("date_of_birth"):
            profile.date_of_birth = extracted.get("date_of_birth")
        if extracted.get("expiry_date"):
            profile.expiry_date = extracted.get("expiry_date")

    if metadata.get("id_number_hash"):
        profile.id_number_hash = metadata.get("id_number_hash")
    if metadata.get("face_embedding") is not None:
        profile.face_embedding = metadata.get("face_embedding")
    if metadata.get("liveness_score") is not None:
        profile.liveness_score = metadata.get("liveness_score")

    profile.save()

    AuditLog.objects.create(
        user=profile.user,
        action=f"KYC {status.lower()} for {profile.user.email}",
        metadata={
            "kyc_profile_id": str(profile.id),
            "status": status,
            "reason": reason,
            "metadata": metadata,
        },
    )

    if status == "APPROVED":
        profile.user.is_identity_verified = True
        profile.user.is_active = True
    elif lock_user or status == "LOCKED":
        profile.user.is_identity_verified = False
        profile.user.is_active = False
    else:
        profile.user.is_identity_verified = False

    profile.user.save(update_fields=["is_active", "is_identity_verified"])


def _duplicate_id_exists(profile, id_hash, fallback_id_number=None):
    queryset = KYCProfile.objects.exclude(id=profile.id)
    if id_hash:
        if queryset.filter(id_number_hash=id_hash).exists():
            return True
    if fallback_id_number:
        return queryset.filter(id_number=_normalize_id_number(fallback_id_number)).exists()
    return False


def _duplicate_face_exists(profile, embedding):
    if embedding is None or embedding.size == 0:
        return False

    for other_profile in KYCProfile.objects.exclude(id=profile.id).exclude(face_embedding__isnull=True):
        try:
            other_embedding = np.asarray(other_profile.face_embedding, dtype=np.float32).flatten()
        except Exception:
            continue
        if other_embedding.size == 0 or other_embedding.size != embedding.size:
            continue
        similarity = calculate_cosine_similarity(embedding, other_embedding)
        if similarity >= DUPLICATE_FACE_THRESHOLD:
            return True
    return False


def process_kyc_background(kyc_profile_id):
    close_old_connections()
    profile = None
    try:
        profile = KYCProfile.objects.select_related("user").get(id=kyc_profile_id)
        user = profile.user

        with _source_path(profile.id_front_image) as id_path:
            with _source_path(profile.selfie_image) as selfie_path:
                preflight = validate_kyc_submission(profile.id_front_image, profile.selfie_image)
                if not preflight["valid"]:
                    _apply_final_status(
                        profile,
                        "REJECTED",
                        preflight["errors"][0] if preflight["errors"] else "KYC uploads failed validation.",
                        metadata={
                            "validation": preflight,
                        },
                    )
                    return

                doc_result = analyze_document_file(
                    id_path,
                    expected_id_number=user.id_number,
                    expected_full_name=f"{user.first_name} {user.last_name}".strip() or None,
                    doc_type="id_document",
                )

                selfie_result = analyse_liveness_file(selfie_path)
                face_embedding = extract_face_embedding(selfie_path)
                document_face_embedding = extract_face_embedding(id_path)
                candidate_id_number = doc_result.get("extracted", {}).get("id_number") or user.id_number
                id_hash = doc_result.get("id_number_hash") or hash_identifier(candidate_id_number)

                if _duplicate_id_exists(profile, id_hash, candidate_id_number):
                    _apply_final_status(
                        profile,
                        "LOCKED",
                        "Duplicate identity detected.",
                        metadata={
                            "id_number_hash": id_hash,
                            "candidate_id_number_tail": str(candidate_id_number)[-4:],
                            "document_result": {
                                "status": doc_result.get("status"),
                                "ocr_confidence": doc_result.get("ocr_confidence"),
                            },
                        },
                        lock_user=True,
                    )
                    return

                if doc_result.get("status") == "REJECTED":
                    _apply_final_status(
                        profile,
                        "REJECTED",
                        doc_result.get("reason", "Document verification failed."),
                        metadata={"document_result": doc_result, "id_number_hash": id_hash},
                    )
                    return

                if selfie_result.get("is_live") is False:
                    _apply_final_status(
                        profile,
                        "REJECTED",
                        selfie_result.get("reason", "Liveness check failed."),
                        metadata={
                            "liveness_result": selfie_result,
                            "id_number_hash": id_hash,
                            "document_result": doc_result,
                        },
                    )
                    return

                if face_embedding is None or document_face_embedding is None:
                    _apply_final_status(
                        profile,
                        "FLAGGED_FOR_REVIEW",
                        "Face analysis could not be completed.",
                        metadata={
                            "document_result": doc_result,
                            "liveness_result": selfie_result,
                            "id_number_hash": id_hash,
                        },
                    )
                    return

                face_similarity = calculate_cosine_similarity(face_embedding, document_face_embedding)
                if face_similarity < FACE_MATCH_THRESHOLD:
                    _apply_final_status(
                        profile,
                        "REJECTED",
                        "Face mismatch between the selfie and the document photo.",
                        metadata={
                            "face_similarity": round(float(face_similarity), 3),
                            "document_result": doc_result,
                            "liveness_result": selfie_result,
                            "id_number_hash": id_hash,
                        },
                    )
                    return

                profile.face_embedding = face_embedding.tolist()
                profile.liveness_score = selfie_result.get("score", 0.0)
                profile.id_number = doc_result.get("extracted", {}).get("id_number") or profile.id_number
                profile.id_number_hash = id_hash
                profile.full_name = doc_result.get("extracted", {}).get("full_name") or profile.full_name
                profile.date_of_birth = doc_result.get("extracted", {}).get("date_of_birth") or profile.date_of_birth
                profile.expiry_date = doc_result.get("extracted", {}).get("expiry_date") or profile.expiry_date

                if _duplicate_face_exists(profile, face_embedding):
                    _apply_final_status(
                        profile,
                        "LOCKED",
                        "Duplicate face detected.",
                        metadata={
                            "id_number_hash": id_hash,
                            "face_similarity_threshold": DUPLICATE_FACE_THRESHOLD,
                            "document_result": doc_result,
                            "liveness_result": selfie_result,
                        },
                        lock_user=True,
                    )
                    return

                final_status = "APPROVED"
                final_reason = "KYC verification passed."
                if doc_result.get("status") == "FLAGGED_FOR_REVIEW" or selfie_result.get("score", 0.0) < (LIVENESS_THRESHOLD + 0.08):
                    final_status = "FLAGGED_FOR_REVIEW"
                    final_reason = "KYC requires manual review."

                _apply_final_status(
                    profile,
                    final_status,
                    final_reason,
                    metadata={
                        "document_result": doc_result,
                        "liveness_result": selfie_result,
                        "face_similarity": round(float(face_similarity), 3),
                        "id_number_hash": id_hash,
                        "face_embedding": face_embedding.tolist(),
                        "extracted": doc_result.get("extracted", {}),
                    },
                )
                return
    except KYCProfile.DoesNotExist:
        logger.warning("KYC profile %s not found", kyc_profile_id)
    except Exception as exc:
        logger.exception("Unexpected error during KYC processing: %s", exc)
        if profile is not None:
            _apply_final_status(
                profile,
                "FLAGGED_FOR_REVIEW",
                "KYC could not be completed automatically.",
                metadata={
                    "system_error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
    finally:
        close_old_connections()


def start_kyc_verification(kyc_profile_id):
    thread = threading.Thread(target=process_kyc_background, args=(kyc_profile_id,))
    thread.daemon = True
    thread.start()
