from __future__ import annotations

import cv2
import numpy as np


def prepare_tesseract_image(image, **kwargs):
    """Подготовка изображения для Tesseract."""
    options = kwargs.get("options")
    order = kwargs.get("order")
    if options is not None and order is not None:
        return _apply_configurable_pipeline(image, options, order)

    use_grayscale = kwargs.get("use_grayscale", True)
    use_median_blur = kwargs.get("use_median_blur", True)
    use_thresholding = kwargs.get("use_thresholding", False)
    use_clahe = kwargs.get("use_clahe", True)
    use_resize = kwargs.get("use_resize", True)
    use_deskew = kwargs.get("use_deskew", False)
    use_noise_removal = kwargs.get("use_noise_removal", True)
    use_morphological_ops = kwargs.get("use_morphological_ops", False)

    if use_grayscale:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    if use_median_blur:
        image = cv2.medianBlur(image, 3)

    if use_thresholding:
        _, image = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if use_clahe:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        image = clahe.apply(image)

    if use_resize:
        image = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    if use_deskew:
        coords = np.column_stack(np.where(image > 0))
        if len(coords) > 0:
            angle = cv2.minAreaRect(coords)[-1]
            angle = -(90 + angle) if angle < -45 else -angle
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            image = cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    if use_noise_removal:
        image = cv2.medianBlur(image, 3)

    if use_morphological_ops:
        kernel = np.ones((1, 1), np.uint8)
        image = cv2.dilate(image, kernel, iterations=1)
        image = cv2.erode(image, kernel, iterations=1)

    return image


def _odd_kernel(value, minimum=1):
    value = max(minimum, int(value))
    return value if value % 2 else value + 1


def _ensure_gray(image):
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image


def _apply_configurable_pipeline(image, options, order):
    """Apply enabled OCR operations in the exact order selected in the UI."""
    result = image.copy()
    for name in order:
        config = options.get(name, {})
        if not config.get("enabled", False):
            continue
        if name == "grayscale":
            result = _ensure_gray(result)
        elif name == "median_blur":
            result = cv2.medianBlur(result, _odd_kernel(config.get("kernel", 3), 3))
        elif name == "clahe":
            gray = _ensure_gray(result)
            grid = max(1, int(config.get("grid_size", 8)))
            result = cv2.createCLAHE(
                clipLimit=max(0.1, float(config.get("clip_limit", 2.0))),
                tileGridSize=(grid, grid),
            ).apply(gray)
        elif name == "thresholding":
            gray = _ensure_gray(result)
            _, result = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        elif name == "resize":
            factor = max(0.25, float(config.get("factor", 2.0)))
            result = cv2.resize(result, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        elif name == "deskew":
            gray = _ensure_gray(result)
            coords = np.column_stack(np.where(gray < 250))
            if len(coords) > 10:
                angle = cv2.minAreaRect(coords)[-1]
                angle = -(90 + angle) if angle < -45 else -angle
                h, w = result.shape[:2]
                matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
                result = cv2.warpAffine(result, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        elif name == "noise_removal":
            result = cv2.medianBlur(result, _odd_kernel(config.get("kernel", 3), 3))
        elif name == "morphological_ops":
            size = max(1, int(config.get("kernel", 1)))
            iterations = max(1, int(config.get("iterations", 1)))
            kernel = np.ones((size, size), np.uint8)
            result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel, iterations=iterations)
    return result
