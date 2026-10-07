from datetime import datetime

import pytest

from edge import main as edge_main


class FakeFrame:
	def __init__(self, shape=(100, 100, 3)):
		self.shape = shape

	def copy(self):
		return self


class FakeCamera:
	def __init__(self, frames):
		self.frames = iter(frames)

	def __enter__(self):
		return self

	def __exit__(self, *_args):
		return False

	def read(self):
		try:
			return True, next(self.frames)
		except StopIteration:
			return False, None


class FakeDetector:
	def __init__(self, events):
		self.events = iter(events)
		self.occupancy = 0
		self.line = ((50, 0), (50, 99))
		self.processed_frame = None
		self.lines_seen = []

	def detect(self, frame):
		self.processed_frame = frame
		self.lines_seen.append(self.line)
		crossing = next(self.events)
		if crossing == "IN":
			self.occupancy += 1
		elif crossing == "OUT":
			self.occupancy = max(0, self.occupancy - 1)
		return [{"crossing": crossing, "bbox": (1, 2, 3, 4), "track_id": 1, "confidence": 0.9}]


class FakePublisher:
	def __init__(self, fail=False):
		self.messages = []
		self.closed = False
		self.fail = fail

	def publish(self, message):
		if self.fail:
			raise RuntimeError("publish failed")
		self.messages.append(message)

	def close(self):
		self.closed = True


def prepare_visual_demo(monkeypatch, frames, events, publisher):
	detector = FakeDetector(events)
	camera = FakeCamera(frames)
	monkeypatch.setattr(edge_main, "WebcamCapture", lambda **_kwargs: camera)
	monkeypatch.setattr(edge_main, "PersonDetector", lambda **_kwargs: detector)
	monkeypatch.setattr(edge_main, "MqttPublisher", lambda: publisher)
	monkeypatch.setattr(edge_main, "_screen_dimensions", lambda: (1280, 800))
	monkeypatch.setattr(edge_main, "_fit_frame_to_screen", lambda frame, _dimensions: frame)
	for name in ("line", "rectangle", "putText", "namedWindow", "resizeWindow", "imshow"):
		monkeypatch.setattr(edge_main.cv2, name, lambda *_args, **_kwargs: None)
	monkeypatch.setattr(edge_main.cv2, "waitKey", lambda _delay: -1)
	monkeypatch.setattr(edge_main.cv2, "destroyAllWindows", lambda: None)
	return detector


def test_visual_demo_publishes_aggregated_counts_per_interval(monkeypatch, capsys):
	monkeypatch.setenv("FACILITY_ID", "facility-1")
	monkeypatch.setenv("REPORTING_INTERVAL_SECONDS", "10")
	publisher = FakePublisher()
	frames = [FakeFrame() for _ in range(4)]
	detector = prepare_visual_demo(monkeypatch, frames, ("IN", "OUT", "IN", "OUT"), publisher)
	ticks = iter((0, 4, 8, 11, 13))
	monkeypatch.setattr(edge_main.time, "monotonic", lambda: next(ticks))

	edge_main.run_visual_demo()

	assert publisher.closed
	assert len(publisher.messages) == 2
	first, final = publisher.messages
	assert {key: value for key, value in first.items() if key != "timestamp"} == {
		"facility_id": "facility-1",
		"occupancy": 1,
		"inflow": 2,
		"outflow": 1,
	}
	assert {key: value for key, value in final.items() if key != "timestamp"} == {
		"facility_id": "facility-1",
		"occupancy": 0,
		"inflow": 0,
		"outflow": 1,
	}
	for message in publisher.messages:
		assert set(message) == {"facility_id", "timestamp", "occupancy", "inflow", "outflow"}
		datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00"))
	log_lines = capsys.readouterr().out.splitlines()
	assert len(log_lines) == 2
	assert all(line.startswith("Published telemetry: {") for line in log_lines)
	assert detector.occupancy == 0


def test_visual_demo_does_not_log_failed_publish_and_closes_publisher(monkeypatch, capsys):
	publisher = FakePublisher(fail=True)
	prepare_visual_demo(monkeypatch, [FakeFrame()], ("IN",), publisher)

	with pytest.raises(RuntimeError, match="publish failed"):
		edge_main.run_visual_demo()

	assert publisher.closed
	assert "Published telemetry:" not in capsys.readouterr().out


def test_edge_pipeline_defaults_to_facility_one_and_sixty_second_interval(monkeypatch):
	monkeypatch.delenv("FACILITY_ID", raising=False)
	monkeypatch.delenv("REPORTING_INTERVAL_SECONDS", raising=False)

	pipeline = edge_main.EdgePipeline(
		camera=FakeCamera([]),
		detector=FakeDetector(iter(())),
		publisher=FakePublisher(),
	)

	assert pipeline.facility_id == "facility-1"
	assert pipeline.reporting_interval_seconds == 60


def test_edge_pipeline_centers_default_line_for_each_source_resolution():
	detector = FakeDetector(("IN", "OUT"))
	detector.line = None
	pipeline = edge_main.EdgePipeline(
		camera=FakeCamera([
			FakeFrame((480, 640, 3)),
			FakeFrame((720, 1280, 3)),
		]),
		detector=detector,
		publisher=FakePublisher(),
	)

	assert len(list(pipeline.run())) == 2
	assert detector.lines_seen == [
		((320, 0), (320, 479)),
		((640, 0), (640, 719)),
	]
	assert detector.occupancy == 0


def test_visual_demo_draws_the_source_line_used_by_detection(monkeypatch, capsys):
	frames = [
		FakeFrame((480, 640, 3)),
		FakeFrame((480, 640, 3)),
		FakeFrame((720, 1280, 3)),
	]
	first_source = object()
	second_source = object()

	class SwitchingFakeCamera(FakeCamera):
		def __init__(self, camera_frames):
			super().__init__(camera_frames)
			self.sources = iter((first_source, second_source, second_source))
			self.source = None

		def read(self):
			ok, frame = super().read()
			if ok:
				self.source = next(self.sources)
			return ok, frame

	camera = SwitchingFakeCamera(frames)
	detector = FakeDetector(("IN", "OUT", "IN"))
	detector.line = None
	publisher = FakePublisher()
	prepare_visual_demo(monkeypatch, frames, ("IN", "OUT", "IN"), publisher)
	monkeypatch.setenv("EDGE_CONTROL_ENABLED", "0")
	monkeypatch.setenv("EDGE_DEBUG_DISPLAY", "1")
	monkeypatch.setattr(edge_main, "InputDeviceManager", lambda **_kwargs: camera)
	monkeypatch.setattr(
		edge_main,
		"PersonDetector",
		lambda **kwargs: (setattr(detector, "line", kwargs["line"]) or detector),
	)
	drawn_lines = []
	monkeypatch.setattr(
		edge_main.cv2,
		"line",
		lambda _frame, start, end, *_args: drawn_lines.append((start, end)),
	)
	monkeypatch.setattr(edge_main, "_draw_side_label", lambda *_args: None)

	edge_main.run_visual_demo()

	expected_lines = [
		((320, 0), (320, 479)),
		((320, 0), (320, 479)),
		((640, 0), (640, 719)),
	]
	assert detector.lines_seen == expected_lines
	assert drawn_lines == expected_lines
	assert detector.occupancy == 1
	debug_lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("SOURCE:")]
	assert len(debug_lines) == 3


def test_privacy_defaults_on_and_keyboard_controls_toggle_visual_state():
	assert edge_main._privacy_state_for_key(True, -1) is True
	assert edge_main._privacy_state_for_key(True, ord("2")) is False
	assert edge_main._privacy_state_for_key(False, ord("1")) is True


def test_privacy_toggle_does_not_change_counting(monkeypatch):
	monkeypatch.setenv("REPORTING_INTERVAL_SECONDS", "10")
	publisher = FakePublisher()
	detector = prepare_visual_demo(monkeypatch, [FakeFrame(), FakeFrame()], ("IN", "OUT"), publisher)
	states = []
	monkeypatch.setattr(edge_main, "_draw_hud", lambda *_args: states.append(_args[-1]))
	keys = iter((ord("2"), ord("1")))
	monkeypatch.setattr(edge_main.cv2, "waitKey", lambda _delay: next(keys))
	monkeypatch.setattr(edge_main.time, "monotonic", lambda: 0)

	edge_main.run_visual_demo()

	assert states == [True, False]
	assert detector.occupancy == 0
	assert publisher.messages[-1]["occupancy"] == 0


def test_line_side_labels_follow_positive_in_side():
	labels = edge_main._line_side_labels(((50, 0), (50, 100)), "positive")

	assert labels["positive"][0] == "IN ->"
	assert labels["negative"][0] == "OUT <-"
	assert labels["positive"][1][0] < 50
	assert labels["negative"][1][0] > 50


def test_line_side_labels_follow_negative_in_side():
	labels = edge_main._line_side_labels(((50, 0), (50, 100)), "negative")

	assert labels["positive"][0] == "OUT <-"
	assert labels["negative"][0] == "IN ->"
	assert labels["positive"][1][0] < 50
	assert labels["negative"][1][0] > 50


def test_cli_preserves_visual_demo_options(monkeypatch):
	calls = []
	monkeypatch.setattr(edge_main, "run_visual_demo", lambda *args: calls.append(args))

	edge_main.main([
		"--source", "video.mp4",
		"--model", "model.pt",
		"--line", "1,2,3,4",
		"--in-side", "negative",
		"--confidence", "0.6",
		"--image-size", "640",
		"--width", "800",
		"--height", "600",
	])

	assert calls == [("video.mp4", "model.pt", ((1.0, 2.0), (3.0, 4.0)), "negative", 0.6, 640, 800, 600)]
