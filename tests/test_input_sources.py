import numpy as np
import pytest

from edge.input.factory import create_input_source
from edge.input.rtsp import RtspSource, redact_rtsp_url
from edge.input.video_file import VideoFileSource
from edge.input.webcam import WebcamSource
from edge.input import rtsp as rtsp_module
from edge.input import video_file as video_file_module


class FakeCapture:
	def __init__(self, opened=True, frames=()):
		self.opened = opened
		self.frames = iter(frames)
		self.released = False
		self.settings = []

	def isOpened(self):
		return self.opened

	def read(self):
		try:
			return True, next(self.frames)
		except StopIteration:
			return False, None

	def set(self, prop_id, value):
		self.settings.append((prop_id, value))
		return True

	def release(self):
		self.released = True


def test_factory_selects_webcam_file_and_rtsp_sources(monkeypatch):
	class FakeWebcam:
		def __init__(self, **_kwargs):
			pass

	monkeypatch.setattr("edge.input.factory.WebcamSource", WebcamSource)

	assert isinstance(create_input_source("0", webcam_capture_cls=FakeWebcam), WebcamSource)
	assert isinstance(create_input_source("clip.mp4"), VideoFileSource)
	assert isinstance(create_input_source("rtsp://camera/stream"), RtspSource)


def test_video_file_source_opens_reads_and_releases(monkeypatch):
	capture = FakeCapture(frames=[np.zeros((2, 2, 3), dtype=np.uint8)])
	monkeypatch.setattr(video_file_module.cv2, "VideoCapture", lambda path: capture)

	with VideoFileSource("clip.mp4") as source:
		ok, frame = source.read()

	assert ok
	assert frame.shape == (2, 2, 3)
	assert capture.released


def test_video_file_source_reports_connection_failure_and_releases(monkeypatch):
	capture = FakeCapture(opened=False)
	monkeypatch.setattr(video_file_module.cv2, "VideoCapture", lambda path: capture)

	with pytest.raises(RuntimeError, match="Unable to open video file"):
		with VideoFileSource("missing.mp4"):
			pass

	assert capture.released


def test_rtsp_source_reconnects_after_a_temporary_read_failure(monkeypatch):
	first = FakeCapture(frames=[])
	second = FakeCapture(frames=[np.ones((2, 2, 3), dtype=np.uint8)])
	captures = iter((first, second))
	monkeypatch.setattr(
		rtsp_module.cv2,
		"VideoCapture",
		lambda *_args: next(captures),
	)

	with RtspSource("rtsp://user:secret@camera/stream", reconnect_attempts=1) as source:
		ok, frame = source.read()

	assert ok
	assert frame.shape == (2, 2, 3)
	assert first.released
	assert second.released


def test_rtsp_credentials_are_redacted_from_description():
	assert "secret" not in redact_rtsp_url("rtsp://user:secret@camera/stream")
	assert "***:***@camera" in redact_rtsp_url("rtsp://user:secret@camera/stream")
