import re

# Patch filter.py
with open("pipeline/stages/filter.py", "r") as f:
    content = f.read()

# Add a helper function to delete episodes
helper = """
def _delete_episodes_for_record(conn, record_id: str):
    ep_ids = [r[0] for r in conn.execute(text("SELECT episode_id FROM episodes WHERE record_id = :rid"), {"rid": record_id}).fetchall()]
    if ep_ids:
        conn.execute(text("DELETE FROM episode_queries WHERE episode_id = ANY(:eids)"), {"eids": ep_ids})
        conn.execute(text("DELETE FROM episode_cues WHERE episode_id = ANY(:eids)"), {"eids": ep_ids})
        conn.execute(text("DELETE FROM episode_forgotten WHERE episode_id = ANY(:eids)"), {"eids": ep_ids})
        conn.execute(text("DELETE FROM hypothesis_evidence WHERE episode_id = ANY(:eids)"), {"eids": ep_ids})
        conn.execute(text("DELETE FROM episodes WHERE episode_id = ANY(:eids)"), {"eids": ep_ids})

"""

content = content.replace("logger = logging.getLogger(__name__)\n", "logger = logging.getLogger(__name__)\n" + helper)
content = content.replace(
    "                    counts[\"keyword_miss_en_excluded\"] += 1",
    "                    _delete_episodes_for_record(conn, record_id)\n                    counts[\"keyword_miss_en_excluded\"] += 1"
)
content = content.replace(
    "                                    WHERE record_id = :id",
    "                                    WHERE record_id = :id\n                                \"\"\"),\n                                {\n                                    \"status\": new_status,\n                                    \"rel_class\": rel_class,\n                                    \"reason\": reason,\n                                    \"lang\": lang,\n                                    \"id\": rid,\n                                    \"run_id\": run_id,\n                                },\n                            )\n                            if new_status == \"excluded\":\n                                _delete_episodes_for_record(conn, rid)"
)
# We need to clean up the double replacement because of the complex replace. Let's just use regex.
