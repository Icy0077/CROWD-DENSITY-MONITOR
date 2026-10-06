import os
from pathlib import Path
from urllib.parse import urlsplit

from .rtsp import RtspSource
from .video_file import VideoFileSource
from .webcam import WebcamSource
from .usb_camera import UsbCameraSource
from .wifi_camera import WifiCameraSource
from .phone import PhoneCameraSource
from .bluetooth import BluetoothSource


def _as_webcam_index(value):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Webcam source must be a numeric device index, got {value!r}") from exc


def validate_source_url(value, allowed_schemes=("rtsp", "rtsps", "http", "https")):
    parts = urlsplit(str(value))
    if parts.scheme.lower() not in allowed_schemes or not parts.netloc or any(char in str(value) for char in ("\r", "\n")):
        raise ValueError("Camera source must be a valid supported network URL")
    return str(value)


def validate_video_path(value):
    path = Path(str(value))
    if path.suffix.lower() not in {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mjpeg"}:
        raise ValueError("Video source must use a supported media extension")
    if any(part == ".." for part in path.parts):
        raise ValueError("Video source path traversal is not allowed")
    return str(path)


def discover_local_cameras(max_devices=10):
    """Best-effort portable discovery; opening a device is never required to select it."""
    import cv2
    devices = []
    for index in range(max_devices):
        capture = cv2.VideoCapture(index)
        try:
            if capture.isOpened():
                devices.append({"type": "webcam", "index": index, "label": f"Camera {index}"})
        finally:
            capture.release()
    return devices


def create_input_source(source=None, input_type=None, width=None, height=None, webcam_capture_cls=None, transport=None):
    configured_source = os.getenv("INPUT_SOURCE", "0") if source is None else source
    configured_type = (input_type or os.getenv("INPUT_TYPE") or "").strip().lower()
    source_text = str(configured_source)

    if source_text.lower() == "webcam":
        configured_source = os.getenv("INPUT_SOURCE", "0")
        source_text = str(configured_source)
        configured_type = "webcam"

    if configured_type in {"webcam", "camera"}:
        capture_class = webcam_capture_cls
        kwargs = {"device_index": _as_webcam_index(configured_source), "width": width, "height": height}
        if capture_class is not None:
            kwargs["capture_class"] = capture_class
        return WebcamSource(**kwargs)

    if configured_type in {"usb", "usb-camera"}:
        kwargs = {"device_index": _as_webcam_index(configured_source), "width": width, "height": height}
        if webcam_capture_cls is not None: kwargs["capture_class"] = webcam_capture_cls
        return UsbCameraSource(**kwargs)

    if configured_type in {"file", "video", "video-file"}:
        return VideoFileSource(validate_video_path(configured_source))

    if configured_type in {"rtsp", "cctv"}:
        return RtspSource(validate_source_url(configured_source, ("rtsp", "rtsps")), width=width, height=height)

    if configured_type in {"wifi", "ip", "mjpeg"}:
        return WifiCameraSource(validate_source_url(configured_source), width=width, height=height)
    if configured_type == "phone":
        phone_transport = transport or os.getenv("PHONE_TRANSPORT", "webrtc")
        if configured_source and phone_transport in {"rtsp", "mjpeg", "http"}:
            configured_source = validate_source_url(configured_source)
        return PhoneCameraSource(configured_source, transport=phone_transport, width=width, height=height)
    if configured_type in {"bluetooth", "bt"}:
        return BluetoothSource()

    if source_text.lower().startswith(("rtsp://", "rtsps://")):
        return RtspSource(validate_source_url(configured_source, ("rtsp", "rtsps")), width=width, height=height)

    if source_text.isdigit() or (source_text.startswith("-") and source_text[1:].isdigit()):
        capture_class = webcam_capture_cls
        kwargs = {"device_index": _as_webcam_index(configured_source), "width": width, "height": height}
        if capture_class is not None:
            kwargs["capture_class"] = capture_class
        return WebcamSource(**kwargs)

    return VideoFileSource(validate_video_path(configured_source))
