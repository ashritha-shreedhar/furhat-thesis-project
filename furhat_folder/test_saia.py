import os
import requests
from dotenv import load_dotenv

# Load API key
load_dotenv()

API_KEY = os.getenv("SAIA_API_KEY")

BASE_URL = "https://chat-ai.academiccloud.de/v1"

if not API_KEY:
    raise ValueError("SAIA API key not found!")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

# Retrieve available models
response = requests.post(
    f"{BASE_URL}/models",
    headers=headers
)

print("Status code:", response.status_code)

response.raise_for_status()

models = response.json()

print("\nAvailable SAIA models:\n")

for model in models.get("data", []):
    print(model.get("id"))