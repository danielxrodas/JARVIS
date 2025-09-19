# import asyncio
# import logging
# import time

# log = logging.getLogger("core.vision_consumer")


# async def vision_event_consumer(event_queue: asyncio.Queue, assistant, min_interval=1.0):
#     """
#     Consume vision events and update assistant.vision_state.
#     Rate-limited to avoid spamming.
#     """
#     last_seen = {}  # key -> timestamp

#     while True:
#         try:
#             event = await event_queue.get()
#             if event is None:
#                 break

#             key = f"{event.get('type')}:{event.get('name', event.get('object',''))}"
#             now = asyncio.get_event_loop().time()
#             if now - last_seen.get(key, 0) < min_interval:
#                 continue
#             last_seen[key] = now

#             # -------------------
#             # Update assistant vision state
#             # -------------------
#             if event["type"] == "face":
#                 assistant.vision_state["face_detected"] = True
#                 assistant.vision_state["last_face_ts"] = time.time()
#             elif event["type"] == "hand_detected":
#                 assistant.vision_state["hand_count"] = event.get("count", 0)
#                 assistant.vision_state["last_hand_ts"] = time.time()
#             elif event["type"] == "object_detected":
#                 assistant.vision_state["last_object"] = event.get("object")

#             # -------------------
#             # Optional: push human-readable logs to chat context
#             # -------------------
#             if event["type"] in ["motion_detected", "object_detected", "face_captured"]:
#                 if event["type"] == "motion_detected":
#                     text = f"[VISION] motion detected (amount={event.get('amount')})"
#                 elif event["type"] == "object_detected":
#                     text = f"[VISION] object detected: {event.get('object')}"
#                 elif event["type"] == "face_captured":
#                     text = "[VISION] face capture complete — marking as You"

#                 try:
#                     chat_ctx_copy = assistant.chat_ctx.copy()
#                     chat_ctx_copy.add_message(role="user", content=text)
#                     await assistant.update_chat_ctx(chat_ctx_copy)
#                 except Exception as e:
#                     log.exception("Failed to forward vision event to assistant: %s", e)

#         except asyncio.CancelledError:
#             log.info("vision_event_consumer cancelled")
#             break
#         except Exception:
#             log.exception("vision_event_consumer error")
#             await asyncio.sleep(0.1)