from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import platform
import time

try:
    import cv2
    CV2_IMPORT_ERROR = None
except ImportError as error:
    cv2 = None
    CV2_IMPORT_ERROR = error

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
except Exception as error:
    pyzbar_decode = None
    PYZBAR_IMPORT_ERROR = error
else:
    PYZBAR_IMPORT_ERROR = None


class CameraScannerError(RuntimeError):
    """Raised when the camera barcode scanner cannot start or decode."""


@dataclass(frozen=True, slots=True)
class CameraScanResult:
    value: str
    symbology: str


class CameraScanner:
    """Opens a webcam feed and decodes one or more barcodes."""

    def __init__(self, camera_index: int = 0, window_title: str = "Barcode Camera Scanner") -> None:
        self.camera_index = camera_index
        self.window_title = window_title

    def scan_barcode(self) -> CameraScanResult | None:
        first_result: CameraScanResult | None = None

        def stop_after_first_detection(scan_result: CameraScanResult) -> bool:
            nonlocal first_result
            first_result = scan_result
            return False

        self.scan_session(on_detect=stop_after_first_detection)
        return first_result

    def scan_session(
        self,
        on_detect: Callable[[CameraScanResult], bool | None] | None = None,
        cooldown_seconds: float = 1.2,
    ) -> int:
        self._ensure_dependencies()

        capture = self._open_camera()
        if capture is None:
            raise CameraScannerError(
                "Unable to open the camera. Check that a webcam is connected and not in use by another app."
            )

        cv2.namedWindow(self.window_title, cv2.WINDOW_NORMAL)

        active_values: set[str] = set()
        recent_detection_times: dict[str, float] = {}
        current_scan_count = 0

        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break

                results = self._process_frame(frame)
                count_increment, continue_scanning = self._handle_scan_results(
                    results,
                    active_values,
                    recent_detection_times,
                    cooldown_seconds,
                    on_detect,
                )
                current_scan_count += count_increment

                self._draw_overlay(frame, current_scan_count)
                cv2.imshow(self.window_title, frame)

                key = cv2.waitKey(1) & 0xFF
                if key == 27 or key == ord("q"):
                    break

                if not continue_scanning:
                    break
        finally:
            capture.release()
            cv2.destroyWindow(self.window_title)

        return current_scan_count

    def _draw_overlay(self, frame, scan_count: int) -> None:
        cv2.putText(
            frame,
            "Press Q or Esc to Exit",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
        )
        cv2.putText(
            frame,
            f"Items Scanned: {scan_count}",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 0, 0),
            2,
        )

    def _process_frame(self, frame) -> list[CameraScanResult]:
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        decoded_objects = pyzbar_decode(gray_frame)

        results = []
        for obj in decoded_objects:
            barcode_data = obj.data.decode("utf-8")
            barcode_type = obj.type
            results.append(CameraScanResult(value=barcode_data, symbology=barcode_type))

            x, y, w, h = obj.rect
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)

            text = f"{barcode_data} ({barcode_type})"
            cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        return results

    def _handle_scan_results(
        self,
        results: list[CameraScanResult],
        active_values: set[str],
        recent_detection_times: dict[str, float],
        cooldown_seconds: float,
        on_detect: Callable[[CameraScanResult], bool | None] | None,
    ) -> tuple[int, bool]:
        now = time.time()
        current_scan_count = 0
        visible_values = {result.value for result in results}

        for result in results:
            if not result.value:
                continue

            if result.value in active_values:
                continue
            if now - recent_detection_times.get(result.value, 0.0) < cooldown_seconds:
                continue

            active_values.add(result.value)
            recent_detection_times[result.value] = now
            current_scan_count += 1

            if on_detect is not None:
                continue_scanning = on_detect(result)
                if continue_scanning is False:
                    active_values.intersection_update(visible_values)
                    return current_scan_count, False

        active_values.intersection_update(visible_values)
        return current_scan_count, True

    def _ensure_dependencies(self) -> None:
        if cv2 is None or pyzbar_decode is None:
            from tkinter import messagebox
            import subprocess
            import sys
            
            messagebox.showinfo(
                "Installing Camera Drivers", 
                "OpenCV and PyZbar are missing in your current PyCharm environment.\n\nPlease wait a moment while the POS system automatically installs them for you in the background..."
            )
            
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python", "pyzbar"])
                messagebox.showinfo("Installation Complete", "Camera drivers installed successfully! Please completely close the POS app and click 'Run' again in PyCharm to apply the changes.")
                sys.exit(0)
            except subprocess.CalledProcessError as e:
                details = f" ({CV2_IMPORT_ERROR})" if CV2_IMPORT_ERROR else ""
                raise CameraScannerError(
                    f"Auto-install failed. Please run `{sys.executable} -m pip install opencv-python pyzbar` manually in your terminal.{details}"
                )

        if pyzbar_decode is None:
            details = ""
            if PYZBAR_IMPORT_ERROR is not None:
                details = f" ({PYZBAR_IMPORT_ERROR})"
            raise CameraScannerError(
                "pyzbar is not available for barcode decoding. "
                "Run `pip install -r python_pos\\requirements.txt` to enable camera scanning."
                f"{details}"
            )

    def _open_camera(self):
        backend_candidates: list[int | None]
        if cv2 is None:
            return None

        if platform.system() == "Windows":
            backend_candidates = [getattr(cv2, "CAP_DSHOW", None), getattr(cv2, "CAP_ANY", None)]
        else:
            backend_candidates = [getattr(cv2, "CAP_ANY", None)]

        for backend in backend_candidates:
            if backend is None:
                capture = cv2.VideoCapture(self.camera_index)
            else:
                capture = cv2.VideoCapture(self.camera_index, backend)

            if capture.isOpened():
                return capture
            capture.release()

        return None

    def _decode_frame(self, frame) -> list[tuple[CameraScanResult, tuple[int, int, int, int]]]:
        candidates = self._build_decode_candidates(frame)
        for candidate_frame, scale in candidates:
            detections = self._decode_candidate(candidate_frame, scale=scale)
            if detections:
                return detections
        return []

    def _build_decode_candidates(self, frame) -> list[tuple[object, float]]:
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred_frame = cv2.GaussianBlur(gray_frame, (3, 3), 0)
        _, otsu_threshold = cv2.threshold(blurred_frame, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        adaptive_threshold = cv2.adaptiveThreshold(
            gray_frame,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )
        enlarged_gray = cv2.resize(gray_frame, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        enlarged_threshold = cv2.resize(otsu_threshold, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_NEAREST)

        return [
            (frame, 1.0),
            (gray_frame, 1.0),
            (otsu_threshold, 1.0),
            (adaptive_threshold, 1.0),
            (enlarged_gray, 2.0),
            (enlarged_threshold, 2.0),
        ]

    def _decode_candidate(self, frame, scale: float) -> list[tuple[CameraScanResult, tuple[int, int, int, int]]]:
        detections: list[tuple[CameraScanResult, tuple[int, int, int, int]]] = []
        for decoded in pyzbar_decode(frame):
            value = decoded.data.decode("utf-8", errors="replace").strip()
            if not value:
                continue

            rect = decoded.rect
            left = int(rect.left / scale)
            top = int(rect.top / scale)
            width = int(rect.width / scale)
            height = int(rect.height / scale)
            result = CameraScanResult(value=value, symbology=str(decoded.type))
            detections.append((result, (left, top, width, height)))
        return detections

    def _draw_detection(self, frame, detection: tuple[CameraScanResult, tuple[int, int, int, int]]) -> None:
        result, (x, y, width, height) = detection
        cv2.rectangle(frame, (x, y), (x + width, y + height), (46, 204, 113), 2)
        cv2.putText(
            frame,
            f"{result.symbology}: {result.value}",
            (x, max(24, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (46, 204, 113),
            2,
            cv2.LINE_AA,
        )

    def _draw_overlay(self, frame, scan_count: int) -> None:
        cv2.putText(
            frame,
            "Scan multiple barcodes. Press Q or Esc to finish.",
            (16, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            f"Items scanned in this session: {scan_count}",
            (16, 62),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
