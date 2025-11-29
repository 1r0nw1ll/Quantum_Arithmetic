"""
QA-TiDAR Decoder

Dual-head QA rotor implementing TiDAR architecture:
- Diffusion head: Quantum Ellipse / parallel exploration
- AR head: Inner Ellipse / sequential verification

Based on: TiDAR (Think in Diffusion, Talk in Autoregression) - NVIDIA 2025
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from math import gcd


@dataclass
class QATuple:
    """QA 4-tuple with derived invariants."""
    b: int
    e: int
    d: int  # = b + e (mod 24)
    a: int  # = e + d (mod 24)

    # Triangle invariants
    C: int = 0  # = 2ed
    F: int = 0  # = ab
    G: int = 0  # = e² + d²

    # Ellipse invariants
    J: int = 0  # = bd
    X: int = 0  # = ed
    K: int = 0  # = da

    # Extended invariants
    W: int = 0  # = X + K = d(e+a)
    Y: int = 0  # = a² - d²
    Z: int = 0  # = e² + K

    # Resonance
    mod9_family: int = 0  # Family ID based on mod-9
    mod24_phase: int = 0  # Phase on torus

    @classmethod
    def from_be(cls, b: int, e: int, modulus: int = 24) -> 'QATuple':
        """Construct QA tuple from (b, e) seed."""
        d = (b + e) % modulus
        a = (e + d) % modulus

        # Triangle
        C = (2 * e * d) % modulus
        F = (a * b) % modulus
        G = (e * e + d * d) % modulus

        # Ellipse
        J = (b * d) % modulus
        X = (e * d) % modulus
        K = (d * a) % modulus

        # Extended
        W = (X + K) % modulus
        Y = (a * a - d * d) % modulus
        Z = (e * e + K) % modulus

        # Resonance
        mod9_family = (b + e) % 9
        mod24_phase = (b * 7 + e * 11) % 24  # Arbitrary hash

        return cls(
            b=b, e=e, d=d, a=a,
            C=C, F=F, G=G,
            J=J, X=X, K=K,
            W=W, Y=Y, Z=Z,
            mod9_family=mod9_family,
            mod24_phase=mod24_phase
        )

    def to_tensor(self) -> torch.Tensor:
        """Convert to tensor representation."""
        return torch.tensor([
            self.b, self.e, self.d, self.a,
            self.C, self.F, self.G,
            self.J, self.X, self.K,
            self.W, self.Y, self.Z,
            self.mod9_family, self.mod24_phase
        ], dtype=torch.float32)


class QAKVCache:
    """Key-Value cache for QA harmonic state."""

    def __init__(self, max_length: int = 1024):
        self.max_length = max_length
        self.tuples: List[QATuple] = []
        self.hidden_states: Optional[torch.Tensor] = None

    def extend(self, new_tuples: List[QATuple], hidden: torch.Tensor):
        """Add new accepted tuples to cache."""
        self.tuples.extend(new_tuples)
        if len(self.tuples) > self.max_length:
            self.tuples = self.tuples[-self.max_length:]

        if self.hidden_states is None:
            self.hidden_states = hidden
        else:
            self.hidden_states = torch.cat([self.hidden_states, hidden], dim=1)
            if self.hidden_states.shape[1] > self.max_length:
                self.hidden_states = self.hidden_states[:, -self.max_length:]

    def get_prefix_tuples(self) -> List[QATuple]:
        return self.tuples.copy()

    def clear(self):
        self.tuples = []
        self.hidden_states = None


class QAEmbedding(nn.Module):
    """Embed QA tuples into hidden space."""

    def __init__(self, hidden_dim: int = 256, modulus: int = 24):
        super().__init__()
        self.modulus = modulus

        # Embeddings for each QA component
        self.b_embed = nn.Embedding(modulus, hidden_dim // 4)
        self.e_embed = nn.Embedding(modulus, hidden_dim // 4)
        self.d_embed = nn.Embedding(modulus, hidden_dim // 4)
        self.a_embed = nn.Embedding(modulus, hidden_dim // 4)

        # Family embedding
        self.family_embed = nn.Embedding(9, hidden_dim // 4)

        # Project to final dim
        self.proj = nn.Linear(hidden_dim + hidden_dim // 4, hidden_dim)

    def forward(self, tuples: List[QATuple]) -> torch.Tensor:
        """Embed list of QA tuples."""
        b = torch.tensor([t.b for t in tuples])
        e = torch.tensor([t.e for t in tuples])
        d = torch.tensor([t.d for t in tuples])
        a = torch.tensor([t.a for t in tuples])
        fam = torch.tensor([t.mod9_family for t in tuples])

        emb = torch.cat([
            self.b_embed(b),
            self.e_embed(e),
            self.d_embed(d),
            self.a_embed(a),
            self.family_embed(fam)
        ], dim=-1)

        return self.proj(emb)


class ARHead(nn.Module):
    """Autoregressive head for sequential QA verification."""

    def __init__(self, hidden_dim: int = 256, modulus: int = 24):
        super().__init__()
        self.modulus = modulus

        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=8, batch_first=True),
            num_layers=2
        )

        # Predict next (b, e)
        self.b_head = nn.Linear(hidden_dim, modulus)
        self.e_head = nn.Linear(hidden_dim, modulus)

    def forward(self, hidden: torch.Tensor, mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            hidden: (B, L, D) encoded QA sequence
        Returns:
            b_logits: (B, L, modulus)
            e_logits: (B, L, modulus)
        """
        # Causal mask
        L = hidden.shape[1]
        if mask is None:
            mask = torch.triu(torch.ones(L, L), diagonal=1).bool()

        h = self.transformer(hidden, mask=mask)
        return self.b_head(h), self.e_head(h)

    def verify(self, prefix_hidden: torch.Tensor, draft_tuples: List[QATuple],
               embedding: QAEmbedding) -> List[QATuple]:
        """Verify drafted tuples against AR distribution."""
        if not draft_tuples:
            return []

        # Embed draft tuples
        draft_hidden = embedding(draft_tuples).unsqueeze(0)

        # Concatenate with prefix
        if prefix_hidden is not None:
            full_hidden = torch.cat([prefix_hidden, draft_hidden], dim=1)
        else:
            full_hidden = draft_hidden

        # Get AR predictions
        b_logits, e_logits = self.forward(full_hidden)

        # Accept tuples where AR agrees
        accepted = []
        start_idx = full_hidden.shape[1] - len(draft_tuples)

        for i, t in enumerate(draft_tuples):
            pos = start_idx + i
            b_pred = b_logits[0, pos-1].argmax().item() if pos > 0 else t.b
            e_pred = e_logits[0, pos-1].argmax().item() if pos > 0 else t.e

            # Accept if predictions are close
            if abs(b_pred - t.b) <= 2 and abs(e_pred - t.e) <= 2:
                accepted.append(t)
            else:
                break  # Stop at first rejection

        return accepted


class DiffusionHead(nn.Module):
    """Diffusion head for parallel QA exploration."""

    def __init__(self, hidden_dim: int = 256, modulus: int = 24):
        super().__init__()
        self.modulus = modulus

        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=8, batch_first=True),
            num_layers=2
        )

        # Predict multiple (b, e) candidates
        self.b_head = nn.Linear(hidden_dim, modulus)
        self.e_head = nn.Linear(hidden_dim, modulus)

    def draft(self, cache: QAKVCache, k: int = 8,
              families: List[str] = None, temperature: float = 1.0) -> List[QATuple]:
        """
        Draft k future QA states in parallel.

        Args:
            cache: Current QA state cache
            k: Number of steps to draft
            families: QA families to explore
            temperature: Sampling temperature
        """
        if cache.hidden_states is None:
            # Bootstrap with random tuple
            return [QATuple.from_be(
                np.random.randint(1, self.modulus),
                np.random.randint(1, self.modulus)
            ) for _ in range(k)]

        prefix = cache.hidden_states

        # Create k draft positions (bidirectional within block)
        B, L, D = prefix.shape
        draft_tokens = torch.randn(B, k, D)  # Noisy initial draft

        # Full sequence with draft block
        full = torch.cat([prefix, draft_tokens], dim=1)

        # Bidirectional mask for draft block only
        total_len = L + k
        mask = torch.zeros(total_len, total_len)
        # Causal for prefix
        mask[:L, :L] = torch.triu(torch.ones(L, L), diagonal=1)
        # Prefix visible to draft
        mask[L:, :L] = 0
        # Bidirectional within draft block
        mask[L:, L:] = 0
        mask = mask.bool()

        # Forward pass
        h = self.transformer(full, mask=mask)

        # Sample draft tuples
        b_logits = self.b_head(h[:, L:]) / temperature
        e_logits = self.e_head(h[:, L:]) / temperature

        b_samples = torch.multinomial(F.softmax(b_logits[0], dim=-1), 1).squeeze(-1)
        e_samples = torch.multinomial(F.softmax(e_logits[0], dim=-1), 1).squeeze(-1)

        # Create QA tuples
        drafts = []
        for i in range(k):
            b = b_samples[i].item()
            e = e_samples[i].item()
            drafts.append(QATuple.from_be(b, e, self.modulus))

        return drafts


class QATiDARDecoder(nn.Module):
    """
    Dual-head QA rotor with diffusion + AR verification.

    Implements TiDAR architecture for QA sequence generation:
    - Diffusion: Parallel exploration of harmonic futures
    - AR: Sequential verification against QA laws
    """

    def __init__(self, hidden_dim: int = 256, modulus: int = 24):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.modulus = modulus

        self.embedding = QAEmbedding(hidden_dim, modulus)
        self.ar_head = ARHead(hidden_dim, modulus)
        self.diff_head = DiffusionHead(hidden_dim, modulus)
        self.kv_cache = QAKVCache()
        self.draft_buffer: List[QATuple] = []

    def decode_step(self, draft_length: int = 8) -> List[QATuple]:
        """
        Single TiDAR decode step.

        1. AR verifies previously drafted QA states
        2. Update cache with accepted states
        3. Diffusion pre-drafts k future states
        """
        # 1. Verify previous drafts
        accepted = self.ar_head.verify(
            self.kv_cache.hidden_states,
            self.draft_buffer,
            self.embedding
        )

        # 2. Update cache
        if accepted:
            hidden = self.embedding(accepted).unsqueeze(0)
            self.kv_cache.extend(accepted, hidden)

        # 3. Draft new candidates
        self.draft_buffer = self.diff_head.draft(
            self.kv_cache,
            k=draft_length,
            temperature=0.8
        )

        return accepted

    def generate(self, seed_tuples: List[QATuple], max_steps: int = 100,
                draft_length: int = 8) -> List[QATuple]:
        """Generate QA sequence from seed."""
        self.kv_cache.clear()
        self.draft_buffer = []

        # Initialize with seed
        if seed_tuples:
            hidden = self.embedding(seed_tuples).unsqueeze(0)
            self.kv_cache.extend(seed_tuples, hidden)

        all_tuples = seed_tuples.copy()

        for _ in range(max_steps):
            accepted = self.decode_step(draft_length)
            all_tuples.extend(accepted)

            if len(accepted) == 0:
                break

        return all_tuples

    def reset(self):
        """Reset decoder state."""
        self.kv_cache.clear()
        self.draft_buffer = []


def demo():
    """Demo the QA-TiDAR decoder."""
    print("=" * 60)
    print("QA-TiDAR DECODER DEMO")
    print("=" * 60)

    # Initialize decoder
    decoder = QATiDARDecoder(hidden_dim=128, modulus=24)

    # Seed with Fibonacci-like tuple
    seed = [QATuple.from_be(1, 1)]  # Fibonacci family
    print(f"\nSeed: b={seed[0].b}, e={seed[0].e}, d={seed[0].d}, a={seed[0].a}")

    # Generate sequence
    sequence = decoder.generate(seed, max_steps=10, draft_length=4)

    print(f"\nGenerated {len(sequence)} tuples:")
    print("-" * 60)
    for i, t in enumerate(sequence[:10]):
        print(f"  [{i}] (b={t.b:2d}, e={t.e:2d}, d={t.d:2d}, a={t.a:2d}) | "
              f"J={t.J:2d}, X={t.X:2d}, K={t.K:2d} | fam={t.mod9_family}")

    # Verify QA invariants
    print("\nInvariant check:")
    violations = 0
    for t in sequence:
        if (t.b + t.e) % 24 != t.d:
            violations += 1
        if (t.e + t.d) % 24 != t.a:
            violations += 1
    print(f"  Violations: {violations}/{len(sequence)*2}")

    return sequence


if __name__ == '__main__':
    demo()
