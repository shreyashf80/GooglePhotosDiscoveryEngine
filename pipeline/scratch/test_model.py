from google import genai
import os
from dotenv import load_dotenv

load_dotenv(".env")
api_keys = os.environ.get("GEMINI_API_KEYS").split(",")
client = genai.Client(api_key=api_keys[0])

try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Say hi"
    )
    print("Success:", response.text)
except Exception as e:
    print("Error:", str(e))
