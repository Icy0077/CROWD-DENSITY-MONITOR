import cv2


class PrivacyDrop:
	@staticmethod
	def drop(frame):
		if frame is None:
			return None
		return cv2.GaussianBlur(frame, (35, 35), 0)
