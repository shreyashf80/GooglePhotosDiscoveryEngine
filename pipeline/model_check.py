import os
import requests
from pipeline.config import GEMINI_API_KEYS
import google.genai as genai

def run_model_check():
    print("Checking models...")
    keys = GEMINI_API_KEYS
    if not keys:
        print("No keys found.")
        return
        
    working_models = set()
    failed_models = set()
    key = keys[0]
    
    client = genai.Client(api_key=key)
    try:
        models = client.models.list()
        
        for m in models:
            if not m.name.startswith("models/gemini"):
                continue
                
            if "generateContent" not in m.supported_actions:
                continue
                
            model_id = m.name.split("models/")[1]
            print(f"Testing {model_id}...")
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={key}"
            try:
                resp = requests.post(url, json={"contents": [{"parts": [{"text": "reply OK"}]}]}, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    try:
                        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    except:
                        text = "UNKNOWN"
                    print(f"  [SUCCESS] {model_id} responded: {text}")
                    working_models.add(model_id)
                else:
                    print(f"  [FAIL] {model_id} failed: {resp.status_code}")
                    failed_models.add(model_id)
            except Exception as e:
                print(f"  [ERROR] {model_id} error: {e}")
                failed_models.add(model_id)
                
    except Exception as e:
        print(f"Failed to list models: {e}")

    print("\n=== SUMMARY ===")
    print(f"Working models: {', '.join(working_models)}")
    print(f"Failed models: {', '.join(failed_models)}")

if __name__ == "__main__":
    run_model_check()
