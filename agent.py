import logging

from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
    metrics,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import (
    cartesia,
    openai,
    deepgram,
    noise_cancellation,
    silero,
    turn_detector,
)

from datetime import datetime

load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("voice-agent")


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    initial_ctx = llm.ChatContext().append(
        role="system",
        text=(
            "You are a voice assistant created by LiveKit. Your interface with users will be voice. "
            "You should use short and concise responses, and avoiding usage of unpronouncable punctuation. "
            "You were created as a demo to showcase the capabilities of LiveKit's agents framework."
        ),
    )

    logger.info(f"ctx {str(ctx.room)}")
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Wait for the first participant to connect
    participant = await ctx.wait_for_participant()
    logger.info(f"starting voice assistant for participant {participant.identity}")
    
    async def llm_cb(assistant: VoicePipelineAgent, chat_ctx: llm.ChatContext):
        logger.info(f"lm_cb assistant room: {str(assistant._room)} chat_ctx: {str(chat_ctx)}")
        if len(chat_ctx.messages) > 6:
            chat_ctx.messages.pop(1)
        # if len(chat_ctx.messages) > 15:
        #     chat_ctx.messages = chat_ctx.messages[-15:]
    # This project is configured to use Deepgram STT, OpenAI LLM and Cartesia TTS plugins
    # Other great providers exist like Cerebras, ElevenLabs, Groq, Play.ht, Rime, and more
    # Learn more and pick the best one for your app:
    # https://docs.livekit.io/agents/plugins
    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(),
        # use LiveKit's transformer-based turn detector
        turn_detector=turn_detector.EOUModel(),
        # minimum delay for endpointing, used when turn detector believes the user is done with their turn
        min_endpointing_delay=0.5,
        # maximum delay for endpointing, used when turn detector does not believe the user is done with their turn
        max_endpointing_delay=5.0,
        # enable background voice & noise cancellation, powered by Krisp
        # included at no additional cost with LiveKit Cloud
        noise_cancellation=noise_cancellation.BVC(),
        chat_ctx=initial_ctx,
        before_llm_cb=llm_cb
    )

    logger.info("VoicePipelineAgent initialized")

    # Debug event subscriptions
    @agent.on("user_speech_committed")
    def log_user_speech_subscription():
        logger.info("user_speech_committed handler attached")
    
    @agent.on("agent_speech_committed") 
    def log_agent_speech_subscription():
        logger.info("agent_speech_committed handler attached")

    usage_collector = metrics.UsageCollector()

    @agent.on("metrics_collected")
    def on_metrics_collected(agent_metrics: metrics.AgentMetrics):
        metrics.log_metrics(agent_metrics)
        usage_collector.collect(agent_metrics)

    # user_speech_committed
    @agent.on("user_speech_committed")
    def on_user_speech_committed(msg: llm.ChatMessage):
        logger.info(f"Received user_speech_committed event: {msg}")
        try:
            content = msg.content
            if isinstance(content, list):
                content = "\n".join(
                    str(x) if not isinstance(x, llm.ChatImage) else "[image]"
                    for x in content
                )
            
            logger.info(f"Processed user speech content: {content[:100]}...")
            
            transcript = {
                "text": content,
                "is_final": True,
                "timestamp": datetime.now().isoformat()
            }
            # session_data.add_stt_transcript(transcript)
            logger.info(f"Added user speech to session data {str(transcript)}")
        except Exception as e:
            logger.error(f"Error processing user speech: {str(e)}", exc_info=True)

    # agent_speech_committed
    @agent.on("agent_speech_committed") 
    def on_agent_speech_committed(msg: llm.ChatMessage):
        logger.info(f"Received agent_speech_committed event: {msg}")
        try:
            content = msg.content
            if isinstance(content, list):
                content = "\n".join(
                    str(x) if not isinstance(x, llm.ChatImage) else "[image]"
                    for x in content
                )
            
            logger.info(f"Processed agent speech content: {content[:100]}...")
            
            message = {
                "role": "assistant",
                "text": content,
                "timestamp": datetime.now().isoformat()
            }
            # session_data.add_llm_message(message)
            logger.info(f"Added agent speech to session data {str(message)}")
        except Exception as e:
            logger.error(f"Error processing agent speech: {str(e)}", exc_info=True)

    agent.start(ctx.room, participant)

    # The agent should be polite and greet the user when it joins :)
    await agent.say("Hey, how can I help you today?", allow_interruptions=True)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        ),
    )
