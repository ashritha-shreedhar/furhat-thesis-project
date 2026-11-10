# Furhat Thesis Project

This project connects the Furhat social robot to a Python turn-taking controller and the SAIA language model.

Furhat is used as a fourth participant in a group discussion with three students. The project compares introverted and extroverted turn-taking conditions.

## Project folders

- `controller_folder/` — turn-taking controller and its simulation and test scripts.
- `furhat_folder/` — Furhat integration, SAIA response generation, and SAIA test script.
- `experiment_data/` — CSV files recorded during experiment sessions.
- `.vscode/` — VS Code settings, including the path used by Pylance to find `controller.py`.

## How the system works

1. Furhat listens to the students through the Furhat Realtime API.
2. The script collects recognized student speech.
3. The turn-taking controller decides whether Furhat should speak.
4. If the controller allows it, `llm_response.py` sends the conversation history to SAIA.
5. The generated response is sent to Furhat.
6. Human and robot speech turns are saved to a CSV file in `experiment_data/`.

The controller decides **when** Furhat speaks. SAIA generates **what** Furhat says.

## Configuration

- Choose the condition in `furhat_folder/furhat_controller_test.py` by setting `PERSONA` to `"introvert"` or `"extrovert"`.
- The SAIA API key is stored in `furhat_folder/.env` as `SAIA_API_KEY`.
- Keep `.env` private. Do not share it or commit it to version control.
- Furhat must be running and reachable at `localhost`.

## Running the project

Use the Python environment where the project dependencies are installed. Run:

```bash
python furhat_controller_test.py