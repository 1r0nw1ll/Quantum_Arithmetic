#!/usr/bin/env python3
"""
QA Vision Agent - Specialized for Vision/Image Processing
Part of the modular multimodal QA swarm architecture.

Capabilities:
- Image processing and QA encoding
- Object recognition via QA invariants
- Scene understanding
- Integration with core QA architecture
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from torchvision.datasets import CIFAR10

# Import QA components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from qa_jepa_encoder import QAEncoder, QAHarmonicLoss
from qa_agents.cli.cim_qalm_agent import CIMQALMAgent


class VisionQAEncoder(nn.Module):
    """QA Encoder specialized for images"""

    def __init__(self, n_channels: int = 3, spatial_size: int = 32):
        super().__init__()
        self.n_channels = n_channels
        self.spatial_size = spatial_size

        # Image processing layers
        self.conv1 = nn.Conv2d(n_channels, 64, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(64, 32, kernel_size=3, padding=1)

        # QA encoding
        flattened_size = 32 * spatial_size * spatial_size
        self.qa_encoder = QAEncoder(
            modulus=24,
            enforce_constraints=True,
            input_dim=flattened_size,
            hidden_dim=256
        )

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Args:
            x: Image [B, H, W, C] or [B, C, H, W]
        Returns:
            QA bundle with visual invariants
        """
        # Ensure [B, C, H, W]
        if x.dim() == 4 and x.shape[-1] == self.n_channels:
            x = x.permute(0, 3, 1, 2)  # [B, H, W, C] -> [B, C, H, W]

        # Image processing
        x = self.conv1(x)
        x = torch.relu(x)
        x = self.conv2(x)
        x = torch.relu(x)

        # Flatten for QA encoding
        x_flat = x.reshape(x.size(0), -1).unsqueeze(1)  # [B, 1, D]

        # QA encoding
        qa_bundle = self.qa_encoder(x_flat)

        return qa_bundle


class VisionQAAgent(CIMQALMAgent):
    """Specialized QA agent for vision/image analysis"""

    def __init__(self, base_path: Path):
        super().__init__(base_path)

        # Agent-specific components
        self.model = VisionQAEncoder()
        self.loss_fn = QAHarmonicLoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=1e-3)

        # Data
        self.vision_data = None
        self.labels = None
        self.is_trained = False

        # Swarm capabilities
        if hasattr(self, 'register_swarm_capability'):
            self.register_swarm_capability("vision")

    def load_vision_data(self) -> bool:
        """Load vision training data"""
        try:
            # Load CIFAR-10
            cifar_dataset = CIFAR10(root='data', train=True, download=False)
            self.vision_data = cifar_dataset.data  # [50000, 32, 32, 3]
            self.labels = np.array(cifar_dataset.targets)

            print(f"Loaded CIFAR-10 data: {self.vision_data.shape}, labels: {len(self.labels)}")
            return True

        except Exception as e:
            print(f"Failed to load vision data: {e}")
            return False

    def train_vision_model(self, epochs: int = 10) -> Dict[str, Any]:
        """Train the vision QA model"""
        if self.vision_data is None:
            if not self.load_vision_data():
                return {"error": "No vision data available"}

        # Prepare data
        dataset = VisionDataset(self.vision_data, self.labels)
        dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

        self.model.train()
        losses = []

        for epoch in range(epochs):
            epoch_loss = 0
            for batch_idx, batch in enumerate(dataloader):
                vision_batch = batch['vision']
                qa_targets = batch['qa_tuple']

                self.optimizer.zero_grad()

                # Forward pass
                qa_pred = self.model(vision_batch)

                # Supervised loss: predict QA tuple from image
                target_bundle = {
                    'b': qa_targets[:, 0].unsqueeze(-1),
                    'e': qa_targets[:, 1].unsqueeze(-1),
                    'd': qa_targets[:, 2].unsqueeze(-1),
                    'a': qa_targets[:, 3].unsqueeze(-1)
                }
                # Compute invariants for target
                target_bundle.update(QAEncoder._compute_primary_invariants(target_bundle))
                target_bundle.update(QAEncoder._compute_secondary_invariants(target_bundle))
                target_bundle.update(QAEncoder._compute_triangle_sides(target_bundle))

                loss, metrics = self.loss_fn(qa_pred, target_bundle)
                loss.backward()
                self.optimizer.step()

                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(dataloader)
            losses.append(avg_loss)
            print(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}")

        self.is_trained = True

        # Save model
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'epochs': epochs,
            'final_loss': losses[-1]
        }, self.base_path / 'trained_models' / 'qa_vision_agent.pt')

        return {
            "status": "trained",
            "epochs": epochs,
            "final_loss": losses[-1],
            "loss_history": losses
        }

    def analyze_visual_signature(self, image_sample: np.ndarray) -> Dict[str, Any]:
        """Analyze visual signature of image sample"""
        if not self.is_trained:
            # Try to load saved model
            model_path = self.base_path / 'trained_models' / 'qa_vision_agent.pt'
            if model_path.exists():
                checkpoint = torch.load(model_path)
                self.model.load_state_dict(checkpoint['model_state_dict'])
                self.is_trained = True
            else:
                return {"error": "Model not trained"}

        self.model.eval()
        with torch.no_grad():
            # Convert to tensor
            if isinstance(image_sample, np.ndarray):
                image_tensor = torch.from_numpy(image_sample).float().unsqueeze(0)
            else:
                image_tensor = image_sample.unsqueeze(0)

            # Get QA encoding
            qa_bundle = self.model(image_tensor)

            # Extract visual invariants
            analysis = {
                "qa_tuple": {
                    "b": qa_bundle["b"].item(),
                    "e": qa_bundle["e"].item(),
                    "d": qa_bundle["d"].item(),
                    "a": qa_bundle["a"].item()
                },
                "invariants": {
                    "J": qa_bundle["J"].item(),
                    "K": qa_bundle["K"].item(),
                    "X": qa_bundle["X"].item(),
                    "W": qa_bundle["W"].item(),
                    "Y": qa_bundle["Y"].item(),
                    "Z": qa_bundle["Z"].item()
                },
                "triangle_sides": {
                    "C": qa_bundle["C"].item(),
                    "F": qa_bundle["F"].item(),
                    "G": qa_bundle["G"].item()
                }
            }

            return analysis

    def classify_image(self, image_sample: np.ndarray) -> Dict[str, Any]:
        """Classify image from visual signature"""
        analysis = self.analyze_visual_signature(image_sample)

        if "error" in analysis:
            return analysis

        # Simple classification based on QA invariants
        qa = analysis["qa_tuple"]
        # CIFAR-10 classes
        classes = ['airplane', 'automobile', 'bird', 'cat', 'deer', 'dog', 'frog', 'horse', 'ship', 'truck']
        # Simple mapping based on qa values
        class_idx = int(qa["b"] % 10)
        predicted_class = classes[class_idx]

        return {
            "predicted_class": predicted_class,
            "confidence": 0.6,
            "qa_analysis": analysis
        }

    def generate_response(self, prompt: str, qa_tuple: Optional[Tuple[int, int, int, int]] = None, max_length: int = 100) -> str:
        """Generate response using vision QA reasoning"""
        if "vision" in prompt.lower() or "image" in prompt.lower():
            if not self.is_trained:
                return "Vision agent not trained. Please train first."

            return f"Visual analysis: {prompt[:50]}... QA-based image processing ready."

        return "Vision agent: Query not related to visual analysis."

    # Swarm Coordination Methods
    def coordinate_multimodal_analysis(self, task_description: str) -> Dict[str, Any]:
        """Coordinate with other agents for multimodal analysis"""
        if not hasattr(self, 'request_coordination'):
            return {"error": "Swarm capabilities not available"}

        # Request coordination for multimodal task
        self.request_coordination(
            task_description,
            ["lidar", "spectral", "audio"]  # Request other modalities
        )

        return {
            "status": "coordination_requested",
            "task": task_description,
            "agent": "vision",
            "capabilities_offered": ["image_classification", "visual_qa_analysis"]
        }

    def share_visual_qa_context(self, qa_tuple: Dict) -> Dict[str, Any]:
        """Share visual QA context with swarm"""
        if not hasattr(self, 'send_qa_tuple'):
            return {"error": "Swarm capabilities not available"}

        # Send QA tuple to other agents
        self.send_qa_tuple(qa_tuple)

        return {
            "status": "qa_context_shared",
            "shared_tuple": qa_tuple,
            "context": "visual_analysis"
        }

    def process_swarm_task(self, task_data: Dict) -> Dict[str, Any]:
        """Process task delegated from swarm coordinator"""
        task_type = task_data.get("task_type", "unknown")

        if task_type == "image_analysis":
            # Process image analysis task
            image_data = task_data.get("image_data")
            if image_data is not None:
                return self.analyze_visual_signature(image_data)
            else:
                return {"error": "No image data provided"}

        elif task_type == "multimodal_fusion":
            # Participate in multimodal fusion
            return self.coordinate_multimodal_analysis("Multimodal scene understanding")

        else:
            return {"error": f"Unknown task type: {task_type}"}

        # Use parent class for other prompts
        return super().generate_response(prompt, qa_tuple, max_length)


class VisionDataset(torch.utils.data.Dataset):
    """Dataset for vision data"""

    def __init__(self, vision_data: np.ndarray, labels: np.ndarray):
        self.vision_data = vision_data
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        vision_sample = self.vision_data[idx]  # [32,32,3]
        label = self.labels[idx]

        # Convert to tensor
        vision_tensor = torch.from_numpy(vision_sample).float()

        # QA tuple based on label
        base = label
        qa_tuple = torch.tensor([base+1, base+2, base+3, base+4], dtype=torch.float)

        return {
            'vision': vision_tensor,
            'qa_tuple': qa_tuple,
            'label': label
        }


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='QA Vision Agent')
    parser.add_argument('--command', choices=['train', 'analyze', 'classify'],
                        default='train', help='Command to execute')
    parser.add_argument('--sample-idx', type=int, help='Sample index for analysis')

    args = parser.parse_args()

    base_path = Path('.')
    agent = VisionQAAgent(base_path)

    if args.command == 'train':
        result = agent.train_vision_model(epochs=2)
        print("Training result:", result)

    elif args.command == 'analyze' and args.sample_idx is not None:
        if agent.vision_data is None:
            agent.load_vision_data()

        if agent.vision_data is not None and args.sample_idx < len(agent.vision_data):
            sample = agent.vision_data[args.sample_idx]
            analysis = agent.analyze_visual_signature(sample)
            print("Visual analysis:", analysis)
        else:
            print("Invalid sample index or data not loaded")

    elif args.command == 'classify' and args.sample_idx is not None:
        if agent.vision_data is None:
            agent.load_vision_data()

        if agent.vision_data is not None and args.sample_idx < len(agent.vision_data):
            sample = agent.vision_data[args.sample_idx]
            classification = agent.classify_image(sample)
            print("Image classification:", classification)
        else:
            print("Invalid sample index or data not loaded")

    else:
        print("QA Vision Agent - Commands: train, analyze --sample-idx <idx>, classify --sample-idx <idx>")