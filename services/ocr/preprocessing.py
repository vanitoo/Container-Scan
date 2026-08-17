from __future__ import annotations

import cv2
import numpy as np


def prepare_tesseract_image(image, **kwargs):
    """Подготовка изображения для Tesseract."""
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
