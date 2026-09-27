import os
import re

with open("pipeline/stages/analyze.py", "r") as f:
    content = f.read()

# Replace _episode_hits_express
new_express = """def _episode_hits_express(episode: dict, cues: list[dict], queries: list[dict]) -> bool:
    \"\"\"Express stage: vague-only cues, explicit cues_forgotten, or user stating they didn't know what to search.\"\"\"
    # All cues are vague
    if cues and all(c.get("precision") == "vague" for c in cues):
        return True

    # Has explicitly forgotten cues
    if episode.get("has_forgotten_cues", False):
        return True

    text = (episode.get("quote_en", "") + " " + episode.get("summary_en", "")).lower()
    if "didn't know what to search" in text or "don't know what to search" in text:
        return True

    return False"""

content = re.sub(r"def _episode_hits_express\(.*?\).*?return False", new_express, content, flags=re.DOTALL)

with open("pipeline/stages/analyze.py", "w") as f:
    f.write(content)
