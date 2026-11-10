from controller import TurnTakingController

# Test extrovert controller
extrovert = TurnTakingController("extrovert")

print("Extrovert silence threshold:", extrovert.silence_threshold)
print("Extrovert speaking probability:", extrovert.base_speaking_chance)

print("-------------------------")

# Test introvert controller
introvert = TurnTakingController("introvert")

print("Introvert silence threshold:", introvert.silence_threshold)
print("Introvert speaking probability:", introvert.base_speaking_chance)