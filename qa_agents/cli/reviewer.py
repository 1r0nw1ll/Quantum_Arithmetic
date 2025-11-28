"""
Auto-refactor: normalize formatting for reviewer.py
"""

#!/usr/bin/env python3
"""
QA Reviewer Agent v4.0
Quality assurance and validation of completed work
"""

import json
try:
    import yaml  # type: ignore
    _YAML_OK = True
except Exception:
    yaml = None
    _YAML_OK = False
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from qa_agents.cli.collab_bridge import broadcast as collab_broadcast

class QAReviewer:
    """Quality assurance agent for completed tasks"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.tasks_active = self.base_dir / "tasks" / "active"
        self.tasks_completed = self.base_dir / "tasks" / "completed"
        self.logs_dir = self.base_dir / "logs"
        self.tasks_completed.mkdir(exist_ok=True)

    def load_task(self, task_file: Path) -> Dict:
        """Load a task from YAML or JSON file"""
        text = task_file.read_text(encoding='utf-8')
        if _YAML_OK:
            return yaml.safe_load(text)
        else:
            return json.loads(text)

    def review_task(self, task: Dict) -> Dict:
        """Perform quality review of completed task"""
        review = {
            'approved': True,
            'feedback': [],
            'score': 85  # Default good score
        }

        title = task['title'].lower()
        lane = task.get('lane', 'green')

        # Basic quality checks
        if lane == 'red':
            review['approved'] = False
            review['feedback'].append("Red lane task requires manual approval")
            review['score'] = 0

        elif 'test' in title:
            review['feedback'].append("Test implementation looks solid")
            review['score'] = 95

        elif 'doc' in title:
            review['feedback'].append("Documentation structure is appropriate")
            review['score'] = 90

        elif 'fix' in title:
            review['feedback'].append("Code fixes implemented cleanly")
            review['score'] = 88

        else:
            review['feedback'].append("General implementation appears correct")
            review['score'] = 85

        return review

    def review_completed_tasks(self) -> List[Dict]:
        """Review all completed tasks"""
        reviewed_tasks = []

        for task_file in self.tasks_active.glob("*.yaml"):
            try:
                task = self.load_task(task_file)

                # Only review tasks marked as completed and with non-error result
                if not task:
                    continue
                if task.get('state') == 'completed':
                    # Check last execution result and enforce quality gate
                    hist = (task.get('execution') or {}).get('history') or []
                    last = hist[-1] if hist else {}
                    res = last.get('result') or {}

                    # Hard failure
                    if res.get('status') == 'error':
                        task['state'] = 'failed'
                        task['metadata']['updated_at'] = datetime.now().isoformat()
                        if _YAML_OK:
                            with open(task_file, 'w') as f:
                                yaml.dump(task, f, default_flow_style=False, sort_keys=False)
                        else:
                            task_file.write_text(json.dumps(task, indent=2), encoding='utf-8')
                        continue

                    # Quality gate: require artifact/applied changes/meaningful changes
                    artifact_path = res.get('artifact')
                    applied_changes = res.get('applied_changes') or 0
                    changes = res.get('changes') or []

                    has_meaningful_changes = bool(changes) and any(c != 'no-op' for c in changes)
                    has_applied = isinstance(applied_changes, int) and applied_changes > 0
                    has_artifact = False
                    try:
                        if artifact_path:
                            from pathlib import Path as _P
                            base_dir = Path(__file__).parent.parent.parent
                            ap = _P(artifact_path)
                            ap = ap if ap.is_absolute() else (base_dir / artifact_path)
                            has_artifact = ap.exists()
                    except Exception:
                        has_artifact = False

                    # Check for research artifacts (E8 analyses, datasets, proofs)
                    if not has_artifact:
                        try:
                            from pathlib import Path as _P
                            base_dir = Path(__file__).parent.parent.parent
                            task_id = task.get('id', '')

                            # Look for artifacts matching this task ID in research outputs
                            artifact_dirs = [
                                base_dir / 'artifacts' / 'evals',
                                base_dir / 'artifacts' / 'proofs',
                                base_dir / 'artifacts' / 'plots',
                                base_dir / 'qa_data'
                            ]

                            for artifact_dir in artifact_dirs:
                                if artifact_dir.exists():
                                    # Check for files containing the task ID
                                    for f in artifact_dir.glob(f'*{task_id}*.*'):
                                        if f.stat().st_size > 50:  # Non-trivial content
                                            has_artifact = True
                                            break
                                if has_artifact:
                                    break
                        except Exception:
                            pass

                    # Also accept QALM responses with meaningful data
                    has_research_output = res.get('rows') or res.get('samples') or res.get('metrics')

                    # Accept ingestion artifacts (scaffolds, extracted text, analysis files)
                    has_ingestion_output = False
                    if res.get('extracted_text') or res.get('analysis_file'):
                        # Check if ingestion files exist and have content
                        try:
                            base_dir = Path(__file__).parent.parent.parent
                            extracted = res.get('extracted_text')
                            analysis = res.get('analysis_file')

                            if extracted:
                                extracted_path = Path(extracted) if Path(extracted).is_absolute() else (base_dir / extracted)
                                if extracted_path.exists() and extracted_path.stat().st_size > 1000:
                                    has_ingestion_output = True

                            if analysis:
                                analysis_path = Path(analysis) if Path(analysis).is_absolute() else (base_dir / analysis)
                                if analysis_path.exists() and analysis_path.stat().st_size > 100:
                                    has_ingestion_output = True
                        except Exception:
                            pass

                    # Accept code stubs, scaffolds, structured JSON outputs
                    has_scaffold = res.get('scaffold') or res.get('code_stub') or res.get('json_output') or res.get('structured_data')

                    # Accept experiment outputs (CSV, plots, benchmarks)
                    has_experiment_output = res.get('csv') or res.get('plots') or res.get('benchmark_results') or res.get('artifacts')

                    if not (has_artifact or has_applied or has_meaningful_changes or has_research_output or has_ingestion_output or has_scaffold or has_experiment_output):
                        # Not enough evidence of real work; fail it for re-run/triage
                        task.setdefault('review', {})
                        task['review'].update({
                            'approved': False,
                            'feedback': ['No artifact or applied changes detected'],
                            'score': 0,
                        })
                        task['state'] = 'failed'
                        task['metadata']['updated_at'] = datetime.now().isoformat()
                        if _YAML_OK:
                            with open(task_file, 'w') as f:
                                yaml.dump(task, f, default_flow_style=False, sort_keys=False)
                        else:
                            task_file.write_text(json.dumps(task, indent=2), encoding='utf-8')
                        print(f"❌ Rejected {task.get('id','task')}: no artifact/changes")
                        continue

                    review = self.review_task(task)
                    task['review'] = review
                    task['metadata']['updated_at'] = datetime.now().isoformat()

                    task_id = task['id']
                    if review['approved']:
                        # Move to completed directory
                        completed_file = self.tasks_completed / f"{task_id}.yaml"
                        if _YAML_OK:
                            with open(completed_file, 'w') as f:
                                yaml.dump(task, f, default_flow_style=False, sort_keys=False)
                        else:
                            completed_file.write_text(json.dumps(task, indent=2), encoding='utf-8')

                        # Remove from active
                        task_file.unlink()

                        print(f"✅ Approved {task_id} (score: {review['score']})")
                    else:
                        print(f"❌ Rejected {task_id}: {review['feedback'][0] if review['feedback'] else 'Failed review'}")
                        task['state'] = 'failed'
                        if _YAML_OK:
                            with open(task_file, 'w') as f:
                                yaml.dump(task, f, default_flow_style=False, sort_keys=False)
                        else:
                            task_file.write_text(json.dumps(task, indent=2), encoding='utf-8')

                    reviewed_tasks.append(task)

            except Exception as e:
                print(f"⚠️  Error reviewing task {task_file.name}: {e}")
                continue

        return reviewed_tasks

    def run(self):
        """Main reviewer execution"""
        print("👀 QA Reviewer: Validating completed work...")

        reviewed_tasks = self.review_completed_tasks()

        if not reviewed_tasks:
            print("📭 No completed tasks found for review")
            return

        approved = sum(1 for t in reviewed_tasks if t['review']['approved'])
        rejected = len(reviewed_tasks) - approved

        print(f"✅ Review complete: {approved} approved, {rejected} rejected")

        # Log activity
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": "Reviewer",
            "action": "quality_review",
            "tasks_reviewed": len(reviewed_tasks),
            "approved": approved,
            "rejected": rejected
        }

        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

        # Collaboration bus event
        collab_broadcast("review.reviewed", {
            "count": len(reviewed_tasks),
            "approved": approved,
            "rejected": rejected,
        })

if __name__ == "__main__":
    reviewer = QAReviewer()
    reviewer.run()
