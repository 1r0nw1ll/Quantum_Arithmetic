#!/usr/bin/env python3
"""
QA Spectral Agent - Specialized for Hyperspectral Imaging (HSI) Analysis
Part of the modular multimodal QA swarm architecture.

Capabilities:
- HSI data processing and QA encoding
- Spectral signature analysis
- Material classification via QA invariants
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


class SpectralQAEncoder(nn.Module):
    """QA Encoder specialized for hyperspectral data"""

    def __init__(self, n_bands: int = 144, spatial_size: int = 11):
        super().__init__()
        self.n_bands = n_bands
        self.spatial_size = spatial_size

        # Spectral processing layers
        self.spectral_conv = nn.Conv2d(n_bands, 64, kernel_size=1)  # 1x1 conv for spectral mixing
        self.spatial_conv = nn.Conv2d(64, 32, kernel_size=3, padding=1)

        # QA encoding
        flattened_size = 32 * spatial_size * spatial_size
        self.qa_encoder = QAEncoder(
            modulus=24,
            enforce_constraints=True,
            input_dim=flattened_size,
            hidden_dim=256  # Smaller for spectral agent
        )

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Args:
            x: HSI cube [B, H, W, C] or [B, C, H, W]
        Returns:
            QA bundle with spectral invariants
        """
        # Ensure [B, C, H, W]
        if x.dim() == 4 and x.shape[-1] == self.n_bands:
            x = x.permute(0, 3, 1, 2)  # [B, H, W, C] -> [B, C, H, W]

        # Spectral processing
        x = self.spectral_conv(x)  # [B, 64, H, W]
        x = torch.relu(x)
        x = self.spatial_conv(x)   # [B, 32, H, W]
        x = torch.relu(x)

        # Flatten for QA encoding
        x_flat = x.reshape(x.size(0), -1).unsqueeze(1)  # [B, 1, D]

        # QA encoding
        qa_bundle = self.qa_encoder(x_flat)

        return qa_bundle


class SpectralQAAgent(CIMQALMAgent):
    """Specialized QA agent for spectral/hyperspectral analysis"""

    def __init__(self, base_path: Path):
        super().__init__(base_path)

        # Agent-specific components
        self.model = SpectralQAEncoder()
        self.loss_fn = QAHarmonicLoss()
        self.optimizer = optim.Adam(self.model.parameters(), lr=1e-3)

        # Data
        self.hsi_data = None
        self.labels = None
        self.is_trained = False

    def load_hsi_data(self) -> bool:
        """Load HSI training data"""
        try:
            data_path = Path('multimodal_data')
            if not data_path.exists():
                print("HSI data not found")
                return False

            # Load HSI and labels
            hsi_mat = loadmat(data_path / 'HSI_Tr.mat')
            label_mat = loadmat(data_path / 'TrLabel.mat')

            # Extract data
            hsi_key = list(hsi_mat.keys())[-1]
            label_key = list(label_mat.keys())[-1]

            self.hsi_data = hsi_mat[hsi_key]  # [N, H, W, C]
            self.labels = label_mat[label_key].flatten()

            print(f"Loaded HSI data: {self.hsi_data.shape}, labels: {len(self.labels)}")
            return True

        except Exception as e:
            print(f"Failed to load HSI data: {e}")
            return False

    def train_spectral_model(self, epochs: int = 10) -> Dict[str, Any]:
        """Train the spectral QA model"""
        if self.hsi_data is None:
            if not self.load_hsi_data():
                return {"error": "No HSI data available"}

        # Prepare data
        dataset = HSIDataset(self.hsi_data, self.labels)
        dataloader = DataLoader(dataset, batch_size=8, shuffle=True)

        self.model.train()
        losses = []

        for epoch in range(epochs):
            epoch_loss = 0
            for batch_idx, batch in enumerate(dataloader):
                hsi_batch = batch['hsi']
                qa_targets = batch['qa_tuple']

                self.optimizer.zero_grad()

                # Forward pass
                qa_pred = self.model(hsi_batch)

                # Supervised loss: predict QA tuple from HSI
                target_bundle = {
                    'b': qa_targets[:, 0].unsqueeze(-1),  # [B] -> [B,1]
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
        }, self.base_path / 'trained_models' / 'qa_spectral_agent.pt')

        return {
            "status": "trained",
            "epochs": epochs,
            "final_loss": losses[-1],
            "loss_history": losses
        }

    def analyze_spectral_signature(self, hsi_sample: np.ndarray) -> Dict[str, Any]:
        """Analyze spectral signature of HSI sample"""
        if not self.is_trained:
            # Try to load saved model
            model_path = self.base_path / 'trained_models' / 'qa_spectral_agent.pt'
            if model_path.exists():
                checkpoint = torch.load(model_path)
                self.model.load_state_dict(checkpoint['model_state_dict'])
                self.is_trained = True
            else:
                return {"error": "Model not trained"}

        self.model.eval()
        with torch.no_grad():
            # Convert to tensor
            if isinstance(hsi_sample, np.ndarray):
                hsi_tensor = torch.from_numpy(hsi_sample).float().unsqueeze(0)
            else:
                hsi_tensor = hsi_sample.unsqueeze(0)

            # Get QA encoding
            qa_bundle = self.model(hsi_tensor)

            # Extract spectral invariants
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

    def classify_material(self, hsi_sample: np.ndarray) -> Dict[str, Any]:
        """Classify material from HSI spectral signature"""
        analysis = self.analyze_spectral_signature(hsi_sample)

        if "error" in analysis:
            return analysis

        # Simple classification based on QA invariants
        # In practice, this would use trained classifier
        qa = analysis["qa_tuple"]
        material_classes = {
            "vegetation": qa["b"] > 2.0,
            "water": qa["e"] > 2.0,
            "soil": qa["d"] > 4.0,
            "urban": qa["a"] > 6.0
        }

        predicted_class = "unknown"
        for material, condition in material_classes.items():
            if condition:
                predicted_class = material
                break

        return {
            "predicted_material": predicted_class,
            "confidence": 0.7,  # Placeholder
            "qa_analysis": analysis
        }

    def generate_response(self, prompt: str, qa_tuple: Optional[Tuple[int, int, int, int]] = None, max_length: int = 100) -> str:
        """Generate response using spectral QA reasoning"""
        if "spectral" in prompt.lower() or "hsi" in prompt.lower():
            if not self.is_trained:
                return "Spectral agent not trained. Please train first."

            return f"Spectral analysis: {prompt[:50]}... QA-based hyperspectral processing ready."

        # Use parent class for other prompts
        return super().generate_response(prompt, qa_tuple, max_length)


class HSIDataset(torch.utils.data.Dataset):
    """Dataset for HSI data"""

    def __init__(self, hsi_data: np.ndarray, labels: np.ndarray):
        self.hsi_data = hsi_data
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        hsi_sample = self.hsi_data[idx]  # [H, W, C]
        label = self.labels[idx]

        # Convert to tensor
        hsi_tensor = torch.from_numpy(hsi_sample).float()

        # QA tuple based on label (simple mapping)
        # Map label to QA tuple with some variation
        base = label.item()
        qa_tuple = torch.tensor([base, base+1, base+2, base+3], dtype=torch.float)

        return {
            'hsi': hsi_tensor,
            'qa_tuple': qa_tuple,
            'label': label
        }


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='QA Spectral Agent')
    parser.add_argument('--command', choices=['train', 'analyze', 'classify'],
                       default='train', help='Command to execute')
    parser.add_argument('--sample-idx', type=int, help='Sample index for analysis')

    args = parser.parse_args()

    base_path = Path('.')
    agent = SpectralQAAgent(base_path)

    if args.command == 'train':
        result = agent.train_spectral_model(epochs=2)
        print("Training result:", result)

    elif args.command == 'analyze' and args.sample_idx is not None:
        if agent.hsi_data is None:
            agent.load_hsi_data()

        if agent.hsi_data is not None and args.sample_idx < len(agent.hsi_data):
            sample = agent.hsi_data[args.sample_idx]
            analysis = agent.analyze_spectral_signature(sample)
            print("Spectral analysis:", analysis)
        else:
            print("Invalid sample index or data not loaded")

    elif args.command == 'classify' and args.sample_idx is not None:
        if agent.hsi_data is None:
            agent.load_hsi_data()

        if agent.hsi_data is not None and args.sample_idx < len(agent.hsi_data):
            sample = agent.hsi_data[args.sample_idx]
            classification = agent.classify_material(sample)
            print("Material classification:", classification)
        else:
            print("Invalid sample index or data not loaded")

    else:
        print("QA Spectral Agent - Commands: train, analyze --sample-idx <idx>, classify --sample-idx <idx>")