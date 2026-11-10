import asyncio
from furhat_realtime_api import AsyncFurhatClient, Events


async def main():

    furhat = AsyncFurhatClient(host="localhost")
    furhat.set_logging_level("DEBUG")

    await furhat.connect()
    print("Connected to Furhat!")

    # Track when Furhat finishes speaking
    speech_finished = asyncio.Event()

    async def on_speech_end(event):
        print("Furhat finished speaking.")
        speech_finished.set()

    # Receive the student's recognised speech
    async def on_student_speech(event):
        student_text = event.get("text", "")
        print("\nStudent said:", student_text)

    # Register event handlers
    furhat.add_handler(
        Events.response_speak_end,
        on_speech_end
    )

    furhat.add_handler(
        Events.response_hear_end,
        on_student_speech
    )

    # Step 1: Furhat speaks
    await furhat.request_speak_text("Hello! I can hear you.")

    # Step 2: Wait until Furhat finishes speaking
    await asyncio.wait_for(speech_finished.wait(), timeout=15)

    # Step 3: Start listening only after speaking is complete
    await furhat.request_listen_start(
        partial=False,
        concat=True
    )

    print("\nFurhat is listening. Please speak!")

    try:
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping...")

    finally:
        await furhat.disconnect()
        print("Disconnected from Furhat.")


if __name__ == "__main__":
    asyncio.run(main())