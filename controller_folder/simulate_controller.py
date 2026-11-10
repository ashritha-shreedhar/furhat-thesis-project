import time
from controller import TurnTakingController

# Choose personality
controller = TurnTakingController("extrovert")

# Simulate three students speaking
print("\nStudent 1 is speaking...")
controller.process_audio_state(True)

time.sleep(2)

print("\nStudent 1 finished speaking.")
controller.process_audio_state(False)

# Keep checking until robot decides to speak
while True:

    if controller.should_robot_speak():

        controller.robot_started_speaking()

        time.sleep(2)

        controller.robot_finished_speaking()

        break

    print("Robot is waiting...")
    time.sleep(1)