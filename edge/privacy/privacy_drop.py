import cv2
import numpy as np


class PrivacyDrop:
	@staticmethod
	def drop(frame):
		if frame is None:
			return None
		frame_copy = np.array(frame, copy=True, order="C")
		return cv2.GaussianBlur(frame_copy, (35, 35), 0)
