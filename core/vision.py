# # core/vision.py
# import asyncio
# import cv2
# import mediapipe as mp
# import numpy as np
# import time
# import logging
# from typing import Optional

# log = logging.getLogger("core.vision")


# class JarvisVisionAsync:
#     """
#     Non-blocking-ish vision producer that pushes events to an asyncio.Queue.
#     Keeps processing lightweight so it can run as a background task.
#     """
#     def __init__(
#         self,
#         event_queue: Optional[asyncio.Queue] = None,
#         display: bool = False,
#         skip_frames: int = 1,
#         width: int = 640,
#         height: int = 360,
#     ):
#         self.event_queue = event_queue or asyncio.Queue()
#         self.display = display
#         self.skip_frames = max(1, skip_frames)
#         self.frame_counter = 0
#         self.closed = False

#         # camera
#         self.cap = cv2.VideoCapture(0)
#         self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
#         self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

#         # mediapipe detectors
#         self.mp_face = mp.solutions.face_detection
#         self.face_detection = self.mp_face.FaceDetection(min_detection_confidence=0.6)

#         self.mp_hands = mp.solutions.hands
#         self.hands = self.mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.6)
#         self.mp_draw = mp.solutions.drawing_utils

#         # motion detection
#         self.prev_gray = None

#         # simple state
#         self.my_face_marked = False  # after capture phase can mark the first detected face as "You"

#         # -------------------
#         # NEW: Vision state for conditional queries
#         # -------------------
#         self.state = {
#             "face_seen": False,
#             "hand_count": 0,
#             "hand_landmarks": None,
#             "last_face_ts": 0,
#             "last_hand_ts": 0
#         }

#     async def capture_my_face(self, wait_seconds: int = 3):
#         """Optional: do a short capture so Jarvis can mark 'You' for future frames."""
#         log.info("Capturing your face in %s seconds...", wait_seconds)
#         await asyncio.sleep(wait_seconds)
#         ret, frame = self.cap.read()
#         if not ret:
#             log.warning("capture_my_face: failed to read frame")
#             return False
#         rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#         results = self.face_detection.process(rgb)
#         if results.detections:
#             self.my_face_marked = True
#             # push an explicit event
#             await self.event_queue.put({"type": "face_captured", "name": "You", "ts": time.time()})
#             log.info("Face capture succeeded")
#             return True
#         log.info("No face detected during capture")
#         return False

#     async def run(self):
#         """Main loop: detect faces/hands/motion, push events to queue (async)."""
#         try:
#             while not self.closed:
#                 ret, frame = self.cap.read()
#                 if not ret:
#                     await asyncio.sleep(0.05)
#                     continue

#                 self.frame_counter += 1
#                 if self.frame_counter % self.skip_frames != 0:
#                     if self.display:
#                         cv2.imshow("Jarvis Vision", frame)
#                         cv2.waitKey(1)
#                     await asyncio.sleep(0)
#                     continue

#                 rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

#                 # -------------------
#                 # Face detection
#                 # -------------------
#                 face_results = self.face_detection.process(rgb)
#                 if face_results.detections:
#                     self.state["face_seen"] = True
#                     self.state["last_face_ts"] = time.time()

#                     det = face_results.detections[0]
#                     bbox = det.location_data.relative_bounding_box
#                     ih, iw, _ = frame.shape
#                     x, y, w, h = (int(bbox.xmin * iw), int(bbox.ymin * ih),
#                                   int(bbox.width * iw), int(bbox.height * ih))
#                     label = "You" if self.my_face_marked else "Unknown"

#                     # draw
#                     cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
#                     cv2.putText(frame, label, (x, max(y - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

#                     await self.event_queue.put({"type": "face", "name": label, "bbox": (x, y, w, h), "ts": time.time()})
#                 else:
#                     self.state["face_seen"] = False

#                 # -------------------
#                 # Hand detection
#                 # -------------------
#                 hand_results = self.hands.process(rgb)
#                 if hand_results.multi_hand_landmarks:
#                     self.state["hand_count"] = len(hand_results.multi_hand_landmarks)
#                     self.state["hand_landmarks"] = hand_results.multi_hand_landmarks
#                     self.state["last_hand_ts"] = time.time()

#                     for hand_landmarks in hand_results.multi_hand_landmarks:
#                         self.mp_draw.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

#                     await self.event_queue.put({"type": "hand_detected", "count": len(hand_results.multi_hand_landmarks), "ts": time.time()})
#                 else:
#                     self.state["hand_count"] = 0
#                     self.state["hand_landmarks"] = None

#                 # -------------------
#                 # Motion detection
#                 # -------------------
#                 gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#                 if self.prev_gray is not None:
#                     diff = cv2.absdiff(self.prev_gray, gray)
#                     _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
#                     motion_pixels = int(np.sum(thresh) / 255)
#                     if motion_pixels > 800:
#                         await self.event_queue.put({"type": "motion_detected", "amount": motion_pixels, "ts": time.time()})
#                 self.prev_gray = gray

#                 if self.display:
#                     cv2.imshow("Jarvis Vision", frame)
#                     cv2.waitKey(1)

#                 await asyncio.sleep(0)
#         except asyncio.CancelledError:
#             log.info("JarvisVisionAsync.run cancelled")
#         finally:
#             self._cleanup()

#     def _cleanup(self):
#         self.closed = True
#         try:
#             if self.cap:
#                 self.cap.release()
#         except Exception:
#             pass
#         if self.display:
#             cv2.destroyAllWindows()

#     async def stop(self):
#         self.closed = True
#         await asyncio.sleep(0.1)
#         self._cleanup()