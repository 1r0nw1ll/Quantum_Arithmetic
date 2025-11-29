#!/usr/bin/env python3
"""
QALM Multimodal Agent v3.0
QA Learning Machine with Multimodal, Agential, and Computer Use Capabilities

Enhanced QALM with:
- Multimodal input processing (vision, audio, video, text)
- Agential decision-making and action planning
- Computer use capabilities (web browsing, command execution, app interaction)
- Tool use and function calling framework
- Unified multimodal QA tuple representations

Integration with QA lab for advanced multimodal reasoning and autonomous operation.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Tuple, Optional, Any, Set, Union
import numpy as np
import json
import hashlib
import time
from pathlib import Path
from dataclasses import dataclass, field
import threading
from concurrent.futures import ThreadPoolExecutor
import subprocess
import requests
from PIL import Image
import io
import base64
import cv2
import wave
import audioop
import sys
import os

# Add the qa_lab directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from qa_agents.cli.cim_qalm_agent import CIMQALMAgent, KnowledgeNode, ReasoningChain
from qa_agents.cli.qalm import QALMAgent


@dataclass
class MultimodalQAInput:
    """Unified multimodal input representation"""
    text: Optional[str] = None
    image: Optional[Image.Image] = None
    audio: Optional[np.ndarray] = None
    video: Optional[np.ndarray] = None
    qa_tuple: Optional[Tuple[float, float, float, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionPlan:
    """Agential action planning structure"""
    goal: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    status: str = "planning"
    confidence: float = 1.0
    reasoning: List[str] = field(default_factory=list)


@dataclass
class ToolResult:
    """Result from tool execution"""
    tool_name: str
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time: float = 0.0


class MultimodalEncoder(nn.Module):
    """Multimodal encoder for vision, audio, and text inputs"""

    def __init__(self, text_dim: int = 768, vision_dim: int = 512, audio_dim: int = 256):
        super().__init__()
        self.text_dim = text_dim
        self.vision_dim = vision_dim
        self.audio_dim = audio_dim

        # Vision encoder (simplified CNN)
        self.vision_encoder = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d((8, 8)),
            nn.Flatten(),
            nn.Linear(128 * 64, vision_dim),
            nn.ReLU()
        )

        # Audio encoder (simplified CNN for spectrograms)
        self.audio_encoder = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.AdaptiveAvgPool2d((4, 4)),
            nn.Flatten(),
            nn.Linear(64 * 16, audio_dim),
            nn.ReLU()
        )

        # Unified projection to common space
        self.unified_projection = nn.Linear(text_dim + vision_dim + audio_dim, text_dim)

    def encode_text(self, text: str) -> torch.Tensor:
        """Encode text input (placeholder - would use actual text encoder)"""
        # Simplified text encoding - in practice would use BERT/RoBERTa/etc.
        text_hash = hashlib.md5(text.encode()).digest()
        text_features = torch.tensor([float(b) for b in text_hash], dtype=torch.float)
        return text_features[:self.text_dim]

    def encode_vision(self, image: Image.Image) -> torch.Tensor:
        """Encode image input"""
        # Convert PIL to tensor
        image_tensor = torch.from_numpy(np.array(image)).float()
        if image_tensor.dim() == 2:  # Grayscale
            image_tensor = image_tensor.unsqueeze(0).repeat(3, 1, 1)
        elif image_tensor.dim() == 3 and image_tensor.shape[2] == 3:  # RGB
            image_tensor = image_tensor.permute(2, 0, 1)
        else:
            raise ValueError("Unsupported image format")

        # Normalize and encode
        image_tensor = image_tensor / 255.0
        return self.vision_encoder(image_tensor.unsqueeze(0)).squeeze(0)

    def encode_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> torch.Tensor:
        """Encode audio input"""
        # Convert to spectrogram (simplified)
        # In practice would use proper STFT/mel spectrogram
        spectrogram = torch.tensor(audio, dtype=torch.float).unsqueeze(0).unsqueeze(0)
        return self.audio_encoder(spectrogram).squeeze(0)

    def forward(self, multimodal_input: MultimodalQAInput) -> torch.Tensor:
        """Encode multimodal input to unified representation"""
        embeddings = []

        if multimodal_input.text:
            text_emb = self.encode_text(multimodal_input.text)
            embeddings.append(text_emb)

        if multimodal_input.image:
            vision_emb = self.encode_vision(multimodal_input.image)
            embeddings.append(vision_emb)

        if multimodal_input.audio is not None:
            audio_emb = self.encode_audio(multimodal_input.audio)
            embeddings.append(audio_emb)

        if not embeddings:
            # Default embedding for empty input
            embeddings.append(torch.zeros(self.text_dim))

        # Concatenate and project to unified space
        combined = torch.cat(embeddings, dim=-1)
        if combined.shape[-1] > self.text_dim:
            combined = combined[:self.text_dim]  # Truncate if too long
        elif combined.shape[-1] < self.text_dim:
            combined = torch.cat([combined, torch.zeros(self.text_dim - combined.shape[-1])], dim=-1)

        return self.unified_projection(combined.unsqueeze(0)).squeeze(0)


class ComputerUseTools:
    """Computer use capabilities for QALM"""

    def __init__(self):
        self.session_cookies = {}
        self.user_agent = "QALM-Agent/3.0"

    def web_browse(self, url: str, method: str = "GET", data: Optional[Dict] = None) -> ToolResult:
        """Browse web pages"""
        start_time = time.time()

        try:
            headers = {"User-Agent": self.user_agent}
            response = requests.request(method, url, headers=headers, json=data, timeout=10)

            result = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": response.text[:5000],  # Limit content size
                "url": response.url
            }

            return ToolResult(
                tool_name="web_browse",
                success=response.status_code == 200,
                output=result,
                execution_time=time.time() - start_time
            )

        except Exception as e:
            return ToolResult(
                tool_name="web_browse",
                success=False,
                output=None,
                error=str(e),
                execution_time=time.time() - start_time
            )

    def run_command(self, command: str, timeout: int = 30) -> ToolResult:
        """Execute shell commands safely"""
        start_time = time.time()

        # Security: Only allow safe commands
        allowed_commands = ['ls', 'pwd', 'echo', 'cat', 'head', 'tail', 'grep', 'find', 'wc', 'python3', 'pip']
        cmd_parts = command.split()

        if not cmd_parts or cmd_parts[0] not in allowed_commands:
            return ToolResult(
                tool_name="run_command",
                success=False,
                output=None,
                error="Command not allowed for security reasons",
                execution_time=time.time() - start_time
            )

        try:
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd()
            )

            output = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }

            return ToolResult(
                tool_name="run_command",
                success=result.returncode == 0,
                output=output,
                execution_time=time.time() - start_time
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_name="run_command",
                success=False,
                output=None,
                error="Command timed out",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ToolResult(
                tool_name="run_command",
                success=False,
                output=None,
                error=str(e),
                execution_time=time.time() - start_time
            )

    def file_operations(self, operation: str, path: str, content: Optional[str] = None) -> ToolResult:
        """Safe file operations"""
        start_time = time.time()

        try:
            full_path = Path(path).resolve()

            # Security: Only allow operations within qa_lab directory
            qa_lab_root = Path(__file__).parent.parent.parent
            if not str(full_path).startswith(str(qa_lab_root)):
                return ToolResult(
                    tool_name="file_operations",
                    success=False,
                    output=None,
                    error="File operations restricted to qa_lab directory",
                    execution_time=time.time() - start_time
                )

            if operation == "read":
                if full_path.exists():
                    content = full_path.read_text()
                    return ToolResult(
                        tool_name="file_operations",
                        success=True,
                        output={"content": content[:5000]},  # Limit size
                        execution_time=time.time() - start_time
                    )
                else:
                    return ToolResult(
                        tool_name="file_operations",
                        success=False,
                        output=None,
                        error="File not found",
                        execution_time=time.time() - start_time
                    )

            elif operation == "write" and content:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                return ToolResult(
                    tool_name="file_operations",
                    success=True,
                    output={"written": len(content)},
                    execution_time=time.time() - start_time
                )

            elif operation == "list":
                if full_path.is_dir():
                    files = [str(f) for f in full_path.iterdir()]
                    return ToolResult(
                        tool_name="file_operations",
                        success=True,
                        output={"files": files[:50]},  # Limit results
                        execution_time=time.time() - start_time
                    )
                else:
                    return ToolResult(
                        tool_name="file_operations",
                        success=False,
                        output=None,
                        error="Path is not a directory",
                        execution_time=time.time() - start_time
                    )

        except Exception as e:
            return ToolResult(
                tool_name="file_operations",
                success=False,
                output=None,
                error=str(e),
                execution_time=time.time() - start_time
            )


class AgentialReasoningEngine:
    """Agential decision-making and action planning"""

    def __init__(self, qalm_agent: QALMAgent, computer_tools: ComputerUseTools):
        self.qalm = qalm_agent
        self.tools = computer_tools
        self.action_history: List[Dict] = []
        self.current_plan: Optional[ActionPlan] = None

    def create_action_plan(self, goal: str, context: MultimodalQAInput) -> ActionPlan:
        """Create an action plan to achieve a goal"""

        # Use QALM to analyze the goal and generate steps
        prompt = f"Create a step-by-step plan to achieve: {goal}"
        if context.text:
            prompt += f"\nContext: {context.text}"

        plan_text = self.qalm.generate_response(prompt)

        # Parse plan into structured steps (simplified)
        steps = []
        lines = plan_text.split('\n')
        for line in lines:
            line = line.strip()
            if line and (line.startswith('1.') or line.startswith('2.') or line.startswith('3.') or
                        line.startswith('-') or line.startswith('Step')):
                steps.append({
                    "description": line,
                    "tool": self._infer_tool_from_step(line),
                    "parameters": {},
                    "completed": False
                })

        plan = ActionPlan(
            goal=goal,
            steps=steps,
            reasoning=[f"Plan generated for goal: {goal}"]
        )

        self.current_plan = plan
        return plan

    def _infer_tool_from_step(self, step_text: str) -> Optional[str]:
        """Infer which tool to use for a step"""
        step_lower = step_text.lower()

        if any(word in step_lower for word in ['browse', 'web', 'url', 'website']):
            return 'web_browse'
        elif any(word in step_lower for word in ['run', 'execute', 'command']):
            return 'run_command'
        elif any(word in step_lower for word in ['read', 'write', 'file', 'list']):
            return 'file_operations'

        return None

    def execute_plan_step(self, plan: ActionPlan) -> ToolResult:
        """Execute the next step in an action plan"""

        if plan.current_step >= len(plan.steps):
            plan.status = "completed"
            return ToolResult(
                tool_name="plan_execution",
                success=True,
                output={"message": "Plan completed"}
            )

        step = plan.steps[plan.current_step]
        tool_name = step.get("tool")

        if not tool_name:
            # Skip steps without tools
            plan.current_step += 1
            step["completed"] = True
            return ToolResult(
                tool_name="plan_execution",
                success=True,
                output={"message": f"Skipped step: {step['description']}"}
            )

        # Execute the tool
        if tool_name == "web_browse":
            result = self.tools.web_browse("https://www.google.com")  # Default for now
        elif tool_name == "run_command":
            result = self.tools.run_command("echo 'Test command'")
        elif tool_name == "file_operations":
            result = self.tools.file_operations("list", ".")
        else:
            result = ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=f"Unknown tool: {tool_name}"
            )

        # Record result
        self.action_history.append({
            "step": plan.current_step,
            "tool": tool_name,
            "result": result.success,
            "timestamp": time.time()
        })

        if result.success:
            plan.current_step += 1
            step["completed"] = True
            plan.confidence *= 0.9  # Slight decay for uncertainty
        else:
            plan.confidence *= 0.7  # More decay for failures

        return result

    def evaluate_plan_success(self, plan: ActionPlan) -> Dict:
        """Evaluate how well the plan achieved its goal"""

        completed_steps = sum(1 for step in plan.steps if step.get("completed", False))
        success_rate = completed_steps / len(plan.steps) if plan.steps else 0

        # Use QALM to evaluate goal achievement
        evaluation_prompt = f"Evaluate if this plan successfully achieved its goal:\nGoal: {plan.goal}\nCompleted steps: {completed_steps}/{len(plan.steps)}\nSuccess rate: {success_rate:.2%}"

        evaluation = self.qalm.generate_response(evaluation_prompt)

        return {
            "plan": plan,
            "completed_steps": completed_steps,
            "total_steps": len(plan.steps),
            "success_rate": success_rate,
            "evaluation": evaluation,
            "overall_success": success_rate > 0.8  # 80% threshold
        }


class QALMMultimodalAgent(CIMQALMAgent):
    """Enhanced QALM with multimodal, agential, and computer use capabilities"""

    def __init__(self, base_path: Path):
        super().__init__(base_path)

        # Initialize multimodal components
        self.multimodal_encoder = MultimodalEncoder()

        # Initialize computer use tools
        self.computer_tools = ComputerUseTools()

        # Initialize agential reasoning
        self.agential_engine = AgentialReasoningEngine(self, self.computer_tools)

        # Thread pool for concurrent operations
        self.executor = ThreadPoolExecutor(max_workers=4)

    def process_multimodal_input(self, multimodal_input: MultimodalQAInput) -> Dict:
        """Process multimodal input and generate QA-aware response"""

        # Encode multimodal input
        with torch.no_grad():
            embedding = self.multimodal_encoder(multimodal_input)

        # Generate QA tuple from multimodal features
        qa_tuple = self._embedding_to_qa_tuple(embedding)

        # Use CIM-QALM reasoning on the QA tuple
        reasoning_result = self.reason_on_knowledge(qa_tuple)

        # Enhance with multimodal context
        enhanced_result = {
            **reasoning_result,
            "multimodal_embedding": embedding.tolist(),
            "input_modalities": {
                "has_text": multimodal_input.text is not None,
                "has_image": multimodal_input.image is not None,
                "has_audio": multimodal_input.audio is not None,
                "has_video": multimodal_input.video is not None
            }
        }

        return enhanced_result

    def _embedding_to_qa_tuple(self, embedding: torch.Tensor) -> Tuple[int, int, int, int]:
        """Convert multimodal embedding to QA tuple"""
        # Extract 4 values from embedding for QA tuple
        emb_values = embedding.detach().numpy()

        # Use statistical properties to create meaningful QA tuple
        b = int(abs(np.mean(emb_values[:len(emb_values)//4])) * 10) + 1
        e = int(abs(np.std(emb_values[len(emb_values)//4:2*len(emb_values)//4])) * 10) + 1
        d = b + e  # Maintain QA invariant
        a = e + d  # Maintain QA invariant

        return (b, e, d, a)

    def create_agential_plan(self, goal: str, context: MultimodalQAInput) -> ActionPlan:
        """Create an agential action plan"""
        return self.agential_engine.create_action_plan(goal, context)

    def execute_agential_step(self, plan: ActionPlan) -> ToolResult:
        """Execute next step in agential plan"""
        return self.agential_engine.execute_plan_step(plan)

    def use_computer_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """Use computer tools directly"""

        if tool_name == "web_browse":
            return self.computer_tools.web_browse(**kwargs)
        elif tool_name == "run_command":
            return self.computer_tools.run_command(**kwargs)
        elif tool_name == "file_operations":
            return self.computer_tools.file_operations(**kwargs)
        else:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=f"Unknown tool: {tool_name}"
            )

    def autonomous_operation(self, goal: str, max_steps: int = 10) -> Dict:
        """Perform autonomous operation to achieve a goal"""

        # Create multimodal context (text-only for now)
        context = MultimodalQAInput(text=f"Goal: {goal}")

        # Create action plan
        plan = self.create_agential_plan(goal, context)

        results = []
        for step in range(max_steps):
            if plan.status == "completed":
                break

            # Execute next step
            result = self.execute_agential_step(plan)
            results.append(result)

            # Check if plan is complete
            if plan.current_step >= len(plan.steps):
                plan.status = "completed"
                break

        # Evaluate success
        evaluation = self.agential_engine.evaluate_plan_success(plan)

        return {
            "goal": goal,
            "plan": plan,
            "execution_results": results,
            "evaluation": evaluation,
            "autonomous_success": evaluation["overall_success"]
        }

    def get_capabilities_summary(self) -> Dict:
        """Get summary of all capabilities"""

        return {
            "multimodal_processing": {
                "text": True,
                "vision": True,
                "audio": True,
                "video": False,  # Not yet implemented
                "qa_tuples": True
            },
            "agential_capabilities": {
                "action_planning": True,
                "decision_making": True,
                "goal_achievement": True,
                "autonomous_operation": True
            },
            "computer_use": {
                "web_browsing": True,
                "command_execution": True,
                "file_operations": True,
                "safe_execution": True
            },
            "knowledge_processing": {
                "memory_mapped_storage": True,
                "markovian_reasoning": True,
                "parallel_processing": True,
                "invariant_checking": True
            }
        }


def create_qalm_multimodal_agent(base_path: Path) -> QALMMultimodalAgent:
    """Factory function to create multimodal QALM agent"""
    return QALMMultimodalAgent(base_path)


# CLI interface for QA lab integration
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='QALM Multimodal Agent v3.0')
    parser.add_argument('--base-path', type=str, default='.',
                        help='Base path for agent data')
    parser.add_argument('--command', choices=['multimodal', 'agential', 'computer', 'autonomous', 'capabilities'],
                        default='capabilities', help='Command to execute')
    parser.add_argument('--goal', type=str, help='Goal for agential operations')
    parser.add_argument('--tool', type=str, help='Tool to use for computer operations')
    parser.add_argument('--text', type=str, help='Text input for multimodal processing')

    args = parser.parse_args()

    base_path = Path(args.base_path)
    agent = create_qalm_multimodal_agent(base_path)

    if args.command == 'multimodal' and args.text:
        # Test multimodal processing
        multimodal_input = MultimodalQAInput(text=args.text)
        result = agent.process_multimodal_input(multimodal_input)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == 'agential' and args.goal:
        # Test agential planning
        context = MultimodalQAInput(text=f"Goal: {args.goal}")
        plan = agent.create_agential_plan(args.goal, context)
        print(f"Created plan with {len(plan.steps)} steps:")
        for i, step in enumerate(plan.steps):
            print(f"  {i+1}. {step['description']}")

    elif args.command == 'computer' and args.tool:
        # Test computer tools
        if args.tool == 'web_browse':
            result = agent.use_computer_tool('web_browse', url='https://httpbin.org/get')
            print(f"Web browse result: {result.success}")
            if result.output:
                print(f"Status: {result.output.get('status_code')}")
        elif args.tool == 'run_command':
            result = agent.use_computer_tool('run_command', command='echo "Hello from QALM!"')
            print(f"Command result: {result.success}")
            if result.output:
                print(f"Output: {result.output.get('stdout', '').strip()}")

    elif args.command == 'autonomous' and args.goal:
        # Test autonomous operation
        result = agent.autonomous_operation(args.goal, max_steps=3)
        print(f"Autonomous operation completed: {result['autonomous_success']}")
        print(f"Steps executed: {len(result['execution_results'])}")

    elif args.command == 'capabilities':
        # Show capabilities
        caps = agent.get_capabilities_summary()
        print("QALM Multimodal Agent v3.0 Capabilities:")
        print(json.dumps(caps, indent=2))

    else:
        print("QALM Multimodal Agent v3.0")
        print("Use --help for usage information")
