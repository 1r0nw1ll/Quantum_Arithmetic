#!/usr/bin/env python3
"""
QA LIDAR Agent - Specialized for LIDAR Point Cloud Processing
Part of the modular multimodal QA swarm architecture.

Capabilities:
- LIDAR point cloud processing and QA encoding
- 3D spatial analysis
- Object detection and tracking via QA invariants
- Integration with core QA architecture
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from scipy.io import loadmat

# Import QA components
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from qa_jepa_encoder import QAEncoder, QAHarmonicLoss
from qa_agents.cli.cim_qalm_agent import CIMQALMAgent


class LidarQAEncoder(nn.Module):
    """QA Encoder specialized for LIDAR point clouds"""

    def __init__(self, n_points: int = 1024, n_features: int = 3):
        super().__init__()
        self.n_points = n_points
        self.n_features = n_features

        # Point cloud processing layers
        self.point_conv = nn.Conv1d(n_features, 64, kernel_size=1)
        self.spatial_conv = nn.Conv1d(64, 32, kernel_size=1)

        # QA encoding
        flattened_size = 32 * n_points
        self.qa_encoder = QAEncoder(
            modulus=24,
            enforce_constraints=True,
            input_dim=flattened_size,
            hidden_dim=256
        )

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Args:
            x: Point cloud [B, N, C] or [B, C, N]
        Returns:
            QA bundle with spatial invariants
        """
        # Ensure [B, C, N]
        if x.dim() == 3 and x.shape[-1] == self.n_features:
            x = x.permute(0, 2, 1)  # [B, N, C] -> [B, C, N]

        # Point processing
        x = self.point_conv(x)  # [B, 64, N]
        x = torch.relu(x)
        x = self.spatial_conv(x)  # [B, 32, N]
        x = torch.relu(x)

        # Flatten for QA encoding
        x_flat = x.reshape(x.size(0), -1).unsqueeze(1)  # [B, 1, D]

        # QA encoding
        qa_bundle = self.qa_encoder(x_flat)

        return qa_bundle


class LidarQAAgent(CIMQALMAgent):
    """Specialized QA agent for LIDAR point cloud analysis"""

    def __init__(self, base_path: Path):
        super().__init__(base_path)

        # Agent-specific components
        self.model = LidarQAEncoder()
        self.loss_fn = QAHarmonicLoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=1e-3)

        # Data
        self.lidar_data = None
        self.labels = None
        self.is_trained = False

    def load_lidar_data(self) -> bool:
        """Load LIDAR training data"""
        try:
            data_path = Path('multimodal_data')
            if not data_path.exists():
                print("LIDAR data not found")
                return False

            # Load LIDAR and labels
            lidar_mat = loadmat(data_path / 'LIDAR_Tr.mat')
            label_mat = loadmat(data_path / 'TrLabel.mat')

            # Extract data
            lidar_key = list(lidar_mat.keys())[-1]
            label_key = list(label_mat.keys())[-1]

            self.lidar_data = lidar_mat[lidar_key]  # [N, H, W, C] or point cloud format
            self.labels = label_mat[label_key].flatten()

            print(f"Loaded LIDAR data: {self.lidar_data.shape}, labels: {len(self.labels)}")
            return True

        except Exception as e:
            print(f"Failed to load LIDAR data: {e}")
            return False

    def train_lidar_model(self, epochs: int = 10) -> Dict[str, Any]:
        """Train the LIDAR QA model"""
        if self.lidar_data is None:
            if not self.load_lidar_data():
                return {"error": "No LIDAR data available"}

        # Prepare data
        dataset = LidarDataset(self.lidar_data, self.labels)
        dataloader = DataLoader(dataset, batch_size=8, shuffle=True)

        self.model.train()
        losses = []

        for epoch in range(epochs):
            epoch_loss = 0
            for batch_idx, batch in enumerate(dataloader):
                lidar_batch = batch['lidar']
                qa_targets = batch['qa_tuple']

                self.optimizer.zero_grad()

                # Forward pass
                qa_pred = self.model(lidar_batch)

                # Supervised loss: predict QA tuple from LIDAR
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
        }, self.base_path / 'trained_models' / 'qa_lidar_agent.pt')

        return {
            "status": "trained",
            "epochs": epochs,
            "final_loss": losses[-1],
            "loss_history": losses
        }

    def analyze_spatial_signature(self, lidar_sample: np.ndarray) -> Dict[str, Any]:
        """Analyze spatial signature of LIDAR sample"""
        if not self.is_trained:
            # Try to load saved model
            model_path = self.base_path / 'trained_models' / 'qa_lidar_agent.pt'
            if model_path.exists():
                checkpoint = torch.load(model_path)
                self.model.load_state_dict(checkpoint['model_state_dict'])
                self.is_trained = True
            else:
                return {"error": "Model not trained"}

        self.model.eval()
        with torch.no_grad():
            # Convert to tensor
            if isinstance(lidar_sample, np.ndarray):
                lidar_tensor = torch.from_numpy(lidar_sample).float().unsqueeze(0)
            else:
                lidar_tensor = lidar_sample.unsqueeze(0)

            # Get QA encoding
            qa_bundle = self.model(lidar_tensor)

            # Extract spatial invariants
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

    def detect_objects(self, lidar_sample: np.ndarray) -> Dict[str, Any]:
        """Detect objects from LIDAR spatial signature"""
        analysis = self.analyze_spatial_signature(lidar_sample)

        if "error" in analysis:
            return analysis

        # Simple classification based on QA invariants
        qa = analysis["qa_tuple"]
        object_classes = {
            "vehicle": qa["b"] > 3.0,
            "pedestrian": qa["e"] > 2.0,
            "building": qa["d"] > 5.0,
            "vegetation": qa["a"] > 8.0
        }

        detected_objects = [obj for obj, condition in object_classes.items() if condition]

        return {
            "detected_objects": detected_objects if detected_objects else ["unknown"],
            "confidence": 0.7,
            "qa_analysis": analysis
        }

    def generate_response(self, prompt: str, qa_tuple: Optional[Tuple[int, int, int, int]] = None, max_length: int = 100) -> str:
        """Generate response using LIDAR QA reasoning"""
        if "lidar" in prompt.lower() or "point" in prompt.lower():
            if not self.is_trained:
                return "LIDAR agent not trained. Please train first."

            return f"Spatial analysis: {prompt[:50]}... QA-based 3D point cloud processing ready."

        # Use parent class for other prompts
        return super().generate_response(prompt, qa_tuple, max_length)


class LidarDataset(torch.utils.data.Dataset):
    """Dataset for LIDAR data"""

    def __init__(self, lidar_data: np.ndarray, labels: np.ndarray):
        self.lidar_data = lidar_data
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        lidar_sample = self.lidar_data[idx]  # Assume [H, W, C] or point cloud
        label = self.labels[idx]

        # Convert to tensor - assume it's already point cloud format
        lidar_tensor = torch.from_numpy(lidar_sample).float()

        # QA tuple based on label
        base = label.item()
        qa_tuple = torch.tensor([base, base+1, base+2, base+3], dtype=torch.float)

        return {
            'lidar': lidar_tensor,
            'qa_tuple': qa_tuple,
            'label': label
        }


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='QA LIDAR Agent')
    parser.add_argument('--command', choices=['train', 'analyze', 'detect'],
                        default='train', help='Command to execute')
    parser.add_argument('--sample-idx', type=int, help='Sample index for analysis')

    args = parser.parse_args()

    base_path = Path('.')
    agent = LidarQAAgent(base_path)

    if args.command == 'train':
        result = agent.train_lidar_model(epochs=2)
        print("Training result:", result)

    elif args.command == 'analyze' and args.sample_idx is not None:
        if agent.lidar_data is None:
            agent.load_lidar_data()

        if agent.lidar_data is not None and args.sample_idx < len(agent.lidar_data):
            sample = agent.lidar_data[args.sample_idx]
            analysis = agent.analyze_spatial_signature(sample)
            print("Spatial analysis:", analysis)
        else:
            print("Invalid sample index or data not loaded")

    elif args.command == 'detect' and args.sample_idx is not None:
        if agent.lidar_data is None:
            agent.load_lidar_data()

        if agent.lidar_data is not None and args.sample_idx < len(agent.lidar_data):
            sample = agent.lidar_data[args.sample_idx]
            detection = agent.detect_objects(sample)
            print("Object detection:", detection)
        else:
            print("Invalid sample index or data not loaded")

    else:
        print("QA LIDAR Agent - Commands: train, analyze --sample-idx <idx>, detect --sample-idx <idx>")
