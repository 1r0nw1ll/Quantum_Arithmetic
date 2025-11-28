"""
Auto-refactor: normalize formatting for emit_metrics_summary.py
"""

#!/usr/bin/env python3
"""
Emit metrics summary: active state counts, completed approvals, artifact counts, and last HI.
Broadcasts collab event metrics.summary and writes to stdout.
"""
import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent.parent
ACTIVE = BASE / 'tasks' / 'active'
COMPLETED = BASE / 'tasks' / 'completed'
PLOTS = BASE / 'artifacts' / 'plots'
EVALS = BASE / 'artifacts' / 'evals'
PROOFS = BASE / 'artifacts' / 'proofs'
LOG_HI = BASE / 'logs' / 'metrics_e8.jsonl'

import sys
sys.path.insert(0, str(BASE))
from qa_agents.cli.collab_bridge import broadcast as collab_broadcast

def active_state_counts():
    from collections import Counter
    c = Counter()
    for p in ACTIVE.glob('*.yaml'):
        try:
            text = p.read_text(encoding='utf-8')
            import yaml
            d = yaml.safe_load(text) or {}
            c[str(d.get('state','')).lower()] += 1
        except Exception:
            continue
    return dict(c)

def last_hi():
    if not LOG_HI.exists():
        return None
    last = None
    with open(LOG_HI, 'r') as f:
        for line in f:
            try:
                last = json.loads(line)
            except Exception:
                continue
    return last

summary = {
    'ts': datetime.now().isoformat(),
    'active_counts': active_state_counts(),
    'artifacts': {
        'plots': len(list(PLOTS.glob('*'))),
        'evals': len(list(EVALS.glob('*'))),
        'proofs': len(list(PROOFS.glob('*'))),
    },
    'last_hi': last_hi(),
}

print(json.dumps(summary, indent=2))
collab_broadcast('metrics.summary', summary)

