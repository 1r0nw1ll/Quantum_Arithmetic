"""
Simple CNN-based ARC Solver for Real Model Output Testing

Generates candidate solutions via neural network, then tests
inverse E8 reranking on actual model outputs (not synthetic).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import json
from pathlib import Path
from typing import List, Tuple, Dict
import sys

sys.path.insert(0, '/home/player2/signal_experiments/qa_lab')
from arc_e8_reranker import ARCE8Reranker


class ARCEncoder(nn.Module):
    """Encode ARC grid (up to 30x30, 10 colors) to latent."""

    def __init__(self, hidden_dim=256):
        super().__init__()
        # Color embedding (10 colors + padding)
        self.color_embed = nn.Embedding(11, 32)

        self.conv1 = nn.Conv2d(32, 64, 3, padding=1)
        self.conv2 = nn.Conv2d(64, 128, 3, padding=1)
        self.conv3 = nn.Conv2d(128, hidden_dim, 3, padding=1)
        self.pool = nn.AdaptiveAvgPool2d((8, 8))
        self.fc = nn.Linear(hidden_dim * 8 * 8, hidden_dim)

    def forward(self, x):
        # x: (B, H, W) integer grid
        B, H, W = x.shape
        emb = self.color_embed(x)  # (B, H, W, 32)
        emb = emb.permute(0, 3, 1, 2)  # (B, 32, H, W)

        h = F.relu(self.conv1(emb))
        h = F.relu(self.conv2(h))
        h = F.relu(self.conv3(h))
        h = self.pool(h)
        h = h.contiguous().view(B, -1)
        return self.fc(h)


class ARCDecoder(nn.Module):
    """Decode latent to ARC output grid."""

    def __init__(self, hidden_dim=256, max_size=30):
        super().__init__()
        self.max_size = max_size
        self.fc = nn.Linear(hidden_dim, hidden_dim * 8 * 8)

        self.deconv1 = nn.ConvTranspose2d(hidden_dim, 128, 4, stride=2, padding=1)
        self.deconv2 = nn.ConvTranspose2d(128, 64, 4, stride=2, padding=1)
        self.final = nn.Conv2d(64, 10, 3, padding=1)  # 10 color logits

    def forward(self, z, output_size):
        # z: (B, hidden_dim)
        # output_size: (H, W) target size
        B = z.shape[0]
        H, W = output_size

        h = self.fc(z).reshape(B, -1, 8, 8)
        h = F.relu(self.deconv1(h))  # -> 16x16
        h = F.relu(self.deconv2(h))  # -> 32x32
        h = self.final(h)  # (B, 10, 32, 32)

        # Resize to target
        h = F.interpolate(h, size=(H, W), mode='bilinear', align_corners=False)
        return h  # (B, 10, H, W) logits


class SimpleARCSolver(nn.Module):
    """Simple ARC solver that learns input-output mapping."""

    def __init__(self, hidden_dim=256):
        super().__init__()
        self.encoder = ARCEncoder(hidden_dim)
        self.decoder = ARCDecoder(hidden_dim)

    def forward(self, inputs: List[torch.Tensor], output_size: Tuple[int, int]):
        # Encode all input examples
        encoded = []
        for inp in inputs:
            if inp.dim() == 2:
                inp = inp.unsqueeze(0)
            encoded.append(self.encoder(inp))

        # Average encoded representations
        z = torch.stack(encoded).mean(0)  # (1, hidden_dim)

        # Decode to output
        logits = self.decoder(z, output_size)
        return logits

    def generate_candidates(self, inputs: List[torch.Tensor],
                           output_size: Tuple[int, int],
                           n_candidates: int = 10,
                           temperature: float = 1.0) -> List[np.ndarray]:
        """Generate multiple candidate solutions via temperature sampling."""
        self.eval()
        candidates = []

        with torch.no_grad():
            logits = self.forward(inputs, output_size)  # (1, 10, H, W)
            logits = logits.squeeze(0)  # (10, H, W)

            for i in range(n_candidates):
                # Temperature-scaled sampling
                if i == 0:
                    # First candidate: argmax (greedy)
                    pred = logits.argmax(0).cpu().numpy()
                else:
                    # Sample with varying temperatures
                    t = temperature * (1.0 + 0.5 * (i - 1))
                    probs = F.softmax(logits / t, dim=0)
                    # Sample from categorical
                    flat_probs = probs.permute(1, 2, 0).reshape(-1, 10)
                    samples = torch.multinomial(flat_probs, 1).squeeze(-1)
                    pred = samples.reshape(output_size[0], output_size[1]).cpu().numpy()

                candidates.append(pred.astype(np.int32))

        return candidates


def train_on_task(model: SimpleARCSolver, task_data: dict,
                 epochs: int = 50, lr: float = 0.01) -> float:
    """Quick train model on a single task's examples."""
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()

    train_examples = task_data['train']
    test_output = np.array(task_data['test'][0]['output'])
    output_size = test_output.shape

    model.train()
    final_loss = 0.0

    for epoch in range(epochs):
        total_loss = 0.0
        for ex in train_examples:
            inp = torch.tensor(ex['input'], dtype=torch.long)
            out = torch.tensor(ex['output'], dtype=torch.long)
            out_size = out.shape

            logits = model([inp], out_size)  # (1, 10, H, W)
            loss = criterion(logits, out.unsqueeze(0))

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        final_loss = total_loss / len(train_examples)

    return final_loss


def test_inverse_e8_on_real_outputs(n_tasks: int = 50):
    """Test inverse E8 reranking on real CNN outputs."""

    print("=" * 70)
    print("INVERSE E8 ON REAL CNN OUTPUTS")
    print("=" * 70)

    # Load tasks
    task_dir = Path('/home/player2/signal_experiments/ARC-AGI/data/training')
    task_files = sorted(task_dir.glob('*.json'))[:n_tasks]

    # Initialize reranker
    reranker = ARCE8Reranker(encoding_mode='patch', modulus=24, inverse=True)

    results = {
        'correct': 0,
        'total': 0,
        'e8_discriminated': 0,
        'model_got_correct': 0,
        'details': []
    }

    for task_file in task_files:
        with open(task_file) as f:
            task_data = json.load(f)

        correct_output = np.array(task_data['test'][0]['output'], dtype=np.int32)
        test_input = task_data['test'][0]['input']
        output_size = correct_output.shape

        # Train fresh model on this task
        model = SimpleARCSolver(hidden_dim=128)
        loss = train_on_task(model, task_data, epochs=30, lr=0.01)

        # Generate candidates
        inputs = [torch.tensor(test_input, dtype=torch.long)]
        candidates = model.generate_candidates(inputs, output_size, n_candidates=10, temperature=0.8)

        # Check if model got correct answer
        model_correct = np.array_equal(candidates[0], correct_output)

        # Insert correct solution at random position for fair test
        correct_pos = np.random.randint(0, 10)
        candidates[correct_pos] = correct_output.copy()

        # Rerank with inverse E8
        rerank_result = reranker.rerank_solutions(candidates)
        best_idx = rerank_result['best_e8_idx']

        # Check if E8 discriminated (not all same score)
        scores = rerank_result['e8_scores']
        discriminated = len(set(scores)) > 1

        success = (best_idx == correct_pos)

        results['total'] += 1
        if success:
            results['correct'] += 1
        if discriminated:
            results['e8_discriminated'] += 1
        if model_correct:
            results['model_got_correct'] += 1

        results['details'].append({
            'task': task_file.stem,
            'correct_pos': correct_pos,
            'best_idx': best_idx,
            'success': success,
            'discriminated': discriminated,
            'model_correct': model_correct,
            'loss': loss
        })

        if results['total'] % 10 == 0:
            acc = results['correct'] / results['total'] * 100
            print(f"  Progress: {results['total']}/{n_tasks} | Accuracy: {acc:.1f}%")

    # Final stats
    acc = results['correct'] / results['total'] * 100
    disc_rate = results['e8_discriminated'] / results['total'] * 100
    model_acc = results['model_got_correct'] / results['total'] * 100

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Tasks tested: {results['total']}")
    print(f"Inverse E8 accuracy: {results['correct']}/{results['total']} = {acc:.1f}%")
    print(f"E8 discrimination rate: {disc_rate:.1f}%")
    print(f"Model greedy accuracy: {model_acc:.1f}%")
    print(f"Random baseline: 10.0%")
    print()

    # Save results
    with open('/home/player2/signal_experiments/qa_lab/real_vit_e8_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print("Results saved to real_vit_e8_results.json")

    return results


if __name__ == '__main__':
    test_inverse_e8_on_real_outputs(n_tasks=50)
