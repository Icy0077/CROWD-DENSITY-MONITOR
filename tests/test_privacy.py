import numpy as np

from edge.main import EdgePipeline
from edge.privacy.privacy_drop import PrivacyDrop
from edge.vision import detector as detector_module


class FakeModel:
	def track(self, **kwargs):
		return [type("Result", (), {"boxes": []})()]


class FakeCamera:
	def __init__(self, frame):
		self.frame = frame
		self.read_count = 0

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		return False

	def read(self):
		self.read_count += 1
		if self.read_count == 1:
			return True, self.frame
		return False, None


class SequenceCamera:
	def __init__(self, frames):
		self.frames = iter(frames)

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		return False

	def read(self):
		try:
			return True, next(self.frames)
		except StopIteration:
			return False, None


class FakePublisher:
	def __init__(self):
		self.messages = []
		self.closed = False

	def publish(self, message):
		self.messages.append(message)

	def close(self):
		self.closed = True


class FakeCountingDetector:
	def __init__(self):
		self.occupancy = 0
		self.events = iter(("IN", None, "IN", "OUT"))

	def detect(self, frame):
		crossing = next(self.events)
		if crossing == "IN":
			self.occupancy += 1
		elif crossing == "OUT":
			self.occupancy = max(0, self.occupancy - 1)
		return [{"crossing": crossing}]


def test_privacy_drop_blurs_a_copy_without_mutating_original():
	frame = np.zeros((100, 100, 3), dtype=np.uint8)
	frame[20:80, :, :] = 255
	original = frame.copy()

	processed = PrivacyDrop.drop(frame)

	assert processed is not frame
	assert processed.flags.writeable
	assert not np.array_equal(processed, original)
	assert np.array_equal(frame, original)


def test_privacy_drop_returns_blurred_copy_for_read_only_frame():
	frame = np.zeros((100, 100, 3), dtype=np.uint8)
	frame[20:80, :, :] = 255
	original = frame.copy()
	frame.setflags(write=False)

	processed = PrivacyDrop.drop(frame)

	assert processed is not frame
	assert processed.flags.writeable
	assert not np.array_equal(processed, original)
	assert np.array_equal(frame, original)


def test_pipeline_publishes_only_aggregate_telemetry(monkeypatch, tmp_path):
	monkeypatch.setattr(detector_module, "YOLO", lambda model_path: FakeModel())
	frame = np.zeros((100, 100, 3), dtype=np.uint8)
	frame[20:80, :, :] = 255
	original = frame.copy()
	publisher = FakePublisher()
	detector = detector_module.PersonDetector()
	pipeline = EdgePipeline(
		camera=FakeCamera(frame),
		detector=detector,
		publisher=publisher,
		facility_id="library_01",
	)

	list(pipeline.run())

	assert publisher.closed
	assert len(publisher.messages) == 1
	assert set(publisher.messages[0]) == {"facility_id", "timestamp", "inflow", "outflow", "occupancy"}
	assert all(isinstance(value, (str, int)) for value in publisher.messages[0].values())
	assert np.array_equal(frame, original)
	assert not np.array_equal(detector.processed_frame, original)
	assert list(tmp_path.iterdir()) == []


def test_pipeline_aggregates_counts_for_reporting_interval():
	frame = np.zeros((10, 10, 3), dtype=np.uint8)
	publisher = FakePublisher()
	pipeline = EdgePipeline(
		camera=SequenceCamera((frame, frame, frame, frame)),
		detector=FakeCountingDetector(),
		publisher=publisher,
		facility_id="library_01",
		reporting_interval_seconds=3600,
	)

	list(pipeline.run())

	assert len(publisher.messages) == 1
	assert publisher.messages[0]["inflow"] == 2
	assert publisher.messages[0]["outflow"] == 1
	assert publisher.messages[0]["occupancy"] == 1
