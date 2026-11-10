"""
=========================================================
FURHAT THESIS - MAIN EXPERIMENT SCRIPT
=========================================================

Purpose:
--------

This script connects Furhat to the Python turn-taking
controller and the SAIA language model.

The system performs the following tasks:

1. Connects to Furhat through the Realtime API.
2. Listens to student contributions.
3. Receives speech transcription events.
4. Collects student contributions.
5. Sends conversation history to SAIA when Furhat
   is allowed to speak.
6. Uses the turn-taking controller to decide WHEN
   Furhat should participate.
7. Sends the generated response to Furhat.
8. Records human and robot turns in a CSV file.

Experimental conditions:

    PERSONA = "introvert"

    PERSONA = "extrovert"

The same SAIA response-generation function is used
for both conditions.
=========================================================
"""


# =====================================================
# 1. IMPORT REQUIRED LIBRARIES
# =====================================================

import asyncio
import sys
import csv

from pathlib import Path
from datetime import datetime

from furhat_realtime_api import AsyncFurhatClient, Events

# SAIA response-generation function.
from llm_response import generate_response


# =====================================================
# 2. IMPORT TURN-TAKING CONTROLLER
# =====================================================

# Locate the folder containing controller.py.
# The controller is stored separately from this main file.

controller_folder = (
    Path(__file__).resolve().parent.parent
    / "controller_folder"
)

# Add the controller folder to Python's import path.
sys.path.append(str(controller_folder))

# Import the controller class.
from controller import TurnTakingController


# =====================================================
# 3. EXPERIMENT CONFIGURATION
# =====================================================

# Select the experimental condition.

PERSONA = "extrovert"

# Use "extrovert" when testing the extrovert condition.

# -----------------------------------------------------
# SPEECH DETECTION SETTINGS
# -----------------------------------------------------

# Time of silence required by the Realtime API to
# consider a human speech segment finished.

END_SPEECH_TIMEOUT = 3.0

# How long Furhat listens when nobody starts speaking.

NO_SPEECH_TIMEOUT = 8.0

# Maximum time to wait for Furhat to finish speaking.

ROBOT_SPEECH_TIMEOUT = 45.0


# =====================================================
# 4. TIMESTAMP FUNCTION
# =====================================================

def get_timestamp():

    """
    Returns the current local timestamp.

    The timestamp includes timezone information and
    milliseconds.

    This is used for CSV experiment logging.
    """

    return datetime.now().astimezone().isoformat(
        timespec="milliseconds"
    )


# =====================================================
# 5. MAIN ASYNCHRONOUS FUNCTION
# =====================================================

async def main():

    """
    Main experiment function.

    This function manages the complete conversation
    between the participants and Furhat.
    """

    # Store the selected personality.
    persona = PERSONA

    # =================================================
    # 5.1 INITIALISE TURN-TAKING CONTROLLER
    # =================================================

    controller = TurnTakingController(persona)

    print("\n========================================")
    print(f"Starting {persona.upper()} FURHAT")
    print("========================================")

    print(
        f"End speech timeout: "
        f"{END_SPEECH_TIMEOUT} seconds"
    )

    # =================================================
    # 5.2 CREATE EXPERIMENT DATA FOLDER
    # =================================================

    # The CSV files will be stored in:
    #
    # furhat_folder/
    #     experiment_data/
    #
    # Each session receives a separate CSV file.

    data_folder = (
        Path(__file__).resolve().parent.parent
        / "experiment_data"
    )

    data_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    # Generate a timestamp for the session filename.
    session_time = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    csv_file = data_folder / (
        f"{persona}_session_{session_time}.csv"
    )

    # -------------------------------------------------
    # CSV COLUMN DEFINITIONS
    # -------------------------------------------------

    csv_columns = [

        "turn_number",

        "start_time",

        "end_time",

        "duration_seconds",

        "speaker_type",

        "speaker_id",

        "transcript",

        "language",

        "condition"

    ]

    # Open the CSV file.
    csv_output = open(
        csv_file,
        mode="w",
        newline="",
        encoding="utf-8"
    )

    # Create CSV writer.
    csv_writer = csv.DictWriter(
        csv_output,
        fieldnames=csv_columns
    )

    # Write column headings.
    csv_writer.writeheader()

    # Save the header immediately.
    csv_output.flush()

    print("\nExperiment data will be saved to:")
    print(csv_file)

    # =================================================
    # 5.3 INITIALISE CONVERSATION VARIABLES
    # =================================================

    # Total number of recorded human and robot turns.
    turn_number = 0

    # Timestamp when a human starts speaking.
    human_speech_start_time = None

    # Timestamp when Furhat starts speaking.
    robot_speech_start_time = None

    # Stores speech segments collected during a listening
    # session. They are combined into one contribution.
    pending_student_segments = []

    # Stores the conversation context for SAIA.
    #
    # Example:
    # [
    #     {"role": "user", "content": "Hello"},
    #     {"role": "assistant", "content": "Hello everyone"}
    # ]

    conversation_history = []

    # Event indicating that a listening session has ended.
    listening_finished = asyncio.Event()

    # Event indicating that Furhat has finished speaking.
    speech_finished = asyncio.Event()

    # Tracks whether the robot speech-end event was received.
    #
    # This prevents duplicate CSV entries if the speech
    # completion event is received normally.
    robot_speech_end_received = False

    # =================================================
    # 6. SAVE CONVERSATION TURN TO CSV
    # =================================================

    def save_turn(
        start_time,
        end_time,
        speaker_type,
        speaker_id,
        transcript,
        language=""
    ):

        """
        Saves one completed human or robot contribution.

        Parameters:

            start_time:
                When the speaker started speaking.

            end_time:
                When the speaker finished speaking.

            speaker_type:
                Human or Robot.

            speaker_id:
                Currently Unknown for humans and Furhat for
                the robot.

            transcript:
                Recognised or generated text.

            language:
                Language returned by the speech recogniser.
        """

        nonlocal turn_number

        # Increment the total turn count.
        turn_number += 1

        # Calculate speaking duration.
        duration = (
            datetime.fromisoformat(end_time)
            - datetime.fromisoformat(start_time)
        ).total_seconds()

        # Create CSV row.
        row = {

            "turn_number": turn_number,

            "start_time": start_time,

            "end_time": end_time,

            "duration_seconds": round(duration, 3),

            "speaker_type": speaker_type,

            "speaker_id": speaker_id,

            "transcript": transcript,

            "language": language,

            "condition": persona

        }

        # Write the row to CSV.
        csv_writer.writerow(row)

        # Flush ensures data is saved immediately.
        csv_output.flush()

        print(
            f"\nSaved {speaker_type} turn {turn_number}."
        )

    # =================================================
    # 7. CONNECT TO FURHAT
    # =================================================

    # Connect to the locally running Furhat robot.

    furhat = AsyncFurhatClient(
        host="localhost"
    )

    # Enable detailed API logging.
    furhat.set_logging_level("DEBUG")

    # Establish connection.
    await furhat.connect()

    print("\nSuccessfully connected to Furhat!")

    # =================================================
    # 8. HUMAN SPEECH START EVENT
    # =================================================

    async def on_student_speech_start(event):

        """
        Triggered when the Realtime API detects
        that a human participant has started speaking.
        """

        nonlocal human_speech_start_time

        # Ignore human speech events while Furhat speaks.
        if controller.robot_is_speaking:

            return

        # Record the start time only once.
        if human_speech_start_time is None:

            human_speech_start_time = get_timestamp()

        print("\nStudent started speaking.")

        # Inform the turn-taking controller.
        controller.process_audio_state(True)

    # =================================================
    # 9. HUMAN SPEECH END EVENT
    # =================================================

    async def on_student_speech_end(event):

        """
        Triggered when the Realtime API detects the end
        of a human speech segment.

        The recognised transcript is stored and later
        passed to the controller and SAIA.
        """

        nonlocal human_speech_start_time

        # Ignore human speech events while Furhat speaks.
        if controller.robot_is_speaking:

            return

        # Extract recognised text.
        student_text = event.get("text", "")

        # Extract detected language.
        language = event.get("language", "")

        # Record the end time.
        end_time = get_timestamp()

        print("\nRecognised student speech:")
        print(student_text)

        # Inform the controller that human speech ended.
        controller.process_audio_state(False)

        # Save only non-empty transcripts.
        if student_text and student_text.strip():

            # Save the human turn in the CSV.
            if human_speech_start_time is not None:

                save_turn(

                    start_time=human_speech_start_time,

                    end_time=end_time,

                    speaker_type="Human",

                    # Speaker diarisation is not implemented.
                    speaker_id="Unknown",

                    transcript=student_text,

                    language=language

                )

            # Store the transcript for the complete
            # student contribution.
            pending_student_segments.append({

                "text": student_text.strip(),

                "language": language

            })

            print(
                "\nStudent speech segment added to collection."
            )

        # Reset the speech start timestamp.
        human_speech_start_time = None

    # =================================================
    # 10. LISTENING COMPLETION EVENT
    # =================================================

    async def on_listening_end(event):

        """
        Triggered when Furhat's listening session ends.

        Possible causes include:

            speech_end
            silence_timeout

        The event wakes up the main conversation loop.
        """

        cause = event.get("cause", "")

        print(
            f"\nListening ended. Cause: {cause}"
        )

        listening_finished.set()

    # =================================================
    # 11. ROBOT SPEECH START EVENT
    # =================================================

    async def on_robot_speech_start(event):

        """
        Triggered when Furhat begins speaking.

        Records the robot speech start timestamp.
        """

        nonlocal robot_speech_start_time

        robot_speech_start_time = get_timestamp()

        print("\nFurhat started speaking.")

    # =================================================
    # 12. ROBOT SPEECH END EVENT
    # =================================================

    async def on_robot_speech_end(event):

        """
        Triggered when Furhat finishes speaking.

        The generated robot response is saved in the CSV.
        The speech_finished event allows robot_speak()
        to continue.
        """

        nonlocal robot_speech_start_time

        nonlocal robot_speech_end_received

        # Extract the robot's spoken text.
        robot_text = event.get("text", "")

        # Record the end timestamp.
        end_time = get_timestamp()

        print("\nFurhat finished speaking.")

        # Save the robot contribution.
        if robot_speech_start_time is not None:

            save_turn(

                start_time=robot_speech_start_time,

                end_time=end_time,

                speaker_type="Robot",

                speaker_id="Furhat",

                transcript=robot_text,

                language=""

            )

            robot_speech_start_time = None

        # Mark that the normal speech-end event arrived.
        robot_speech_end_received = True

        # Inform robot_speak() that speech has completed.
        speech_finished.set()

    # =================================================
    # 13. REGISTER REALTIME API EVENT HANDLERS
    # =================================================

    """
    Event handlers connect the Realtime API events
    to the functions defined above.
    """

    furhat.add_handler(

        Events.response_hear_start,

        on_student_speech_start

    )

    furhat.add_handler(

        Events.response_hear_end,

        on_student_speech_end

    )

    furhat.add_handler(

        Events.response_listen_end,

        on_listening_end

    )

    furhat.add_handler(

        Events.response_speak_start,

        on_robot_speech_start

    )

    furhat.add_handler(

        Events.response_speak_end,

        on_robot_speech_end

    )

    # =================================================
    # 14. START FURHAT LISTENING
    # =================================================

    async def start_listening():

        """
        Starts a new listening session.

        partial=False:
            Only final speech transcripts are processed.

        concat=True:
            Speech segments are combined by the API.

        no_speech_timeout:
            Maximum waiting time when nobody speaks.

        end_speech_timeout:
            Silence duration used to determine when a
            human contribution has ended.
        """

        # Reset the listening event before starting again.
        listening_finished.clear()

        await furhat.request_listen_start(

            partial=False,

            concat=True,

            no_speech_timeout=NO_SPEECH_TIMEOUT,

            end_speech_timeout=END_SPEECH_TIMEOUT

        )

        print("\n================================")
        print("FURHAT IS LISTENING")
        print("================================")

    # =================================================
    # 15. COLLECT STUDENT CONTRIBUTION
    # =================================================

    def collect_student_contribution():

        """
        Combines all speech segments collected during
        the current listening session.

        Example:

            Segment 1: "I think Germany"
            Segment 2: "is a good place to study"

        Combined contribution:

            "I think Germany is a good place to study"

        This complete contribution is passed to both
        the controller and SAIA.
        """

        nonlocal pending_student_segments

        if not pending_student_segments:

            return ""

        # Join all recognised speech segments.
        complete_message = " ".join(

            segment["text"]

            for segment in pending_student_segments

        )

        print("\n================================")
        print("COMPLETE STUDENT CONTRIBUTION")
        print("================================")

        print(complete_message)

        # Clear the segments after collection.
        pending_student_segments = []

        return complete_message

    # =================================================
    # 16. GENERATE RESPONSE USING SAIA
    # =================================================

    async def get_llm_response(student_message):

        """
        Sends the conversation history to SAIA.

        The same response-generation function is used
        for both introvert and extrovert conditions.

        The turn-taking controller determines WHEN
        Furhat speaks. SAIA determines WHAT it says.
        """

        print("\n================================")
        print("SENDING CONVERSATION TO SAIA")
        print("================================")

        print("Personality:", persona)

        print("\nLatest student contribution:")
        print(student_message)

        # Add the latest human contribution to history.
        conversation_history.append({

            "role": "user",

            "content": student_message

        })

        print("\nConversation history length:")
        print(len(conversation_history))

        # Run the synchronous SAIA function in a separate
        # thread so that the asynchronous event loop
        # remains available.
        robot_response = await asyncio.to_thread(

            generate_response,

            conversation_history.copy(),

            persona

        )

        # Fallback if SAIA returns an empty response.
        if not robot_response:

            robot_response = (
                "Could you tell me a little more about that?"
            )

        # Add the robot response to conversation history.
        conversation_history.append({

            "role": "assistant",

            "content": robot_response

        })

        print("\nSAIA GENERATED RESPONSE:")
        print(robot_response)

        return robot_response

    # =================================================
    # 17. ROBOT SPEAKING FUNCTION
    # =====================================================

    async def robot_speak(student_message):

        """
        Complete robot speaking workflow.

        Steps:

            1. Generate a response using SAIA.
            2. Inform the controller that Furhat is speaking.
            3. Send the response to Furhat.
            4. Wait for the speech-end event.
            5. Save the robot contribution.
            6. Reset the controller.
        """

        nonlocal robot_speech_start_time

        nonlocal robot_speech_end_received

        # -------------------------------------------------
        # 17.1 GENERATE ROBOT RESPONSE
        # -------------------------------------------------

        try:

            response = await get_llm_response(
                student_message
            )

        except Exception as error:

            print("\nSAIA ERROR:")
            print(error)

            # Use a fallback response if SAIA fails.
            response = (
                "That's interesting. "
                "Could you tell me a little more?"
            )

            conversation_history.append({

                "role": "assistant",

                "content": response

            })

        # -------------------------------------------------
        # 17.2 PREPARE FURHAT TO SPEAK
        # -------------------------------------------------

        print("\n================================")
        print("FURHAT IS PREPARING TO SPEAK")
        print("================================")

        # Update controller state.
        controller.robot_started_speaking()

        # Reset the speech completion event.
        speech_finished.clear()

        # Reset the event-received flag.
        robot_speech_end_received = False

        # Record initial speech start time.
        robot_speech_start_time = get_timestamp()

        # -------------------------------------------------
        # 17.3 SEND RESPONSE TO FURHAT
        # -------------------------------------------------

        try:

            await furhat.request_speak_text(response)

            print("\nWaiting for Furhat to finish speaking...")

            # Wait until the response.speak.end event arrives.
            await asyncio.wait_for(

                speech_finished.wait(),

                timeout=ROBOT_SPEECH_TIMEOUT

            )

        except asyncio.TimeoutError:

            print(
                "\nWARNING: Robot speech completion timed out."
            )

        except Exception as error:

            print("\nFURHAT SPEECH ERROR:")
            print(error)

        finally:

            # -------------------------------------------------
            # 17.4 SAVE FALLBACK ROBOT RECORD IF NECESSARY
            # -------------------------------------------------

            # Normally, the speech-end event saves the turn.
            # If that event was not received, save the response
            # here to avoid losing the robot contribution.

            if (

                not robot_speech_end_received

                and robot_speech_start_time is not None

            ):

                save_turn(

                    start_time=robot_speech_start_time,

                    end_time=get_timestamp(),

                    speaker_type="Robot",

                    speaker_id="Furhat",

                    transcript=response,

                    language=""

                )

                robot_speech_start_time = None

            # -------------------------------------------------
            # 17.5 RESET CONTROLLER
            # -------------------------------------------------

            controller.robot_finished_speaking()

            print("\nRobot turn completed.")

    # =================================================
    # 18. MAIN CONVERSATION LOOP
    # =================================================

    try:

        # Start the first listening session.
        await start_listening()

        while True:

            # Wait until the listening session ends.
            await listening_finished.wait()

            print("\nListening session completed.")

            # Collect all recognised student speech.
            student_message = collect_student_contribution()

            # -------------------------------------------------
            # 18.1 HANDLE EMPTY LISTENING SESSIONS
            # -------------------------------------------------

            # If nobody spoke, restart listening.
            if not student_message:

                print(
                    "\nNo student contribution detected."
                )

                await start_listening()

                continue

            # -------------------------------------------------
            # 18.2 ASK THE TURN-TAKING CONTROLLER
            # -------------------------------------------------

            print("\nChecking turn-taking controller...")

            # IMPORTANT CHANGE:
            #
            # Pass the complete student transcript to the
            # controller.
            #
            # The controller uses this text to check whether
            # the participant explicitly addressed Furhat.
            #
            # Without this argument, direct-address detection
            # cannot work.

            should_speak = controller.should_robot_speak(
                student_message
            )

            print(
                "\nController decision:",
                should_speak
            )

            # -------------------------------------------------
            # 18.3 ROBOT SPEAKS
            # -------------------------------------------------

            if should_speak:

                print(
                    "\nController decided that Furhat should speak."
                )

                await robot_speak(student_message)

            # -------------------------------------------------
            # 18.4 ROBOT REMAINS SILENT
            # -------------------------------------------------

            else:

                print(
                    "\nController decided that Furhat should remain silent."
                )

                # Even when Furhat does not speak, the human
                # contribution must be added to conversation
                # history so SAIA has the full context later.

                conversation_history.append({

                    "role": "user",

                    "content": student_message

                })

            # -------------------------------------------------
            # 18.5 RESTART LISTENING
            # -------------------------------------------------

            await start_listening()

    # =================================================
    # 19. HANDLE CANCELLATION AND INTERRUPTIONS
    # =================================================

    except asyncio.CancelledError:

        print("\nExperiment task cancelled.")

        # Re-raise cancellation so asyncio can shut down
        # correctly. The finally block still performs cleanup.
        raise

    except KeyboardInterrupt:

        print("\nKeyboard interruption received.")

    # =================================================
    # 20. CLEANUP AND SAVE EXPERIMENT DATA
    # =================================================

    finally:

        print("\nStopping experiment and cleaning up...")

        # Disconnect from Furhat.
        try:

            await furhat.disconnect()

        except Exception as error:

            print("\nDisconnect warning:")
            print(error)

        # Close the CSV file.
        if not csv_output.closed:

            csv_output.close()

        print("\n================================")
        print("EXPERIMENT SESSION FINISHED")
        print("================================")

        print("\nFurhat disconnected.")

        print("CSV data saved successfully.")

        print("\nCSV location:")
        print(csv_file)

        print("\nTotal recorded turns:")
        print(turn_number)

        print("\nConversation messages:")
        print(len(conversation_history))


# =====================================================
# 21. START THE EXPERIMENT
# =====================================================

if __name__ == "__main__":

    asyncio.run(main())