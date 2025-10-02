from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext
from livekit.plugins import noise_cancellation, cartesia, openai
from livekit.plugins.openai import realtime
from openai.types.beta.realtime.session import TurnDetection

from prompts import AGENT_INSTRUCTION
from commands.calendar import create_calendar_event, set_reminder, delete_reminder, delete_calendar_event
from commands.communication import send_text_message, send_email, call_contact
from commands.media import play_music, can_you_open_the_app, search_web, close_app
from commands.system import (
    unmute_microphone,
    mute_microphone,
    restart_system,
    power_down,
)
from commands.utilities import (
    get_time,
    get_date,
    get_weather,
    get_directions,
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

from mem0 import AsyncMemoryClient
import json
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
                send_text_message, manage_python_project, close_app,
                create_or_open_python, generate_python_code, manage_spring_boot_project,
                create_or_open_spring_file, generate_spring_java_code, 
                create_calendar_event, set_reminder, delete_calendar_event,
                mute_microphone, unmute_microphone, get_directions,
                turn_on_lamp, turn_off_lamp, delete_reminder,
                restart_system,
            ],
            chat_ctx=chat_ctx
        )

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

    # Register shutdown callback
    ctx.add_shutdown_callback(lambda: shutdown_hook(session._agent.chat_ctx, mem0, memory_str))


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
