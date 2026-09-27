import sys
from pathlib import Path
import json

# Add project root to sys.path
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from pipeline.db import execute_sql

def main():
    rows = execute_sql("""
        SELECT 
            extra->>'search_term' as search_term, 
            extra->>'community_search' as community_search,
            relevance_class,
            COUNT(*) as count
        FROM raw_records
        WHERE source = 'reddit' AND relevance_class IS NOT NULL
        GROUP BY 1, 2, 3
    """)
    
    stats = {}
    for row in rows:
        st = row['search_term']
        cs = row['community_search']
        rc = row['relevance_class']
        cnt = row['count']
        
        # Skip if no search term (e.g., from old ingestions before we saved search_term)
        if not st:
            continue
            
        key = (st, cs)
        if key not in stats:
            stats[key] = {
                'total': 0,
                'specific_episode': 0,
                'success_or_tip': 0,
                'general_search_complaint': 0,
                'lost_not_hidden': 0,
                'irrelevant': 0
            }
        
        stats[key]['total'] += cnt
        if rc in stats[key]:
            stats[key][rc] += cnt
            
    kept_terms = []
    dropped_terms = []
    neither_terms = []
    
    print(f"{'Search Term':<45} | {'Comm':<18} | {'Total':<5} | {'Spec':<4} | {'Tip':<3} | {'GenC':<4} | {'Lost':<4} | {'Irr':<3} | {'Yield%':<7} | {'Action'}")
    print("-" * 115)
    
    for (st, cs), data in sorted(stats.items(), key=lambda x: (x[0][1], x[0][0])):
        total = data['total']
        spec = data['specific_episode']
        tip = data['success_or_tip']
        genc = data['general_search_complaint']
        lost = data['lost_not_hidden']
        irr = data['irrelevant']
        
        yield_count = spec + tip
        yield_pct = (yield_count / total * 100) if total > 0 else 0
        lost_irr_pct = ((lost + irr) / total * 100) if total > 0 else 0
        
        action = "WAIT"
        if yield_pct >= 15:
            action = "KEEP"
            kept_terms.append(f"{st} ({cs or 'wide'})")
        elif lost_irr_pct >= 50 and spec == 0:
            action = "DROP"
            dropped_terms.append(f"{st} ({cs or 'wide'})")
        else:
            neither_terms.append(f"{st} ({cs or 'wide'})")
            
        print(f"{st:<45} | {cs:<18} | {total:<5} | {spec:<4} | {tip:<3} | {genc:<4} | {lost:<4} | {irr:<3} | {yield_pct:>6.1f}% | {action}")

    print("\n--- Scale-up Rule Results ---")
    print(f"KEPT ({len(kept_terms)}):")
    for t in kept_terms:
        print("  - " + t)
    
    print(f"\nDROPPED ({len(dropped_terms)}):")
    for t in dropped_terms:
        print("  - " + t)
        
    print(f"\nNEITHER KEEP NOR DROP ({len(neither_terms)}):")
    for t in neither_terms:
        print("  - " + t)

if __name__ == '__main__':
    main()
