from .base import InputSource
from .rtsp import RtspSource, redact_rtsp_url


class PhoneCameraSource(InputSource):
    """Phone source boundary. RTSP is supported; WebRTC is a future transport."""
    is_live = True
    input_type = "phone"
    connection = "wi-fi"

    def __init__(self, url=None, transport="webrtc", **kwargs):
        self.url = url
        self.source = redact_rtsp_url(url) if url else None
        self.transport = transport.lower()
        self.options = kwargs
        self.delegate = RtspSource(url, **kwargs) if url and self.transport in {"rtsp", "mjpeg", "http"} else None

    @property
    def description(self):
        return f"phone ({self.transport})"

    @property
    def status(self):
        available = self.delegate is not None
        return {"type": self.input_type, "description": self.description, "connection": self.connection,
                "connected": False, "video_available": available,
                "message": "WebRTC signaling integration required" if not available else ""}

    def __enter__(self):
        if self.delegate is None:
            raise RuntimeError("Phone WebRTC source is not connected; provide an RTSP URL or signaling adapter.")
        self.delegate.__enter__()
        return self

    def read(self):
        if self.delegate is None:
            raise RuntimeError("Phone source has no compatible video transport")
        return self.delegate.read()

    def release(self):
        if self.delegate:
            self.delegate.release()


class PhoneWebRtcSignaling:
    """Small interface for a future local browser/WebRTC signaling server."""
    def offer(self, sdp):
        raise NotImplementedError

    def close(self):
        pass
