from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext
from livekit.plugins import noise_cancellation, cartesia, openai
from livekit.plugins.openai import realtime
from openai.types.beta.realtime.session import TurnDetection

from prompts import AGENT_INSTRUCTION
from commands.calendar import create_calendar_event, set_reminder, delete_reminder, delete_calendar_event
from commands.communication import send_text_message, send_email, call_contact
from commands.media import play_music, can_you_open_the_app, search_web
from commands.system import (
    unmute_microphone,
    mute_microphone,
    restart_system,
    start_a_new_project,
    power_down,
)
from commands.utilities import (
    get_time,
    get_date,
    get_weather,
    generate_code,
    get_eta,
    turn_off_lamp,
    turn_on_lamp,
)
from core.context_watcher import start_scheduler
from coding.mangeprojects import (manage_python_project, create_or_open_python, generate_python_code,
                                initialize_git_repo,
                                git_stage_file,
                                git_unstage_file,
                                git_commit,
                                git_push,
                                git_undo_last_commit,
                                git_status)
from coding.javaprojects import (
    manage_spring_boot_project,
    create_or_open_spring_file,
    generate_spring_java_code,
)

# from core.vision import JarvisVisionAsync
# from core.vision_consumer import vision_event_consumer
from mem0 import AsyncMemoryClient
import json
# import asyncio
# import time
import logging

load_dotenv()


class Assistant(Agent):
    def __init__(self, chat_ctx=None) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=openai.realtime.RealtimeModel(
                model="gpt-4o-realtime-preview-2024-12-17",
                # voice="sage",
                modalities=["text"],
                turn_detection=TurnDetection(
                    type="semantic_vad",
                    eagerness="auto",
                    create_response=True,
                    interrupt_response=True,
                )
            ),
            tts=cartesia.TTS(
                model="sonic-2",
                voice="5891f60a-e5e5-4f99-836e-c2387feb4342",
            ),
            tools=[
                can_you_open_the_app, get_time, get_date,
                get_weather, search_web, initialize_git_repo,
                git_stage_file, git_unstage_file, git_commit,
                git_push, git_undo_last_commit, git_status,
                play_music, send_email, call_contact, power_down,
                send_text_message, manage_python_project, 
                create_or_open_python, generate_python_code, manage_spring_boot_project,
                create_or_open_spring_file, generate_spring_java_code, 
                create_calendar_event, set_reminder, delete_calendar_event,
                mute_microphone, unmute_microphone, get_eta,
                turn_on_lamp, turn_off_lamp, delete_reminder,
                restart_system,
            ],
            chat_ctx=chat_ctx
        )
    #     self.vision_state = {
    #         "face_detected": False,
    #         "last_object": None,
    #         "hand_count": 0,
    #         "last_face_ts": 0,
    #         "last_hand_ts": 0,
    #     }

    # # --- ADDED: Handle vision-specific queries ---
    # async def handle_user_input(self, user_text: str):
    #     """Handle user input and respond to vision-specific queries."""

    #     text_lower = user_text.lower()

    #     # Can you see me?
    #     if "can you see me" in text_lower:
    #         # optional: reset face_detected if last face > 2 sec ago
    #         if time.time() - self.vision_state.get("last_face_ts", 0) > 2:
    #             self.vision_state["face_detected"] = False

    #         if self.vision_state.get("face_detected", False):
    #             return await self.send_response("Yes, I see you clearly.")
    #         else:
    #             return await self.send_response("Not right now, I don’t see you.")

    #     # What do you see?
    #     if "what do you see" in text_lower:
    #         obj = self.vision_state.get("last_object")
    #         if obj:
    #             return await self.send_response(f"I see a {obj}.")
    #         else:
    #             return await self.send_response("I don't see any objects right now.")

    #     # How many fingers?
    #     if "how many fingers" in text_lower:
    #         count = self.vision_state.get("hand_count", 0)
    #         if count > 0:
    #             return await self.send_response(f"I see {count} fingers.")
    #         else:
    #             return await self.send_response("I can't detect your fingers right now.")

    #     # Otherwise, default LLM handling
    #     return await super().handle_user_input(user_text)

    # # --- helper to send responses into chat context ---
    # async def send_response(self, text: str):
    #     if hasattr(self, "chat_ctx"):
    #         self.chat_ctx.add_message({"role": "assistant", "content": text})
    #     return text
    
    
    

# ==============================
# ENTRYPOINT
# ==============================
async def entrypoint(ctx: agents.JobContext):
    
    async def shutdown_hook(chat_ctx: ChatContext, mem0: AsyncMemoryClient, memory_str: str):
        logging.info("Shutting down, saving chat context to memory...")
        messages_formatted = [
            
        ]

        logging.info(f"Chat context messages: {chat_ctx.items}")

        for item in chat_ctx.items:
            content_str = ''.join(item.content) if isinstance(item.content, list) else str(item.content)
            
            if memory_str and memory_str in content_str:
                continue
            
            if item.role in ['user', 'assistant']:
                messages_formatted.append({
                    "role": item.role,
                    "content": content_str.strip()
                })

        logging.info(f"Formatted messages to add to memory: {messages_formatted}")
        if messages_formatted:
            try:
                await mem0.add(messages_formatted, user_id="Daniel")
                logging.info("Chat context saved to memory.")
            except Exception as e:
                logging.error(f"Failed to save chat context to Mem0: {e}")
        else:
            logging.info("No messages to save, skipping Mem0 add.")

    # Initialize session and assistant
    session = AgentSession(tts=cartesia.TTS(
                model="sonic-2",
                voice="5891f60a-e5e5-4f99-836e-c2387feb4342",
            ))

    # Initialize memory
    mem0 = AsyncMemoryClient()
    user_name = "Daniel"
    results = await mem0.get_all(user_id=user_name)
    initial_ctx = ChatContext()
    memory_str = ''

    if results:
        memories = [
            {
                "memory": result["memory"],
                "updated_at": result["updated_at"]
            }
            for result in results
        ]
        memory_str = json.dumps(memories)
        logging.info(f"Memories: {memory_str}")
        initial_ctx.add_message(
            role="assistant",
            content=f"The user's name is {user_name}, and this is relvant context about him: {memory_str}."
        )

    # Create assistant with correct ChatContent
    assistant = Assistant(chat_ctx=initial_ctx)
    
    
    # # --- Vision integration start ---
    # vision_queue = asyncio.Queue()
    # vision = JarvisVisionAsync(event_queue=vision_queue, display=False, skip_frames=2, width=640, height=360)

    # try:
    #     await vision.capture_my_face(wait_seconds=2)
    # except Exception:
    #     pass

    # vision_task = asyncio.create_task(vision.run())
    # consumer_task = asyncio.create_task(vision_event_consumer(vision_queue, assistant, min_interval=1.0))

    # def _shutdown_vision_tasks():
    #     for t in (consumer_task, vision_task):
    #         if not t.done():
    #             t.cancel()
    #     try:
    #         asyncio.create_task(vision.stop())
    #     except Exception:
    #         pass

    # ctx.add_shutdown_callback(lambda: _shutdown_vision_tasks())
    # # --- Vision integration end ---

    # Start scheduler (reminders, etc.)
    start_scheduler(session)

    # Connect to the LiveKit room
    await ctx.connect()

    # Start session with assistant
    await session.start(
        room=ctx.room,
        agent=assistant,
        room_input_options=RoomInputOptions(
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    # await inject_video_frame(ctx, assistant)
    # "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYW1lIjoibXkgbmFtZSIsInZpZGVvIjp7InJvb21Kb2luIjp0cnVlLCJyb29tIjoibXktcm9vbSIsImNhblB1Ymxpc2giOnRydWUsImNhblN1YnNjcmliZSI6dHJ1ZSwiY2FuUHVibGlzaERhdGEiOnRydWV9LCJzdWIiOiJpZGVudGl0eSIsImlzcyI6IkFQSUVxQXpKRGU1ZHNnNiIsIm5iZiI6MTc1ODA3ODc5OCwiZXhwIjoxNzU4MTAwMzk4fQ.auz2uqMECVRS1aYZShB0gYbaJDnQJzYfEAI5arRXCSI";

    # Sync callback for transcription
    # def on_transcription(event):
    #     transcription = event.transcription
    #     asyncio.create_task(assistant.handle_user_input(transcription))

    # session.on("transcription", on_transcription)

    # Register shutdown callback
    ctx.add_shutdown_callback(lambda: shutdown_hook(session._agent.chat_ctx, mem0, memory_str))


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
