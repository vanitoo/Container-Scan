from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from pdf_ocr_app.utils.logger import logger


@dataclass
class AlignmentResult:
    aligned_image: Image.Image | None
    homography: np.ndarray | None
    matches: int
    inliers: int
    inlier_ratio: float
    reprojection_error: float | None
    status: str
    message: str
    debug_dir: Path | None = None


class AlignmentService:
    """Geometrically align a scanned form to a reference template."""

    def __init__(self, state):
        self.state = state

    @staticmethod
    def _gray(image: Image.Image) -> np.ndarray:
        array = np.asarray(image.convert("RGB"))
        return cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)

    @staticmethod
    def _scaled(gray: np.ndarray, max_width: int = 1400) -> tuple[np.ndarray, float]:
        scale = min(1.0, max_width / max(1, gray.shape[1]))
        if scale == 1.0:
            return gray, scale
        return (
            cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA),
            scale,
        )

    @staticmethod
    def _full_resolution_homography(
        homography_small: np.ndarray,
        current_scale: float,
        reference_scale: float,
    ) -> np.ndarray:
        current_to_small = np.array(
            [[current_scale, 0.0, 0.0], [0.0, current_scale, 0.0], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        reference_to_small = np.array(
            [[reference_scale, 0.0, 0.0], [0.0, reference_scale, 0.0], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        return np.linalg.inv(reference_to_small) @ homography_small @ current_to_small

    @staticmethod
    def _reprojection_error(
        homography: np.ndarray,
        current_points: np.ndarray,
        reference_points: np.ndarray,
        inlier_mask: np.ndarray,
    ) -> float | None:
        mask = inlier_mask.ravel().astype(bool)
        if not mask.any():
            return None
        projected = cv2.perspectiveTransform(current_points[mask].reshape(-1, 1, 2), homography)
        projected = projected.reshape(-1, 2)
        expected = reference_points[mask]
        return float(np.mean(np.linalg.norm(projected - expected, axis=1)))

    @staticmethod
    def _quality(matches: int, inliers: int, ratio: float, error: float | None) -> tuple[str, str]:
        if error is None or matches < 18 or inliers < 10 or ratio < 0.22 or error > 9.0:
            return "FAILED", "Недостаточно надёжных геометрических совпадений"
        if matches >= 35 and inliers >= 22 and ratio >= 0.45 and error <= 4.0:
            return "GOOD", "Геометрическая привязка надёжная"
        return "WARNING", "Привязка найдена, но требуется ручная проверка"

    def align(
        self,
        reference_image: Image.Image,
        current_image: Image.Image,
        reference_box: tuple[int, int, int, int] | None = None,
        page_number: int | None = None,
    ) -> AlignmentResult:
        reference_gray = self._gray(reference_image)
        current_gray = self._gray(current_image)
        reference_small, reference_scale = self._scaled(reference_gray)
        current_small, current_scale = self._scaled(current_gray)

        orb = cv2.ORB_create(nfeatures=6000, scaleFactor=1.2, nlevels=8)
        ref_keypoints, ref_descriptors = orb.detectAndCompute(reference_small, None)
        cur_keypoints, cur_descriptors = orb.detectAndCompute(current_small, None)
        if ref_descriptors is None or cur_descriptors is None:
            return AlignmentResult(None, None, 0, 0, 0.0, None, "FAILED", "Не найдены ORB-дескрипторы")

        raw_matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(cur_descriptors, ref_descriptors, k=2)
        good_matches = []
        for pair in raw_matches:
            if len(pair) != 2:
                continue
            first, second = pair
            if first.distance < 0.72 * second.distance:
                good_matches.append(first)

        if len(good_matches) < 8:
            return AlignmentResult(
                None, None, len(good_matches), 0, 0.0, None,
                "FAILED", "Слишком мало совпадений для расчёта homography",
            )

        current_points_small = np.float32([cur_keypoints[m.queryIdx].pt for m in good_matches])
        reference_points_small = np.float32([ref_keypoints[m.trainIdx].pt for m in good_matches])
        homography_small, inlier_mask = cv2.findHomography(
            current_points_small,
            reference_points_small,
            cv2.RANSAC,
            4.0,
        )
        if homography_small is None or inlier_mask is None:
            return AlignmentResult(
                None, None, len(good_matches), 0, 0.0, None,
                "FAILED", "RANSAC не смог рассчитать homography",
            )

        inliers = int(inlier_mask.sum())
        inlier_ratio = inliers / max(1, len(good_matches))
        error_small = self._reprojection_error(
            homography_small,
            current_points_small,
            reference_points_small,
            inlier_mask,
        )
        error_full = None if error_small is None else error_small / max(reference_scale, 1e-9)
        status, message = self._quality(len(good_matches), inliers, inlier_ratio, error_full)

        homography_full = self._full_resolution_homography(
            homography_small,
            current_scale,
            reference_scale,
        )
        current_rgb = np.asarray(current_image.convert("RGB"))
        reference_width, reference_height = reference_image.size
        aligned_array = cv2.warpPerspective(
            current_rgb,
            homography_full,
            (reference_width, reference_height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255),
        )
        aligned_image = Image.fromarray(aligned_array)

        debug_dir = self._save_debug(
            reference_image,
            current_image,
            aligned_image,
            reference_small,
            current_small,
            ref_keypoints,
            cur_keypoints,
            good_matches,
            inlier_mask,
            reference_box,
            page_number,
            len(good_matches),
            inliers,
            inlier_ratio,
            error_full,
            status,
        )

        logger.info(
            f"Анализ2: matches={len(good_matches)}, inliers={inliers}, "
            f"ratio={inlier_ratio:.1%}, reprojection={error_full:.2f}px, status={status}"
        )
        return AlignmentResult(
            aligned_image,
            homography_full,
            len(good_matches),
            inliers,
            inlier_ratio,
            error_full,
            status,
            message,
            debug_dir,
        )

    def _save_debug(
        self,
        reference_image: Image.Image,
        current_image: Image.Image,
        aligned_image: Image.Image,
        reference_small: np.ndarray,
        current_small: np.ndarray,
        ref_keypoints,
        cur_keypoints,
        good_matches,
        inlier_mask: np.ndarray,
        reference_box,
        page_number,
        matches: int,
        inliers: int,
        ratio: float,
        error: float | None,
        status: str,
    ) -> Path | None:
        try:
            base = Path(self.state.pdf_path).parent if self.state.pdf_path else Path.cwd()
            suffix = f"page_{page_number:03d}" if page_number is not None else "page"
            debug_dir = base / "debug_alignment" / suffix
            debug_dir.mkdir(parents=True, exist_ok=True)

            current_image.save(debug_dir / "source.jpg", quality=95)
            reference_image.save(debug_dir / "template.jpg", quality=95)
            aligned_image.save(debug_dir / "aligned.jpg", quality=95)

            matches_image = cv2.drawMatches(
                current_small,
                cur_keypoints,
                reference_small,
                ref_keypoints,
                good_matches,
                None,
                matchesMask=inlier_mask.ravel().tolist(),
                flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
            )
            cv2.imwrite(str(debug_dir / "matches.jpg"), matches_image)

            boxed = aligned_image.copy()
            if reference_box:
                ImageDraw.Draw(boxed).rectangle(reference_box, outline="red", width=5)
            boxed.save(debug_dir / "aligned_boxes.jpg", quality=95)

            reprojection = "n/a" if error is None else f"{error:.3f} px"
            (debug_dir / "metrics.txt").write_text(
                "\n".join(
                    [
                        f"status={status}",
                        f"matches={matches}",
                        f"inliers={inliers}",
                        f"inlier_ratio={ratio:.4f}",
                        f"reprojection_error={reprojection}",
                    ]
                ),
                encoding="utf-8",
            )
            return debug_dir
        except Exception as exc:
            logger.warning(f"Не удалось сохранить debug alignment: {exc}")
            return None
