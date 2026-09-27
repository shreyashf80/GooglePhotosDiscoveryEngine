import os
import sys

# Add project root to PYTHONPATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pipeline.stages.analyze import run_analyze
from pipeline.db import engine
from sqlalchemy import text
import json
import logging

logging.basicConfig(level=logging.INFO)

# Run the analysis
res = run_analyze()
print("Analyze result:", res)

print("\n=== Funnel Table ===")
with engine.begin() as conn:
    rows = conn.execute(text("SELECT stage, episode_count, general_complaint_count, gave_up_rate, avg_severity FROM funnel_stats ORDER BY stage")).fetchall()
    for r in rows:
        print(f"Stage: {r.stage:<10} | Episodes: {r.episode_count:<3} | General: {r.general_complaint_count:<2} | Gave Up Rate: {r.gave_up_rate:.2f} | Avg Severity: {r.avg_severity:.2f}")

print("\n=== Hypothesis Table ===")
with engine.begin() as conn:
    rows = conn.execute(text("SELECT hypothesis_id, status, support_count, contradict_count, relevant_count FROM hypotheses ORDER BY hypothesis_id")).fetchall()
    for r in rows:
        print(f"{r.hypothesis_id}: {r.status:<18} | Support: {r.support_count:<2} | Contradict: {r.contradict_count:<2} | Relevant: {r.relevant_count}")

print("\n=== Top 5 Gaps ===")
with engine.begin() as conn:
    rows = conn.execute(text("SELECT cue_type, gap_score, remembered_share FROM cue_stats WHERE gap_score IS NOT NULL ORDER BY gap_score DESC LIMIT 5")).fetchall()
    for r in rows:
        print(f"Cue: {r.cue_type:<20} | Gap Score: {r.gap_score:.3f} | Remembered Share: {r.remembered_share:.3f}")

print("\n=== Forgotten-Cues Ranking ===")
with engine.begin() as conn:
    rows = conn.execute(text("SELECT cue_type, forgotten_count FROM cue_stats WHERE forgotten_count > 0 ORDER BY forgotten_count DESC")).fetchall()
    for r in rows:
        print(f"Cue: {r.cue_type:<20} | Forgotten Count: {r.forgotten_count}")
