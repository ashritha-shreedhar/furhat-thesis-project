"""
Turn-Taking Controller for the Furhat Thesis Experiment

Purpose:
--------
This controller determines WHEN Furhat should speak during a
conversation involving three human participants and the robot.

Two interaction conditions are implemented:

1. EXTROVERT
   - More proactive
   - Can speak after one human turn
   - Higher initial speaking probability
   - Shorter cooldown

2. INTROVERT
   - More reserved
   - Waits for at least two human turns
   - Lower initial speaking probability
   - Longer cooldown

IMPORTANT:
----------
Both conditions share the same direct-address rule.

If a participant explicitly addresses Furhat and asks it a
question or requests assistance, Furhat responds regardless
of its normal speaking probability or cooldown.

The controller does NOT identify human emotions, vocal tone,
or individual speakers. It uses the transcribed text and
turn-taking events supplied by the Furhat Realtime API.
"""

import time
import random
import re


class TurnTakingController:

    # =====================================================
    # 1. INITIALISE THE CONTROLLER
    # =====================================================

    def __init__(self, persona):

        """
        Initialise the controller according to the selected
        experimental condition.

        persona must be either:
            "introvert"
            "extrovert"
        """

        # -------------------------------------------------
        # EXTROVERT CONFIGURATION
        # -------------------------------------------------

        if persona == "extrovert":

            self.required_human_turns = 1

            self.base_speaking_chance = 0.65

            self.minimum_cooldown_time = 10

            self.hard_ceiling = 45

            self.escalation_step = 0.15

        # -------------------------------------------------
        # INTROVERT CONFIGURATION
        # -------------------------------------------------

        elif persona == "introvert":

            self.required_human_turns = 2

            self.base_speaking_chance = 0.35

            self.minimum_cooldown_time = 20

            self.hard_ceiling = 90

            self.escalation_step = 0.15

        else:

            raise ValueError(
                "Persona must be either 'introvert' or 'extrovert'."
            )

        self.persona = persona

        # =================================================
        # 2. INITIALISE CONVERSATION STATE
        # =================================================

        # Tracks whether a human is currently speaking.
        self.human_is_speaking = False

        # Tracks whether Furhat is currently speaking.
        self.robot_is_speaking = False

        # Stores the time when a human turn ended.
        self.pending_turn_completion_time = None

        # Counts completed human turns since Furhat last spoke.
        self.human_turns_since_last_robot_turn = 0

        # Store the experiment start time.
        self.experiment_start_time = time.time()

        # Store the last time Furhat finished speaking.
        self.last_robot_spoken_time = self.experiment_start_time

        # Current speaking probability.
        self.current_speaking_chance = self.base_speaking_chance

        # Prevents the controller from evaluating the same
        # completed human-turn count repeatedly.
        self.last_evaluated_turn_count = 0

        # =================================================
        # 3. DISPLAY INITIAL CONFIGURATION
        # =================================================

        print("\n================================")
        print(f"Controller initialized: {persona.upper()}")
        print(f"Speaking probability: {self.base_speaking_chance}")
        print(f"Required human turns: {self.required_human_turns}")
        print(f"Cooldown: {self.minimum_cooldown_time}s")
        print(f"Hard ceiling: {self.hard_ceiling}s")
        print("Direct-address override: ENABLED")
        print("================================\n")

    # =====================================================
    # 4. DETECT WHETHER A PARTICIPANT ADDRESSES FURHAT
    # =====================================================

    def is_directly_addressed(self, text):

        """
        Checks whether the participant explicitly mentions
        Furhat and asks it a question or makes a request.

        Examples:
            "Furhat, what do you think?"
            "Can you explain this, Furhat?"
            "Furhat, can you help us?"

        Speech recognition may transcribe Furhat's name
        differently, so a few common variations are included.

        This is text-based detection, NOT voice-tone detection.
        """

        if not text:
            return False

        text = text.lower().strip()

        # Common transcription variations of the robot's name.
        name_patterns = [
            r"\bfurhat\b",
            r"\bfur\s+hat\b",
            r"\bfor\s+heart\b",
            r"\bfur\s+hut\b",
            r"\bforhat\b"
        ]

        name_detected = any(
            re.search(pattern, text)
            for pattern in name_patterns
        )

        # If Furhat's name is not detected, there is no
        # direct-address override.
        if not name_detected:
            return False

        # Words and phrases indicating a question or request.
        request_patterns = [

            r"\bwhat do you think\b",
            r"\bwhat do you say\b",
            r"\bdo you think\b",
            r"\bdo you have\b",

            r"\bcan you\b",
            r"\bcould you\b",
            r"\bwould you\b",
            r"\bwill you\b",

            r"\bplease\b",
            r"\bexplain\b",
            r"\bsuggest\b",
            r"\bhelp us\b",
            r"\btell us\b",

            r"\byour opinion\b",
            r"\bany idea\b",
            r"\bwhat is your\b",
            r"\bhow would you\b",
            r"\bwhat about you\b"
        ]

        request_detected = any(
            re.search(pattern, text)
            for pattern in request_patterns
        )

        # Both the robot's name and a request must be detected.
        if name_detected and request_detected:

            print("\n================================")
            print("DIRECT ADDRESS DETECTED!")
            print("Furhat has been explicitly addressed.")
            print("Overriding normal turn-taking rules.")
            print("================================\n")

            return True

        return False

    # =====================================================
    # 5. TRACK HUMAN SPEECH ACTIVITY
    # =====================================================

    def process_audio_state(self, human_speaking):

        """
        Called by the Furhat Realtime API event handlers.

        human_speaking = True:
            A participant has started speaking.

        human_speaking = False:
            A participant has finished speaking.

        A completed turn is confirmed later when the
        controller evaluates the conversation.
        """

        if human_speaking:

            self.human_is_speaking = True

            # Reset pending completion if speech resumes.
            self.pending_turn_completion_time = None

        else:

            self.human_is_speaking = False

            # Record the time when speech ended.
            if self.pending_turn_completion_time is None:

                self.pending_turn_completion_time = time.time()

    # =====================================================
    # 6. CONFIRM COMPLETED HUMAN TURNS
    # =====================================================

    def update_turn_completion(self):

        """
        Confirms a human turn after the speech-end event.

        The Furhat Realtime API already uses the configured
        end_speech_timeout to determine when speech has ended.

        Therefore, this controller does not introduce another
        independent silence timer.
        """

        if self.pending_turn_completion_time is None:
            return

        if time.time() >= self.pending_turn_completion_time:

            self.human_turns_since_last_robot_turn += 1

            print(
                "Human turn confirmed. "
                f"Completed human turns: "
                f"{self.human_turns_since_last_robot_turn}"
            )

            self.pending_turn_completion_time = None

    # =====================================================
    # 7. DECIDE WHETHER FURHAT SHOULD SPEAK
    # =====================================================

    def should_robot_speak(self, student_text=""):

        """
        Main decision-making function.

        Returns:
            True  -> Furhat should speak.
            False -> Furhat should continue listening.

        Decision priority:

        1. Never interrupt ongoing speech.
        2. Respond to direct questions addressed to Furhat.
        3. Check the minimum required human turns.
        4. Check the hard ceiling.
        5. Check cooldown.
        6. Apply probability-based turn-taking.
        """

        current_time = time.time()

        # First, update the number of completed human turns.
        self.update_turn_completion()

        # -------------------------------------------------
        # PRIORITY 1: AVOID INTERRUPTING SPEECH
        # -------------------------------------------------

        if self.human_is_speaking:
            return False

        if self.robot_is_speaking:
            return False

        # Wait until the current contribution is complete.
        if self.pending_turn_completion_time is not None:
            return False

        # -------------------------------------------------
        # PRIORITY 2: DIRECT-ADDRESS OVERRIDE
        # -------------------------------------------------

        # This rule applies equally to both personalities.
        # A direct question overrides the normal thresholds.

        if self.is_directly_addressed(student_text):

            self.last_evaluated_turn_count = (
                self.human_turns_since_last_robot_turn
            )

            print("Controller decision: DIRECT RESPONSE")

            return True

        # -------------------------------------------------
        # PRIORITY 3: MINIMUM HUMAN TURN REQUIREMENT
        # -------------------------------------------------

        if (
            self.human_turns_since_last_robot_turn
            < self.required_human_turns
        ):

            return False

        # Only evaluate a new human-turn count once.
        if (
            self.human_turns_since_last_robot_turn
            == self.last_evaluated_turn_count
        ):

            return False

        # Calculate the time since Furhat last spoke.
        time_since_robot = (
            current_time - self.last_robot_spoken_time
        )

        # -------------------------------------------------
        # PRIORITY 4: HARD CEILING
        # -------------------------------------------------

        # If the maximum waiting time has passed, Furhat
        # speaks at the next eligible decision opportunity.

        if time_since_robot >= self.hard_ceiling:

            print(
                f"[{self.persona.upper()}] "
                f"Hard ceiling reached: {time_since_robot:.1f}s"
            )

            self.last_evaluated_turn_count = (
                self.human_turns_since_last_robot_turn
            )

            return True

        # -------------------------------------------------
        # PRIORITY 5: COOLDOWN
        # -------------------------------------------------

        if time_since_robot < self.minimum_cooldown_time:

            print(
                f"[{self.persona.upper()}] "
                f"Cooldown active: {time_since_robot:.1f}s"
            )

            self.last_evaluated_turn_count = (
                self.human_turns_since_last_robot_turn
            )

            return False

        # -------------------------------------------------
        # PRIORITY 6: PROBABILITY-BASED DECISION
        # -------------------------------------------------

        self.last_evaluated_turn_count = (
            self.human_turns_since_last_robot_turn
        )

        random_value = random.random()

        print(
            f"[{self.persona.upper()}] "
            f"Speaking probability: "
            f"{self.current_speaking_chance:.2f}"
        )

        print(
            f"[{self.persona.upper()}] "
            f"Random value: {random_value:.2f}"
        )

        if random_value < self.current_speaking_chance:

            print(
                f"[{self.persona.upper()}] "
                "Decision: ROBOT WILL SPEAK"
            )

            return True

        else:

            print(
                f"[{self.persona.upper()}] "
                "Decision: ROBOT WILL WAIT"
            )

            # Increase the probability for the next
            # eligible human-turn opportunity.
            self.current_speaking_chance = min(
                1.0,
                self.current_speaking_chance
                + self.escalation_step
            )

            return False

    # =====================================================
    # 8. RECORD WHEN FURHAT STARTS SPEAKING
    # =====================================================

    def robot_started_speaking(self):

        self.robot_is_speaking = True

        print(
            f"[{self.persona.upper()}] "
            "Robot started speaking."
        )

    # =====================================================
    # 9. RESET CONTROLLER AFTER FURHAT FINISHES SPEAKING
    # =====================================================

    def robot_finished_speaking(self):

        """
        Called after Furhat finishes its spoken contribution.

        The speaking probability returns to its initial value.
        The human-turn counter is reset.
        The cooldown timer starts again.
        """

        self.robot_is_speaking = False

        self.last_robot_spoken_time = time.time()

        self.human_turns_since_last_robot_turn = 0

        self.last_evaluated_turn_count = 0

        self.current_speaking_chance = (
            self.base_speaking_chance
        )

        self.pending_turn_completion_time = None

        print(
            f"[{self.persona.upper()}] "
            "Robot finished speaking. Controller reset."
        )