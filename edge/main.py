import os

from .mqtt.publisher import MqttPublisher, build_telemetry
from .vision.detector import PersonDetector
from .vision.webcam import WebcamCapture


class EdgePipeline:
	def __init__(self, camera=None, detector=None, publisher=None, facility_id=None):
		self.camera = camera or WebcamCapture()
		self.detector = detector or PersonDetector()
		self.publisher = publisher if publisher is not None else MqttPublisher()
		self.facility_id = facility_id or os.getenv("FACILITY_ID", "facility-1")

	def run(self):
		try:
			with self.camera as camera:
				while True:
					ok, frame = camera.read()
					if not ok:
						break

					detections = self.detector.detect(frame)
					telemetry = build_telemetry(
						self.facility_id,
						self.detector.occupancy,
						sum(detection["crossing"] == "IN" for detection in detections),
						sum(detection["crossing"] == "OUT" for detection in detections),
					)
					self.publisher.publish(telemetry)
					frame = None
					yield {
						"detections": detections,
						"occupancy": self.detector.occupancy,
					}
		except RuntimeError as exc:
			raise RuntimeError(f"Edge pipeline failed: {exc}") from exc
		finally:
			self.publisher.close()
