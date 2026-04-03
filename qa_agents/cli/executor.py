"""
Auto-refactor: normalize formatting for executor.py
"""

#!/usr/bin/env python3
"""
QA Executor Agent v4.0
Executes active tasks assigned to specific agents and records outputs.

Currently supported assignees:
- qalm: runs local QALM agent to generate analysis or theorem text.
- rust: runs rust_porter to scaffold Rust stubs + PyO3 glue and emit patches.
Other assignees are logged as deferred.
"""

import json
import sys
import os
import subprocess
import shlex
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml  # type: ignore
    _YAML_OK = True
except Exception:
    yaml = None
    _YAML_OK = False

# Ensure project root is on path for imports
_BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_BASE_DIR))
from qa_agents.cli.collab_bridge import broadcast as collab_broadcast

# Try to import QALM only when available (torch may be missing)


class QAExecutor:
    """Execute tasks by delegating to agent-specific handlers"""

    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.tasks_active = self.base_dir / "tasks" / "active"
        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        # Initialize agent instances lazily
        self._qalm: Optional[QALMAgent] = None
        self._qalm_multimodal = None
        self._qalm_data_collector = None
        self._e8_benchmark = None
        self._pim_kernel = None

    def _load_task(self, path: Path) -> Optional[Dict]:
        try:
            text = path.read_text(encoding="utf-8")
            return yaml.safe_load(text) if _YAML_OK else json.loads(text)
        except Exception:
            return None

    def _save_task(self, path: Path, task: Dict) -> None:
        if _YAML_OK:
            with open(path, "w") as f:
                yaml.dump(task, f, default_flow_style=False, sort_keys=False)
        else:
            path.write_text(json.dumps(task, indent=2), encoding="utf-8")

    def _ensure_qalm(self):
        if self._qalm is None:
            # Try to load latest trained model first (self-improvement!)
            latest_model = _BASE_DIR / 'trained_models' / 'qa_model_latest.pt'
            fallback_model = _BASE_DIR / 'trained_models' / 'qa_model_light.pt'

            try:
                from qa_agents.cli.qalm import QALMAgent  # type: ignore
                if latest_model.exists():
                    print(f"🧠 Loading latest self-improved model: {latest_model.name}")
                    self._qalm = QALMAgent(model_path=str(latest_model))
                elif fallback_model.exists():
                    print(f"🧠 Loading baseline model: {fallback_model.name}")
                    self._qalm = QALMAgent(model_path=str(fallback_model))
                else:
                    self._qalm = QALMAgent(model_path=None)
            except Exception as e:
                # Fallback to a lightweight dummy agent when torch or model isn't available
                print(f"⚠️ QALM loading failed, using dummy: {e}")
                class DummyQALM:
                    def generate_response(self, prompt: str, qa_tuple=None, max_length: int = 100) -> str:
                        base = "QALM(dry): "
                        if qa_tuple:
                            base += f"tuple={qa_tuple} "
                        return base + (prompt[:200] if prompt else "Processed task")

                    def analyze_qa_tuple(self, qa_tuple):
                        b, e, d, a = qa_tuple
                        inv = {
                            'closure_b_e_d': abs((b + e) - d) < 1e-6,
                            'closure_e_d_a': abs((e + d) - a) < 1e-6,
                        }
                        return {
                            'qa_tuple': qa_tuple,
                            'invariants_satisfied': inv,
                            'model_analysis': f"Dummy analysis for tuple {qa_tuple}",
                            'is_valid_qa_tuple': all(inv.values()),
                        }

                self._qalm = DummyQALM()
        return self._qalm

    def _execute_with_rust_porter(self, task: Dict) -> Dict:
        try:
            from qa_agents.cli.rust_porter import RustPorter  # type: ignore
        except Exception as e:
            return {"status": "error", "error": f"rust_porter_import_failed:{e}"}
        porter = RustPorter(_BASE_DIR)
        try:
            return porter.run_task(task)
        except Exception as e:
            return {"status": "error", "error": f"rust_porter_failed:{e}"}

    def _ensure_qalm_multimodal(self):
        if self._qalm_multimodal is None:
            try:
                from qa_agents.cli.qalm_multimodal_agent import QALMMultimodalAgent, create_qalm_multimodal_agent
                self._qalm_multimodal = create_qalm_multimodal_agent(self.base_dir)
                print("🧠 Loaded QALM Multimodal Agent")
            except Exception as e:
                print(f"⚠️ QALM Multimodal loading failed: {e}")
                # Fallback dummy
                class DummyMultimodal:
                    def process_multimodal_input(self, input_data):
                        return {"status": "dummy", "message": "Multimodal processing not available"}
                    def create_agential_plan(self, goal, context):
                        return {"goal": goal, "steps": [{"description": "Dummy step"}]}
                    def autonomous_operation(self, goal):
                        return {"goal": goal, "success": False}
                self._qalm_multimodal = DummyMultimodal()
        return self._qalm_multimodal

    def _ensure_qalm_data_collector(self):
        if self._qalm_data_collector is None:
            print("DEBUG: Attempting to load Torch-Free Data Collector Agent...")
            try:
                from qa_agents.cli.qa_torch_free_data_collector import TorchFreeDataCollector, create_torch_free_data_collector
                self._qalm_data_collector = create_torch_free_data_collector(self.base_dir)
                print("🧠 Loaded Torch-Free Data Collector Agent")
            except Exception as e:
                import traceback
                print(f"⚠️ Torch-Free Data Collector loading failed: {e}")
                traceback.print_exc() # Print the full traceback
                # Fallback dummy
                class DummyDataCollector:
                    def autonomous_data_collection(self, topics, max_sources=10):
                        return {"error": "Data collector not available", "topics": topics}
                self._qalm_data_collector = DummyDataCollector()
        return self._qalm_data_collector

    def _ensure_e8_benchmark(self):
        """Lazy-load E8 Benchmark Agent"""
        if self._e8_benchmark is None:
            try:
                from qa_agents.cli.e8_benchmark_agent import E8BenchmarkAgent
                self._e8_benchmark = E8BenchmarkAgent(base_dir=self.base_dir)
                print("✓ E8 Benchmark Agent loaded")
            except Exception as e:
                print(f"⚠️ E8 Benchmark Agent loading failed: {e}")
                # Fallback dummy
                class DummyE8Agent:
                    def execute(self, task):
                        return {"status": "error", "error": "E8 agent not available"}
                self._e8_benchmark = DummyE8Agent()
        return self._e8_benchmark

    def _execute_with_qalm_data_collector(self, task: Dict) -> Dict:
        """Execute task using QALM Data Collector Agent"""
        try:
            agent = self._ensure_qalm_data_collector()
            task_id = task.get('id', 'unknown')
            title = task.get('title', '')
            content = task.get('content', '')

            # Determine operation type based on task content
            if any(keyword in title.lower() for keyword in ['collect', 'gather', 'forage']):
                # Autonomous data collection
                # Extract topics from content or use defaults
                topics = self._extract_topics_from_content(content)
                if not topics:
                    topics = ['machine learning', 'artificial intelligence', 'quantum computing']

                result = agent.autonomous_data_collection(topics, max_sources=10)
                return {
                    "status": "ok",
                    "output": result,
                    "task_type": "data_collection"
                }

            elif any(keyword in title.lower() for keyword in ['enhance', 'training', 'improve']):
                # Enhance QALM training with collected data
                result = agent.enhance_qalm_training()
                return {
                    "status": "ok",
                    "output": result,
                    "task_type": "training_enhancement"
                }

            elif any(keyword in title.lower() for keyword in ['stats', 'statistics', 'summary']):
                # Show collection statistics
                stats = agent.get_collection_stats()
                return {
                    "status": "ok",
                    "output": stats,
                    "task_type": "collection_stats"
                }

            else:
                # Default to data collection
                topics = ['mathematical reasoning', 'theorem proving', 'invariant learning']
                result = agent.autonomous_data_collection(topics, max_sources=5)
                return {
                    "status": "ok",
                    "output": result,
                    "task_type": "data_collection"
                }

        except Exception as e:
            return {"status": "error", "error": f"qalm_data_collector_execution_failed: {str(e)}"}

    def _extract_topics_from_content(self, content: str) -> List[str]:
        """Extract relevant topics from task content"""
        # Simple keyword extraction
        content_lower = content.lower()

        topic_keywords = {
            'machine learning': ['machine learning', 'ml', 'neural network', 'deep learning'],
            'artificial intelligence': ['artificial intelligence', 'ai', 'intelligent systems'],
            'quantum computing': ['quantum', 'qubit', 'quantum computing'],
            'mathematical reasoning': ['mathematical', 'theorem', 'proof', 'reasoning'],
            'computer vision': ['computer vision', 'image', 'vision', 'cv'],
            'natural language': ['natural language', 'nlp', 'language processing'],
            'reinforcement learning': ['reinforcement learning', 'rl', 'reinforcement'],
            'graph neural networks': ['graph neural', 'gnn', 'graph network']
        }

        topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                topics.append(topic)

        return topics[:3]  # Limit to 3 topics

    def _execute_with_qalm_multimodal(self, task: Dict) -> Dict:
        """Execute task using QALM Multimodal Agent"""
        try:
            agent = self._ensure_qalm_multimodal()
            task_id = task.get('id', 'unknown')
            title = task.get('title', '')
            content = task.get('content', '')

            # Determine operation type based on task content
            if any(keyword in title.lower() for keyword in ['multimodal', 'vision', 'audio', 'process']):
                # Multimodal processing
                from qa_agents.cli.qalm_multimodal_agent import MultimodalQAInput
                multimodal_input = MultimodalQAInput(text=content)
                result = agent.process_multimodal_input(multimodal_input)
                return {
                    "status": "ok",
                    "output": result,
                    "task_type": "multimodal_processing"
                }

            elif any(keyword in title.lower() for keyword in ['agential', 'plan', 'goal']):
                # Agential planning
                from qa_agents.cli.qalm_multimodal_agent import MultimodalQAInput
                context = MultimodalQAInput(text=content)
                plan = agent.create_agential_plan(content, context)
                return {
                    "status": "ok",
                    "output": {
                        "plan": {
                            "goal": plan.goal,
                            "steps": [{"description": s["description"]} for s in plan.steps],
                            "total_steps": len(plan.steps)
                        }
                    },
                    "task_type": "agential_planning"
                }

            elif any(keyword in title.lower() for keyword in ['autonomous', 'execute', 'operation']):
                # Autonomous operation
                result = agent.autonomous_operation(content, max_steps=5)
                return {
                    "status": "ok",
                    "output": result,
                    "task_type": "autonomous_operation"
                }

            else:
                # Default multimodal processing
                from qa_agents.cli.qalm_multimodal_agent import MultimodalQAInput
                multimodal_input = MultimodalQAInput(text=content)
                result = agent.process_multimodal_input(multimodal_input)
                return {
                    "status": "ok",
                    "output": result,
                    "task_type": "multimodal_processing"
                }

        except Exception as e:
            return {"status": "error", "error": f"qalm_multimodal_execution_failed: {str(e)}"}

    def _execute_with_qalm(self, task: Dict) -> Dict:
        """Execute task using QALM agent"""
        import os, json, hashlib
        from pathlib import Path
        base = _BASE_DIR
        evals = base / 'artifacts' / 'evals'
        proofs = base / 'artifacts' / 'proofs'
        evals.mkdir(parents=True, exist_ok=True)
        proofs.mkdir(parents=True, exist_ok=True)

        title = (task.get('title') or '').lower()
        task_id = task.get('id') or hashlib.md5((task.get('title') or '').encode('utf-8')).hexdigest()[:8]

        # Helper to write json artifact
        def write_json_artifact(path: Path, data: dict) -> Dict:
            path.write_text(json.dumps(data, indent=2), encoding='utf-8')
            return {"status": "ok", "artifact": str(path)}

        # 1) E8 exploration
        if 'e8' in title:
            try:
                from qa_e8_alignment import e8_alignment_single
                rows = []
                for b in [1,2,3]:
                    for e in [1,2,3]:
                        d = b + e
                        a = e + d
                        score = e8_alignment_single(b, e, d, a)
                        rows.append({"b":b,"e":e,"d":d,"a":a,"e8":score})
                out = evals / f"e8_exploration_{task_id}.json"
                return write_json_artifact(out, {"title": task.get('title'), "rows": rows})
            except Exception as e:
                return {"status": "error", "error": f"e8_compute_failed:{e}"}

        # 2) Apply QA arithmetic to audio signal classification (produce QA summaries)
        if 'audio' in title and 'classification' in title:
            try:
                from projects.volk_triangle.triangle_util import compute_summary
                samples = []
                for b,e in [(1,2),(2,3),(3,5)]:
                    samples.append(compute_summary(float(b), float(e)))
                out = evals / f"audio_qa_summary_{task_id}.json"
                return write_json_artifact(out, {"title": task.get('title'), "samples": samples})
            except Exception as e:
                return {"status": "error", "error": f"audio_compute_failed:{e}"}

        # 3) Collect and curate dataset (summarize existing datasets)
        if 'collect' in title and 'dataset' in title:
            try:
                stats = {}
                data_dir = base / 'qa_data'
                for p in data_dir.glob('*.json*'):
                    stats[p.name] = os.path.getsize(p)
                out = proofs / f"dataset_index_{task_id}.json"
                return write_json_artifact(out, {"title": task.get('title'), "files": stats})
            except Exception as e:
                return {"status": "error", "error": f"dataset_index_failed:{e}"}

        # 4) Design optimal QA-specialized model architecture (emit config suggestion)
        if 'design' in title and 'model' in title:
            try:
                vocab_size = 10000
                data_file = base / 'qa_data' / 'qa_training_dataset.json'
                if data_file.exists():
                    try:
                        import json as _json
                        js = _json.loads(data_file.read_text())
                        # crude token count
                        texts = []
                        if isinstance(js, dict) and 'data' in js:
                            for arr in js['data'].values():
                                for it in arr:
                                    texts.append((it.get('text_description','')+' '+it.get('qa_reasoning','')).strip())
                        tokens = set()
                        for t in texts:
                            tokens.update(t.split())
                        vocab_size = max(2000, min(50000, len(tokens)))
                    except Exception:
                        pass
                cfg = {
                    "vocab_size": vocab_size,
                    "hidden_size": 128,
                    "num_hidden_layers": 2,
                    "num_attention_heads": 2,
                    "intermediate_size": 256,
                    "max_position_embeddings": 256
                }
                out = proofs / f"qa_model_recommendation_{task_id}.json"
                return write_json_artifact(out, {"title": task.get('title'), "config": cfg})
            except Exception as e:
                return {"status": "error", "error": f"model_design_failed:{e}"}

        # 5) Build local training pipeline (sanity checks)
        if 'build' in title and 'training pipeline' in title:
            status = {"imports": False, "dataset": False}
            try:
                import importlib
                importlib.import_module('qa_training_pipeline')
                status['imports']=True
            except Exception:
                pass
            status['dataset'] = (base / 'qa_data' / 'qa_training_dataset.json').exists()
            out = proofs / f"pipeline_status_{task_id}.json"
            return write_json_artifact(out, {"title": task.get('title'), "status": status})

        # 6) Integrate QALM into agent system (tokenize/generate)
        if 'integrate' in title and 'qalm' in title:
            try:
                qalm = self._ensure_qalm()
                resp = qalm.generate_response("Test integration of QALM.")
                out = proofs / f"qalm_integration_{task_id}.json"
                return write_json_artifact(out, {"title": task.get('title'), "response": resp[:200]})
            except Exception as e:
                return {"status": "error", "error": f"qalm_integration_failed:{e}"}

        # 7) Evaluate QALM performance (baseline stub)
        if 'evaluate' in title and 'qalm' in title:
            try:
                # Baseline: report dataset sizes and placeholder metrics
                data_dir = base / 'qa_data'
                metrics = {"datasets": [p.name for p in data_dir.glob('*.json*')]}
                out = evals / f"qalm_eval_baseline_{task_id}.json"
                return write_json_artifact(out, {"title": task.get('title'), "metrics": metrics})
            except Exception as e:
                return {"status": "error", "error": f"qalm_eval_failed:{e}"}

        # Fallback: simple invariant analysis if tuple provided using dummy QALM
        qalm = self._ensure_qalm()
        qa_tuple = None
        tuple_data = task.get("tuple") or task.get("qa_tuple")
        if isinstance(tuple_data, dict):
            qa_tuple = [
                float(tuple_data.get("b", 0)),
                float(tuple_data.get("e", 0)),
                float(tuple_data.get("d", 0)),
                float(tuple_data.get("a", 0)),
            ]
            return qalm.analyze_qa_tuple(qa_tuple)

        # Default: minimal response
        prompt = task.get("title", "")
        desc = task.get("description", "")
        content = (prompt + "\n\n" + desc).strip()
        response = qalm.generate_response(content or "Analyze this QA task", qa_tuple=None)
        return {"status": "ok", "response": response}

    def _execute_training(self, task: Dict) -> Dict:
        """Execute model training on accumulated research data (self-improvement!)"""
        import subprocess
        from pathlib import Path as _P
        base = _BASE_DIR

        print("🧠 SELF-IMPROVEMENT: Initiating model training...")

        try:
            # Consolidate research artifacts into training data
            evals_dir = base / 'artifacts' / 'evals'
            training_data = {"data": {}, "texts": []}

            # Collect all E8 and QA research results
            for eval_file in evals_dir.glob('*.json'):
                try:
                    with open(eval_file) as f:
                        data = json.load(f)
                        # Add to training corpus
                        if 'rows' in data:
                            for row in data['rows']:
                                key = f"qa_{row.get('b')}_{row.get('e')}"
                                training_data['data'][key] = row
                        if 'title' in data:
                            training_data['texts'].append(data['title'])
                except Exception:
                    continue

            # Save consolidated training data
            training_file = base / 'qa_data' / 'consolidated_research.json'
            training_file.parent.mkdir(parents=True, exist_ok=True)
            with open(training_file, 'w') as f:
                json.dump(training_data, f, indent=2)

            print(f"📊 Consolidated {len(training_data['data'])} QA samples for training")

            # Run lightweight training (1 epoch to avoid long blocking)
            cmd = [
                'python3', str(base / 'train_qa_only.py'),
                '--data', str(training_file),
                '--epochs', '1',
                '--output', str(base / 'trained_models' / 'qa_model_latest.pt')
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=base)

            if result.returncode == 0:
                print("✅ Training completed successfully!")
                return {
                    "status": "ok",
                    "artifact": str(base / 'trained_models' / 'qa_model_latest.pt'),
                    "samples_trained": len(training_data['data']),
                    "training_log": result.stdout[-500:] if result.stdout else "No output"
                }
            else:
                print(f"⚠️ Training failed: {result.stderr[:200]}")
                return {
                    "status": "error",
                    "error": f"Training failed: {result.stderr[:200]}"
                }

        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Training timeout (>5min)"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def execute_task(self, path: Path, task: Dict) -> Optional[Dict]:
        """Execute a single task and update its record; returns result dict on success."""
        assignee = (task.get("assignee") or "").lower()
        lane = task.get("lane", "green")
        state = task.get("state", "queued")

        # Do not re-execute tasks that were explicitly reviewed and rejected
        rev = task.get('review') or {}
        if rev.get('approved') is False:
            return None

        # Only process safe lanes and assigned tasks; allow retry on failed when opted-in
        retry_failed = os.getenv("QA_RETRY_FAILED", "0") == "1"
        if lane == "red" or (state not in {"assigned", "in_progress"} and not (retry_failed and state == "failed")):
            return None

        start = datetime.now().isoformat()
        result: Optional[Dict] = None

        try:
            # Apply proposed files upfront (self-upgrade path)
            applied_changes = self._apply_proposed_files(task)
            if applied_changes:
                result = {"status": "ok", "applied_changes": len(applied_changes)}
                collab_broadcast("execute.applied_changes", {"count": len(applied_changes), "task_id": task.get('id')})
                task.setdefault('execution', {}).setdefault('history', []).append({
                    'agent': assignee or 'opencode',
                    'started_at': start,
                    'completed_at': datetime.now().isoformat(),
                    'result': result,
                })
                task['state'] = 'completed'
                task.setdefault('metadata', {})['updated_at'] = datetime.now().isoformat()
                self._save_task(path, task)
                return result

            # No proposed changes; delegate
            if assignee == "trainer":
                # SELF-IMPROVEMENT: Train model on accumulated research
                result = self._execute_training(task)
                status = 'ok' if result.get('status') == 'ok' else 'failed'
            elif assignee == "qalm":
                result = self._execute_with_qalm(task)
                status = 'ok'
            elif assignee == "qalm_multimodal":
                result = self._execute_with_qalm_multimodal(task)
                status = 'ok'
            elif assignee == "qalm_data_collector":
                result = self._execute_with_qalm_data_collector(task)
                status = 'ok'
            elif assignee == "opencode":
                # Allow external override via OPENCODE_CMD
                if os.getenv("OPENCODE_CMD"):
                    ext = self._execute_with_external_cmd(os.getenv("OPENCODE_CMD"), task, agent_name="opencode")
                    # If external failed, mark awaiting instead of error
                    if ext.get('status') == 'error':
                        task['state'] = 'awaiting_external'
                        result = {'status': 'deferred', 'external': 'opencode', 'detail': ext}
                        status = 'deferred'
                    else:
                        result = ext
                        status = 'ok'
                else:
                    result = self._execute_with_opencode(task)
                    status = 'ok'
            elif assignee == "e8_benchmark":
                result = self._execute_with_e8_benchmark(task)
                status = 'ok' if result.get('status') == 'ok' else 'failed'
            elif assignee == "pim_kernel":
                result = self._execute_with_pim_kernel(task)
                status = 'ok' if result.get('status') == 'ok' else 'failed'
            elif assignee == "rust":
                result = self._execute_with_rust_porter(task)
                status = 'ok' if result.get('status') == 'ok' else 'failed'

            elif assignee in {"codex", "gemini", "claude"}:
                # Fallback to local collab_broadcast if no external command configured
                cmd = os.getenv(f"{assignee.upper()}_CMD")
                if not cmd:
                    cb = _BASE_DIR / "collab_broadcast"
                    if cb.exists():
                        cmd = str(cb)
                ext = self._execute_with_external_cmd(cmd, task, agent_name=assignee)
                if ext.get('status') == 'error':
                    task['state'] = 'awaiting_external'
                    result = {'status': 'deferred', 'external': assignee, 'detail': ext}
                    status = 'deferred'
                else:
                    result = ext
                    status = 'ok'
            else:
                result = {"status": "skipped", "reason": f"unknown assignee '{assignee}'"}
                status = 'skipped'

            # Attach execution record
            execution = task.get("execution") or {}
            history: List[Dict] = execution.get("history") or []
            history.append({
                "agent": assignee,
                "started_at": start,
                "completed_at": datetime.now().isoformat(),
                "result": result,
            })
            execution["history"] = history
            task["execution"] = execution

            # Mark completed only for successful work
            if result.get('status') == 'ok' or result.get('applied_changes'):
                task["state"] = "completed"
            elif result.get('status') == 'deferred':
                task["state"] = 'awaiting_external'
            else:
                task["state"] = 'failed'
            task.setdefault("metadata", {})["updated_at"] = datetime.now().isoformat()

            # Save updates
            self._save_task(path, task)

            return result
        except Exception as e:
            # Record failure
            execution = task.get("execution") or {}
            history: List[Dict] = execution.get("history") or []
            history.append({
                "agent": assignee,
                "started_at": start,
                "completed_at": datetime.now().isoformat(),
                "error": str(e),
            })
            execution["history"] = history
            task["execution"] = execution
            task["state"] = "failed"
            task.setdefault("metadata", {})["updated_at"] = datetime.now().isoformat()
            self._save_task(path, task)
            return None

    def run(self) -> None:
        print("🛠️  QA Executor: Processing active tasks...")
        processed = 0

        for task_file in sorted(self.tasks_active.glob("*.yaml")):
            task = self._load_task(task_file)
            if not task:
                print(f"DEBUG: Could not load task from {task_file.name}")
                continue

            print(f"DEBUG: Processing task file: {task_file.name}")
            review = task.get('review', {})
            state = task.get('state')
            print(f"DEBUG: Task state: {state}, review approved: {review.get('approved')}")
            print(f"DEBUG: Skipping conditions: review rejected: {review.get('approved') == False}, completed/awaiting: {state in ('completed', 'awaiting_external')}")

            # Skip tasks that were reviewed and rejected - but allow retry for queued/assigned/failed
            if review.get('approved') is False and state not in ('assigned', 'queued', 'failed'):
                print(f"DEBUG: Skipping {task_file.name} because review is not approved and state is {state}.")
                continue

            # Skip tasks that are already completed or awaiting external
            if state in ('completed', 'awaiting_external'):
                print(f"DEBUG: Skipping {task_file.name} because state is {state}.")
                continue

            res = self.execute_task(task_file, task)
            if res is not None:
                processed += 1
                title = (task.get("title") or task.get("id") or str(task_file.name))
                print(f"  • Executed: {title}")

        # Log
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": "Executor",
            "action": "task_execution",
            "tasks_processed": processed,
        }
        log_file = self.logs_dir / "agent_runs.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Collaboration bus event
        collab_broadcast("execute.processed", {"processed": processed})

        print(f"✅ Execution complete: {processed} tasks processed")

    # --- Agent-specific handlers ---
    def _apply_proposed_files(self, task: Dict) -> List[str]:
        changes: List[str] = []
        proposed = task.get('proposed_files') or []
        if isinstance(proposed, list):
            for pf in proposed:
                try:
                    path = pf.get('path')
                    content = pf.get('content', '')
                    mode = pf.get('mode', '')
                    if not path:
                        continue
                    fpath = _BASE_DIR / path
                    fpath.parent.mkdir(parents=True, exist_ok=True)
                    if content is not None:
                        fpath.write_text(content, encoding='utf-8')
                    if mode == 'exec':
                        try:
                            import stat
                            fpath.chmod(fpath.stat().st_mode | stat.S_IEXEC)
                        except Exception:
                            pass
                    changes.append(f"wrote {path}")
                except Exception as e:
                    changes.append(f"error writing {pf.get('path')}: {e}")
        return changes
    def _apply_files_from_list(self, files: List[Dict]) -> List[str]:
        changes: List[str] = []
        for pf in files:
            try:
                path = pf.get('path')
                content = pf.get('content', '')
                mode = pf.get('mode', '')
                if not path:
                    continue
                fpath = _BASE_DIR / path
                fpath.parent.mkdir(parents=True, exist_ok=True)
                if content is not None:
                    fpath.write_text(content, encoding='utf-8')
                if mode == 'exec':
                    try:
                        import stat
                        fpath.chmod(fpath.stat().st_mode | stat.S_IEXEC)
                    except Exception:
                        pass
                changes.append(f"wrote {path}")
            except Exception as e:
                changes.append(f"error writing {pf.get('path')}: {e}")
        return changes

    def _execute_with_e8_benchmark(self, task: Dict) -> Dict:
        """Execute task using E8 Benchmark Agent"""
        try:
            agent = self._ensure_e8_benchmark()
            result = agent.execute(task)
            return result
        except Exception as e:
            return {"status": "error", "error": f"e8_benchmark_failed: {str(e)}"}

    def _ensure_pim_kernel(self):
        """Lazy-load PIM Kernel + Graph feature toolkit"""
        if self._pim_kernel is None:
            try:
                from qa_pim.kernels import RESIDUE_SELECT, RADD_m, ROLLING_SUM_PHASE
                from qa_pim.graph import build_sector_csr, neighbor_expand
                from qa_pim.schema import QAParams
                from qa_graph.feature_map import qa_feature_vector, CANONICAL_21
                self._pim_kernel = {
                    'RESIDUE_SELECT': RESIDUE_SELECT,
                    'RADD_m': RADD_m,
                    'ROLLING_SUM_PHASE': ROLLING_SUM_PHASE,
                    'build_sector_csr': build_sector_csr,
                    'neighbor_expand': neighbor_expand,
                    'qa_feature_vector': qa_feature_vector,
                    'CANONICAL_21': CANONICAL_21,
                    'QAParams': QAParams,
                }
                print("✓ PIM Kernel Agent loaded")
            except Exception as e:
                print(f"⚠️ PIM Kernel Agent loading failed: {e}")
                self._pim_kernel = {}
        return self._pim_kernel

    def _execute_with_pim_kernel(self, task: Dict) -> Dict:
        """Execute task using PIM Kernel Agent (sector filtering, graph analysis, feature extraction)"""
        try:
            toolkit = self._ensure_pim_kernel()
            if not toolkit:
                return {"status": "error", "error": "pim_kernel not available"}
            task_id = task.get('id', 'unknown')
            title = (task.get('title', '') or '').lower()

            if 'sector' in title or 'residue' in title:
                return {"status": "ok", "task_id": task_id, "task_type": "sector_analysis",
                        "available": ['RESIDUE_SELECT', 'build_sector_csr', 'neighbor_expand']}
            elif 'feature' in title or 'qa21' in title:
                return {"status": "ok", "task_id": task_id, "task_type": "feature_extraction",
                        "available": ['qa_feature_vector'], "modes": ["qa21", "qa27", "qa83"]}
            else:
                return {"status": "ok", "task_id": task_id, "task_type": "pim_kernel",
                        "available": list(toolkit.keys())}
        except Exception as e:
            return {"status": "error", "error": f"pim_kernel_failed: {str(e)}"}

    def _execute_with_external_cmd(self, cmd: Optional[str], task: Dict, agent_name: str) -> Dict:
        """Execute task by calling an external command that accepts JSON on stdin and returns JSON on stdout.

        The command is taken as a shell string (respects quoted args). If not provided, returns a deferred result.
        """
        if not cmd:
            return {"status": "deferred", "reason": f"no command configured for {agent_name}", "agent": agent_name}

        # Build payload. If using collab_broadcast, emit the expected event_type/data
        basename = os.path.basename(cmd) if cmd else ""
        if basename == "collab_broadcast":
            payload = {
                "event_type": f"{agent_name}.execute",
                "data": {
                    "task": task,
                    "task_id": task.get("id"),
                    "source": "qa_lab",
                },
            }
        else:
            payload = {
                "task": task,
                "base_dir": str(_BASE_DIR),
                "mode": "execute",
                "agent": agent_name,
            }

        try:
            proc = subprocess.run(
                shlex.split(cmd),
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=int(os.getenv("QA_EXT_TIMEOUT", "120")),
                cwd=str(_BASE_DIR),
            )
        except Exception as e:
            return {"status": "error", "error": f"spawn_failed: {e}", "agent": agent_name}

        if proc.returncode != 0:
            return {"status": "error", "error": f"nonzero_exit:{proc.returncode}", "stderr": proc.stderr[-4000:], "agent": agent_name}

        try:
            data = json.loads(proc.stdout.strip() or "{}")
        except Exception as e:
            return {"status": "error", "error": f"invalid_json: {e}", "stdout": proc.stdout[-4000:], "agent": agent_name}

        # Normalize and apply any proposed_files from external result
        data.setdefault("agent", agent_name)
        data.setdefault("status", "ok")
        proposed = data.get('proposed_files') or []
        if isinstance(proposed, list) and proposed:
            applied = self._apply_files_from_list(proposed)
            if applied:
                data['applied_changes'] = len(applied)
                # Broadcast for observability
                collab_broadcast("execute.applied_changes", {"count": len(applied), "task_id": task.get('id')})
        return data

    def _execute_with_opencode(self, task: Dict) -> Dict:
        """Perform small, safe code operations for common maintenance tasks."""
        title = (task.get("title") or "").lower()
        changes: List[str] = []

        # Initialize mkdocs documentation if requested
        if ("documentation" in title or "docs" in title) and True:
            mkdocs_yml = _BASE_DIR / "mkdocs.yml"
            docs_dir = _BASE_DIR / "qa_docs"
            index_md = docs_dir / "index.md"

            if not mkdocs_yml.exists():
                mkdocs_yml.write_text(
                    """
site_name: QA Lab
repo_url: https://example.local/qa_lab
docs_dir: qa_docs
theme:
  name: material
nav:
  - Home: index.md
  - Agents:
      - Runs: agents/runs.md
""".strip()
                    + "\n",
                    encoding="utf-8",
                )
                changes.append("created mkdocs.yml")

            docs_dir.mkdir(parents=True, exist_ok=True)
            index_md.parent.mkdir(parents=True, exist_ok=True)
            if not index_md.exists():
                index_md.write_text(
                    """
# QA Lab Documentation

Welcome to the QA Bob-iverse Autonomic Research Lab.

- Pipeline: scout → prioritize → plan → dispatch → executor → review → archive
- Model: QALM with invariant-aware attention.

Use `mkdocs build` to render this site.
""".strip()
                    + "\n",
                    encoding="utf-8",
                )
                changes.append("created qa_docs/index.md")

        # apply_proposed_files handled earlier; retain 'changes' for return structure

        # Summarize TODO/FIXME counts (non-destructive)
        if title.startswith("address todo/fixme in "):
            filename = title.replace("address todo/fixme in ", "").strip()
            report_dir = self.logs_dir / "opencode_actions"
            report_dir.mkdir(exist_ok=True)
            matches = []
            for root in [
                _BASE_DIR / "qa_agents",
                _BASE_DIR / "qa_core",
                _BASE_DIR / "projects",
                _BASE_DIR / "scripts",
            ]:
                for f in root.rglob(filename):
                    try:
                        text = f.read_text(encoding="utf-8")
                    except Exception:
                        continue
                    count = text.count("TODO") + text.count("FIXME")
                    matches.append({"path": str(f.relative_to(_BASE_DIR)), "count": count})
            report = {"file": filename, "occurrences": matches}
            (report_dir / f"{task.get('id','task')}.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            changes.append("wrote TODO report")

        # Lightweight refactor: normalize whitespace and ensure module docstring
        if title.startswith("refactor ") or title.startswith("refactor:") or "refactor" in title:
            import re
            target = None
            # Try to extract filename from title
            parts = title.replace("refactor:", "refactor ").split()
            for p in parts:
                if p.endswith('.py'):
                    target = p
                    break
            if target:
                fpath = _BASE_DIR / target
                try:
                    text = fpath.read_text(encoding='utf-8')
                    original = text
                    # Strip trailing spaces
                    text = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
                    # Ensure final newline
                    if not text.endswith("\n"):
                        text += "\n"
                    # Ensure module docstring
                    if not re.match(r"^\s*\"\"\"", text):
                        header = f'"""\nRefactored module: {target}\n"""\n\n'
                        text = header + text
                    if text != original:
                        fpath.write_text(text, encoding='utf-8')
                        changes.append(f"refactored {target}")
                except Exception as e:
                    changes.append(f"refactor_error {target}: {e}")

        result = {
            "agent": "opencode",
            "changes": changes or ["no-op"],
        }
        # Broadcast applied changes for observability
        if changes:
            collab_broadcast("execute.applied_changes", {"count": len(changes), "task_id": task.get('id')})
        return result


if __name__ == "__main__":
    QAExecutor().run()
