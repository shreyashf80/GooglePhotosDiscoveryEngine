from google import genai
import os
from dotenv import load_dotenv

load_dotenv(".env")
api_keys = os.environ.get("GEMINI_API_KEYS").split(",")
client = genai.Client(api_key=api_keys[0])
for model in client.models.list_models():
    print(model.name)
