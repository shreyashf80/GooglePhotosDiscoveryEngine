import os
import re

def update_prd():
    with open('docs/PRD.md', 'r') as f:
        content = f.read()
    
    # Prepend notice
    if 'change_spec_listening_v2' not in content:
        content = "> **NOTE:** This document is overridden by `docs/change_spec_listening_v2.md` regarding ingestion, filtering, themes, and hypotheses.\n\n" + content
    
    # Remove archetypes
    content = re.sub(r'- \*\*G3\.\*\* Compare retrieval problem types \(archetypes\).*', '- **G3.** Compare problem types (themes) and rank areas bottom-up from signals.', content)
    content = re.sub(r'- \*\*G4\.\*\* Evaluate 8 starting hypotheses.*', '- **G4.** Generate and evaluate data-derived hypotheses from signals instead of predefined ones.', content)
    
    # Pages
    content = content.replace('Archetype explorer, Evidence browser, Ask the corpus', 'Themes, Evidence browser, Ask the corpus')
    
    with open('docs/PRD.md', 'w') as f:
        f.write(content)

def update_architecture():
    with open('docs/architecture.md', 'r') as f:
        content = f.read()
        
    if 'change_spec_listening_v2' not in content:
        content = "> **NOTE:** This document is overridden by `docs/change_spec_listening_v2.md`.\n\n" + content
        
    with open('docs/architecture.md', 'w') as f:
        f.write(content)

def update_extraction():
    with open('docs/extraction_spec.md', 'r') as f:
        content = f.read()
        
    if 'change_spec_listening_v2' not in content:
        content = "> **NOTE:** This document is overridden by `docs/change_spec_listening_v2.md`.\n\n" + content
        
    with open('docs/extraction_spec.md', 'w') as f:
        f.write(content)

update_prd()
update_architecture()
update_extraction()
