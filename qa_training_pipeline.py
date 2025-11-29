#!/usr/bin/env python3
"""
QA Language Model Training Pipeline v1.0
Efficient training system with mathematical validation and invariant monitoring
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt

from qa_model_architecture import QALanguageModel, QAConfig, QAOperations
try:
    from qa_metrics.e8_harmonic_index import log_harmonic_index as _log_hi
except Exception:
    def _log_hi(tag: str, e8: float, loss: float, extra=None):
        return e8
try:
    from qa_e8_alignment import e8_alignment_batch_torch as _e8_align_batch
except Exception:
    def _e8_align_batch(b, e, d=None, a=None):
        import torch
        return torch.zeros_like(b, dtype=torch.float)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QADataset(Dataset):
    """Dataset for QA language model training"""

    def __init__(self, data_path: str, max_length: int = 512, qa_only: bool = False):
        self.max_length = max_length
        self.qa_only = qa_only

        # Load training data (QA or general text)
        with open(data_path, 'r') as f:
            self.data = json.load(f)

        # Check if it's QA data or general text
        if 'data' in self.data and isinstance(self.data['data'], dict):
            # QA data
            self.is_qa_data = True
            self.qa_data = self.data['data']
        elif 'texts' in self.data:
            # General text data
            self.is_qa_data = False
            self.texts = self.data['texts']
        else:
            raise ValueError("Unknown data format")

        # Build vocabulary
        self.vocab = self._build_vocabulary()
        self.token_to_id = {token: i for i, token in enumerate(self.vocab)}
        self.id_to_token = {i: token for token, i in self.token_to_id.items()}

        if self.is_qa_data:
            total_samples = sum(len(samples) for samples in self.qa_data.values())
            logger.info(f"Loaded {total_samples} QA training samples")
        else:
            logger.info(f"Loaded {len(self.texts)} text training samples")
        logger.info(f"Vocabulary size: {len(self.vocab)}")

    def _build_vocabulary(self) -> List[str]:
        """Build vocabulary from training data"""
        vocab = set()

        if self.is_qa_data:
            for sample in self.qa_data.values():
                for item in sample:
                    # Add text tokens
                    text = item.get('text_description', '') + ' ' + item.get('qa_reasoning', '')
                    vocab.update(text.split())
        else:
            for text in self.texts:
                vocab.update(text.split())

        # Add special tokens
        vocab.update(['<pad>', '<unk>', '<bos>', '<eos>', '<qa>', '</qa>'])

        return sorted(list(vocab))

    def __len__(self):
        # Count total samples
        if self.is_qa_data:
            return sum(len(samples) for samples in self.qa_data.values())
        else:
            return len(self.texts)

    def __getitem__(self, idx):
        if self.is_qa_data:
            # Find the sample at the given index across all categories
            total_samples = 0
            for category, samples in self.qa_data.items():
                if idx < total_samples + len(samples):
                    sample = samples[idx - total_samples]
                    break
                total_samples += len(samples)
            else:
                # Fallback for out of bounds
                sample = list(self.qa_data.values())[0][0]

            # Extract or generate QA tuple
            if 'tuple' in sample:
                # Use provided tuple
                qa_tuple = torch.tensor([
                    sample['tuple']['b'],
                    sample['tuple']['e'],
                    sample['tuple']['d'],
                    sample['tuple']['a']
                ], dtype=torch.float)
            else:
                # Generate QA tuple from b,e if available
                if 'b' in sample and 'e' in sample:
                    b_val = sample['b']
                    e_val = sample['e']
                    d_val = (b_val + e_val) % 24
                    a_val = (e_val + d_val) % 24
                    qa_tuple = torch.tensor([b_val, e_val, d_val, a_val], dtype=torch.float)
                else:
                    # Dummy tuple
                    qa_tuple = torch.zeros(4, dtype=torch.float)

            # Create text input
            text = sample.get('text_description', 'QA tuple description')
            if not self.qa_only:
                text += ' ' + sample.get('qa_reasoning', 'QA reasoning')
        else:
            # General text data
            sample = None  # Not used
            text = self.texts[idx]
            qa_tuple = torch.zeros(4, dtype=torch.float)  # Dummy QA tuple

        # Tokenize
        tokens = ['<bos>'] + text.split()[:self.max_length-2] + ['<eos>']
        token_ids = [self.token_to_id.get(token, self.token_to_id['<unk>']) for token in tokens]

        # Pad to max length
        attention_mask = [1] * len(token_ids) + [0] * (self.max_length - len(token_ids))
        token_ids += [self.token_to_id['<pad>']] * (self.max_length - len(token_ids))

        return {
            'input_ids': torch.tensor(token_ids, dtype=torch.long),
            'attention_mask': torch.tensor(attention_mask, dtype=torch.long),
            'qa_tuples': qa_tuple.unsqueeze(0).expand(self.max_length, -1),  # Broadcast to sequence length
            'labels': torch.tensor(token_ids, dtype=torch.long),  # For language modeling
        }


class MathematicalValidationLoss(nn.Module):
    """Loss functions that validate mathematical correctness"""

    def __init__(self, invariant_weight: float = 0.1):
        super().__init__()
        self.invariant_weight = invariant_weight

    def forward(self, qa_tuples: torch.Tensor) -> torch.Tensor:
        """
        Compute mathematical validation loss
        Ensures QA invariants are preserved: J=b·d, K=d·a, X=e·d
        """
        b, e, d, a = qa_tuples[..., 0], qa_tuples[..., 1], qa_tuples[..., 2], qa_tuples[..., 3]

        # Check closure invariants
        closure_b_e_d = torch.abs((b + e) - d)  # d = b + e
        closure_e_d_a = torch.abs((e + d) - a)  # a = e + d

        # Check algebraic invariants
        invariant_J = torch.abs(b * d - (b + e) * d + e * d)  # J = b·d
        invariant_K = torch.abs(d * a - d * (e + d) + e * d)  # K = d·a
        invariant_X = torch.abs(e * d - e * d)  # X = e·d (should be 0 for valid tuples)

        # Combine losses
        closure_loss = closure_b_e_d.mean() + closure_e_d_a.mean()
        invariant_loss = invariant_J.mean() + invariant_K.mean() + invariant_X.mean()

        total_loss = closure_loss + self.invariant_weight * invariant_loss

        return total_loss


class QATrainer:
    """Training pipeline for QA Language Model"""

    def __init__(
        self,
        model: QALanguageModel,
        train_dataset: QADataset,
        val_dataset: Optional[QADataset] = None,
        batch_size: int = 8,
        learning_rate: float = 1e-4,
        num_epochs: int = 10,
        checkpoint_dir: str = "./checkpoints",
        log_dir: str = "./logs",
        general_lm: bool = False
    ):
        self.model = model
        self.train_dataset = train_dataset
        self.val_dataset = val_dataset
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.num_epochs = num_epochs

        # Create directories
        self.checkpoint_dir = Path(checkpoint_dir)
        self.log_dir = Path(log_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        self.general_lm = general_lm

        # Setup device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

        # Setup data loaders
        self.train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            num_workers=0  # For compatibility
        )

        if val_dataset:
            self.val_loader = DataLoader(
                val_dataset,
                batch_size=batch_size,
                shuffle=False,
                num_workers=0
            )

        # Setup optimizer and loss
        self.optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
        self.lm_criterion = nn.CrossEntropyLoss(ignore_index=train_dataset.token_to_id['<pad>'])
        self.math_validator = MathematicalValidationLoss()

        # Curriculum learning
        self.curriculum_stage = 0
        self.max_curriculum_stages = 3

        # Training state
        self.current_epoch = 0
        self.best_val_loss = float('inf')
        self.training_stats = []

        logger.info("QA Trainer initialized")
        logger.info(f"Training samples: {len(train_dataset)}")
        logger.info(f"Batch size: {batch_size}")
        logger.info(f"Learning rate: {learning_rate}")

    def curriculum_scheduler(self, epoch: int) -> Dict[str, float]:
        """Curriculum learning scheduler"""
        if self.general_lm:
            # For general language modeling, focus only on LM loss
            weights = {
                'lm_weight': 1.0,
                'math_weight': 0.0,
                'invariant_weight': 0.0,
            }
        else:
            stage = min(epoch // 3, self.max_curriculum_stages - 1)
            self.curriculum_stage = stage

            # Adjust weights based on curriculum stage
            weights = {
                'lm_weight': 1.0,  # Language modeling always active
                'math_weight': min(0.1 + stage * 0.2, 0.5),  # Increase math validation weight
                'invariant_weight': min(0.05 + stage * 0.1, 0.25),  # Increase invariant preservation
            }

        return weights

    def train_epoch(self) -> Dict[str, float]:
        """Train for one epoch"""
        self.model.train()
        epoch_stats = {
            'lm_loss': 0.0,
            'math_loss': 0.0,
            'total_loss': 0.0,
            'invariant_violations': 0,
            'num_batches': 0
        }

        curriculum_weights = self.curriculum_scheduler(self.current_epoch)

        hi_logged = False
        batch_count = 0
        for batch in self.train_loader:
            batch_count += 1
            print(f"Processing batch {batch_count}/{len(self.train_loader)}")
            input_ids = batch['input_ids'].to(self.device)
            attention_mask = batch['attention_mask'].to(self.device)
            qa_tuples = batch['qa_tuples'].to(self.device)
            labels = batch['labels'].to(self.device)

            self.optimizer.zero_grad()

            # Forward pass
            outputs = self.model(
                input_ids=input_ids,
                qa_tuples=qa_tuples,
                attention_mask=attention_mask
            )
            lm_logits = outputs[0]

            # Language modeling loss
            lm_loss = self.lm_criterion(
                lm_logits.view(-1, lm_logits.size(-1)),
                labels.view(-1)
            )

            # QA invariant loss (only for QA data)
            invariant_loss = torch.tensor(0.0, device=self.device)
            if not self.general_lm and qa_tuples is not None:
                # Extract b,e,d,a from qa_tuples
                b, e, d, a = qa_tuples[:, 0], qa_tuples[:, 1], qa_tuples[:, 2], qa_tuples[:, 3]
                invariant_loss = QAOperations.check_invariants(b, e, d, a)

            # Total loss
            total_loss = (
                curriculum_weights['lm_weight'] * lm_loss +
                curriculum_weights['invariant_weight'] * invariant_loss
            )

            # Mathematical validation loss
            math_loss = self.math_validator(qa_tuples)

            # Check for invariant violations
            with torch.no_grad():
                violations = (math_loss > 0.1).float().sum().item()

            # Combined loss with curriculum weighting
            total_loss = (
                curriculum_weights['lm_weight'] * lm_loss +
                curriculum_weights['math_weight'] * math_loss
            )

            # Backward pass
            total_loss.backward()
            self.optimizer.step()

            # Update stats
            epoch_stats['lm_loss'] += lm_loss.item()
            epoch_stats['math_loss'] += math_loss.item()
            epoch_stats['total_loss'] += total_loss.item()
            epoch_stats['invariant_violations'] += violations
            epoch_stats['num_batches'] += 1

            # Log E8 Harmonic Index once per epoch using first batch
            if not hi_logged:
                try:
                    # Take first position tuples across batch
                    b, e, d, a = qa_tuples[:, 0, 0], qa_tuples[:, 0, 1], qa_tuples[:, 0, 2], qa_tuples[:, 0, 3]
                    e8_scores = _e8_align_batch(b, e, d, a)
                    e8_mean = float(e8_scores.mean().detach().cpu().item())
                    _ = _log_hi(f"train_epoch_{self.current_epoch}", e8_mean, float(total_loss.detach().cpu().item()), {
                        'epoch': int(self.current_epoch), 'batch': int(batch_count)
                    })
                except Exception:
                    pass
                hi_logged = True

        # Average stats
        for key in ['lm_loss', 'math_loss', 'total_loss']:
            epoch_stats[key] /= epoch_stats['num_batches']

        return epoch_stats

    def validate(self) -> Dict[str, float]:
        """Validation step"""
        if not self.val_dataset:
            return {}

        self.model.eval()
        val_stats = {
            'val_lm_loss': 0.0,
            'val_math_loss': 0.0,
            'val_total_loss': 0.0,
            'num_batches': 0
        }

        with torch.no_grad():
            for batch in self.val_loader:
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                qa_tuples = batch['qa_tuples'].to(self.device)
                labels = batch['labels'].to(self.device)

                outputs = self.model(
                    input_ids=input_ids,
                    qa_tuples=qa_tuples,
                    attention_mask=attention_mask
                )
                lm_logits = outputs[0]

                lm_loss = self.lm_criterion(
                    lm_logits.view(-1, lm_logits.size(-1)),
                    labels.view(-1)
                )
                math_loss = self.math_validator(qa_tuples)

                val_stats['val_lm_loss'] += lm_loss.item()
                val_stats['val_math_loss'] += math_loss.item()
                val_stats['val_total_loss'] += (lm_loss + 0.1 * math_loss).item()
                val_stats['num_batches'] += 1

        # Average stats
        for key in ['val_lm_loss', 'val_math_loss', 'val_total_loss']:
            val_stats[key] /= val_stats['num_batches']

        return val_stats

    def save_checkpoint(self, epoch: int, val_loss: float, is_best: bool = False):
        """Save model checkpoint"""
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'val_loss': val_loss,
            'curriculum_stage': self.curriculum_stage,
            'training_stats': self.training_stats
        }

        checkpoint_path = self.checkpoint_dir / f'checkpoint_epoch_{epoch}.pt'
        torch.save(checkpoint, checkpoint_path)

        if is_best:
            best_path = self.checkpoint_dir / 'best_model.pt'
            torch.save(checkpoint, best_path)
            logger.info(f"Saved best model checkpoint: {best_path}")

        logger.info(f"Saved checkpoint: {checkpoint_path}")

    def load_checkpoint(self, checkpoint_path: str):
        """Load model checkpoint"""
        checkpoint = torch.load(checkpoint_path)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.current_epoch = checkpoint['epoch']
        self.best_val_loss = checkpoint.get('val_loss', float('inf'))
        self.training_stats = checkpoint.get('training_stats', [])

        logger.info(f"Loaded checkpoint from epoch {self.current_epoch}")

    def plot_training_progress(self):
        """Plot training progress"""
        if not self.training_stats:
            return

        epochs = [s['epoch'] for s in self.training_stats]
        lm_losses = [s['lm_loss'] for s in self.training_stats]
        math_losses = [s['math_loss'] for s in self.training_stats]
        total_losses = [s['total_loss'] for s in self.training_stats]

        plt.figure(figsize=(12, 4))

        plt.subplot(1, 3, 1)
        plt.plot(epochs, lm_losses, label='LM Loss')
        plt.xlabel('Epoch')
        plt.ylabel('Language Modeling Loss')
        plt.legend()

        plt.subplot(1, 3, 2)
        plt.plot(epochs, math_losses, label='Math Loss', color='orange')
        plt.xlabel('Epoch')
        plt.ylabel('Mathematical Validation Loss')
        plt.legend()

        plt.subplot(1, 3, 3)
        plt.plot(epochs, total_losses, label='Total Loss', color='green')
        plt.xlabel('Epoch')
        plt.ylabel('Total Loss')
        plt.legend()

        plt.tight_layout()
        plt.savefig(self.log_dir / 'training_progress.png')
        plt.close()

        logger.info(f"Saved training progress plot: {self.log_dir / 'training_progress.png'}")

    def train(self):
        """Main training loop"""
        logger.info("Starting QA Language Model training...")

        for epoch in range(self.current_epoch, self.num_epochs):
            self.current_epoch = epoch

            logger.info(f"\nEpoch {epoch + 1}/{self.num_epochs}")
            logger.info(f"Curriculum stage: {self.curriculum_stage}")

            # Train epoch
            train_stats = self.train_epoch()
            logger.info(f"Train - LM Loss: {train_stats['lm_loss']:.4f}, "
                       f"Math Loss: {train_stats['math_loss']:.4f}, "
                       f"Total Loss: {train_stats['total_loss']:.4f}, "
                       f"Invariant Violations: {train_stats['invariant_violations']}")

            # Validate
            val_stats = self.validate()
            if val_stats:
                val_loss = val_stats['val_total_loss']
                logger.info(f"Val - LM Loss: {val_stats['val_lm_loss']:.4f}, "
                           f"Math Loss: {val_stats['val_math_loss']:.4f}, "
                           f"Total Loss: {val_stats['val_total_loss']:.4f}")

                # Save best model
                is_best = val_loss < self.best_val_loss
                if is_best:
                    self.best_val_loss = val_loss
            else:
                is_best = False

            # Save checkpoint
            if (epoch + 1) % 5 == 0 or is_best:
                self.save_checkpoint(epoch, val_stats.get('val_total_loss', train_stats['total_loss']), is_best)

            # Record stats
            epoch_stats = {
                'epoch': epoch,
                'curriculum_stage': self.curriculum_stage,
                **train_stats,
                **val_stats
            }
            self.training_stats.append(epoch_stats)

            # Plot progress
            if (epoch + 1) % 10 == 0:
                self.plot_training_progress()

        logger.info("Training completed!")
        self.plot_training_progress()

        return self.training_stats


def create_training_pipeline(
    data_path: str = "qa_data/qa_training_dataset.json",
    model_config: Optional[QAConfig] = None,
    batch_size: int = 4,
    num_epochs: int = 5,
    checkpoint_dir: str = "./checkpoints",
    log_dir: str = "./logs",
    general_lm: bool = False
) -> QATrainer:
    """Factory function to create training pipeline"""

    # Create dataset first to get vocab size
    train_dataset = QADataset(data_path, max_length=256, qa_only=False)  # Match position embeddings

    # Default config if not provided
    if model_config is None:
        model_config = QAConfig(
            vocab_size=len(train_dataset.vocab),  # Use actual vocab size
            hidden_size=128,   # Smaller model for faster training
            num_hidden_layers=2,
            num_attention_heads=2,
            intermediate_size=256,
            max_position_embeddings=256,  # Shorter sequences
        )

    # Create model
    model = QALanguageModel(model_config)

    # Create validation dataset (reuse train for now)
    val_dataset = QADataset(data_path, max_length=256, qa_only=True)  # Use same data for validation

    # Create trainer
    trainer = QATrainer(
        model=model,
        train_dataset=train_dataset,
        val_dataset=val_dataset,
        batch_size=batch_size,
        num_epochs=num_epochs,
        checkpoint_dir=checkpoint_dir,
        log_dir=log_dir
    )

    return trainer


if __name__ == "__main__":
    # Create and run training pipeline
    # Test runs: QA mode vs General LM mode
    print("=== Testing QA Mode (Discrete Mathematics) ===")
    qa_trainer = create_training_pipeline(
        data_path="qa_data/qa_training_dataset.json",
        num_epochs=1,  # Single epoch for testing
        batch_size=1,  # Small batch
        general_lm=False  # Enable QA invariant training
    )
    qa_stats = qa_trainer.train()
    print(f"QA Training Results: {qa_stats[-1] if qa_stats else 'No stats'}")

    print("\n=== Testing General LM Mode ===")
    lm_trainer = create_training_pipeline(
        data_path="wikitext_train.json",
        num_epochs=1,  # Single epoch for testing
        batch_size=1,  # Small batch
        general_lm=True
    )
    lm_stats = lm_trainer.train()
    print(f"LM Training Results: {lm_stats[-1] if lm_stats else 'No stats'}")

    print("Comparative testing completed!")
    print("Check logs/ and checkpoints/ directories for results.")
