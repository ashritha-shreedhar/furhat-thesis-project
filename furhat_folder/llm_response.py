import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# Load API key from the .env file
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("SAIA_API_KEY")

if not API_KEY:
    raise ValueError(
        "SAIA_API_KEY was not found. Please check your .env file."
    )


# Connect to SAIA
client = OpenAI(
    api_key=API_KEY,
    base_url="https://chat-ai.academiccloud.de/v1",
    timeout=60.0
)

MODEL = "qwen3-30b-a3b-instruct-2507"


def generate_response(
    conversation_history,
    personality="extrovert"
):
    """
    Generate a context-aware response using the conversation history.

    conversation_history should contain messages in this format:

    [
        {"role": "user", "content": "Previous student contribution"},
        {"role": "assistant", "content": "Previous Furhat response"},
        {"role": "user", "content": "Latest student contribution"}
    ]
    """

    if personality == "extrovert":

        personality_prompt = """
You are Furhat, an extroverted social robot participating in a
group discussion with three university students.

Your personality is enthusiastic, expressive, friendly and proactive.

You enjoy contributing ideas, asking relevant questions and encouraging
students to participate.

You may occasionally initiate a contribution when the conversation
allows it, but you must not dominate the discussion.
"""

    elif personality == "introvert":

        personality_prompt = """
You are Furhat, an introverted social robot participating in a
group discussion with three university students.

Your personality is calm, thoughtful, reserved and friendly.

You usually listen carefully before contributing.
When you speak, your contributions are concise, reflective and relevant.

You should not dominate the discussion.
"""

    else:
        raise ValueError(
            "Personality must be 'introvert' or 'extrovert'."
        )

    system_prompt = f"""
{personality_prompt}

CONVERSATION RULES:

1. Understand the discussion from the conversation history.
2. Respond to the actual topic being discussed by the students.
3. Do not assume that the discussion is about any particular subject.
4. If a student asks you a question, answer that question directly.
5. Remember what you and the students have said earlier in this session.
6. Connect your response naturally to previous contributions when relevant.
7. Do not repeat information unnecessarily.
8. Do not introduce unrelated topics.
9. Do not invent facts or pretend to understand something that is unclear.
10. If you genuinely cannot understand a contribution, politely ask for
    clarification.
11. Sound like a natural participant in a group conversation, not a
    virtual assistant giving a formal presentation.
12. Keep spoken responses concise, normally one to three sentences.
13. Do not use emojis, markdown formatting or numbered lists in spoken
    responses.

Your goal is to participate naturally and meaningfully in the
ongoing group discussion.
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    # Add the conversation history
    messages.extend(conversation_history)

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=120
    )

    answer = response.choices[0].message.content

    if not answer:
        return "Could you tell me a little more about that?"

    return answer.strip()