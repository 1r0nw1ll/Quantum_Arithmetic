#!/usr/bin/env python3
"""
QA Dataset Loader for JSONL Format
Adapts our qa_training_dataset.jsonl for QALM training
"""

import torch
from torch.utils.data import Dataset
import json
from pathlib import Path
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QAJSONLDataset(Dataset):
    """Dataset loader for JSONL format QA training data"""

    def __init__(
        self,
        data_path: str,
        max_length: int = 512,
        vocab_size: int = 10000,
        train: bool = True
    ):
        self.data_path = Path(data_path)
        self.max_length = max_length
        self.vocab_size = vocab_size
        self.train = train

        # Load all examples
        self.examples = self._load_data()

        # Build vocabulary from examples
        self.vocab, self.token_to_id, self.id_to_token = self._build_vocabulary()

        logger.info(f"Loaded {len(self.examples)} examples")
        logger.info(f"Vocabulary size: {len(self.vocab)}")
        logger.info(f"Mode: {'train' if train else 'eval'}")

    def _load_data(self) -> List[Dict]:
        """Load JSONL data"""
        examples = []

        with open(self.data_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                try:
                    example = json.loads(line.strip())
                    examples.append(example)
                except json.JSONDecodeError as e:
                    logger.warning(f"Skipping line {line_num}: {e}")
                    continue

        return examples

    def _build_vocabulary(self) -> tuple:
        """Build vocabulary from examples"""
        # Special tokens MUST be first
        special_tokens = ['<pad>', '<unk>', '<bos>', '<eos>', '<sep>',
                         '<qa>', '</qa>', '<tuple>', '</tuple>',
                         'b=', 'e=', 'd=', 'a=', 'J=', 'K=', 'X=']

        vocab = set()

        # Add tokens from examples
        for ex in self.examples:
            # From theorems
            if ex.get('type') == 'theorem':
                text = ex.get('statement', '')
                vocab.update(text.lower().split())

            # From Q&A pairs
            elif ex.get('type') == 'qa_reasoning':
                q = ex.get('question', '')
                a = ex.get('answer', '')
                vocab.update(q.lower().split())
                vocab.update(a.lower().split())

            # From tuple data
            if 'tuple' in ex:
                tuple_data = ex['tuple']
                for key in ['b', 'e', 'd', 'a']:
                    vocab.add(str(tuple_data.get(key, 0)))

        # Sort and limit vocab, but keep special tokens
        vocab = sorted(list(vocab))
        vocab = special_tokens + [t for t in vocab if t not in special_tokens]
        vocab = vocab[:self.vocab_size]

        token_to_id = {token: i for i, token in enumerate(vocab)}
        id_to_token = {i: token for token, i in token_to_id.items()}

        return vocab, token_to_id, id_to_token

    def _format_example(self, example: Dict) -> str:
        """Format example into text"""
        ex_type = example.get('type', 'unknown')

        if ex_type == 'theorem':
            return f"<qa> Theorem: {example.get('statement', '')} </qa>"

        elif ex_type == 'qa_reasoning':
            q = example.get('question', '')
            a = example.get('answer', '')
            return f"<qa> Q: {q} <sep> A: {a} </qa>"

        elif ex_type == 'synthetic_qa' or ex_type == 'qa_example':
            tuple_data = example.get('tuple', {})
            b, e, d, a = tuple_data.get('b', 0), tuple_data.get('e', 0), \
                         tuple_data.get('d', 0), tuple_data.get('a', 0)
            inv = example.get('invariants', {})
            J, K, X = inv.get('J', 0), inv.get('K', 0), inv.get('X', 0)

            return f"<qa> <tuple> b={b} e={e} d={d} a={a} </tuple> " \
                   f"Invariants: J={J} K={K} X={X} </qa>"

        elif ex_type == 'e8_qa_mapping':
            tuple_data = example.get('tuple', {})
            b, e, d, a = tuple_data.get('b', 0), tuple_data.get('e', 0), \
                         tuple_data.get('d', 0), tuple_data.get('a', 0)
            align = example.get('e8_alignment', 0)
            return f"<qa> QA tuple ({b},{e},{d},{a}) has E8 alignment: {align:.3f} </qa>"

        else:
            return f"<qa> {ex_type} data </qa>"

    def _extract_qa_tuple(self, example: Dict) -> torch.Tensor:
        """Extract QA tuple (b,e,d,a) or return zeros"""
        if 'tuple' in example:
            tuple_data = example['tuple']
            return torch.tensor([
                float(tuple_data.get('b', 0)),
                float(tuple_data.get('e', 0)),
                float(tuple_data.get('d', 0)),
                float(tuple_data.get('a', 0))
            ], dtype=torch.float32)
        else:
            return torch.zeros(4, dtype=torch.float32)

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        example = self.examples[idx]

        # Format text
        text = self._format_example(example)

        # Tokenize
        tokens = ['<bos>'] + text.lower().split()[:self.max_length-2] + ['<eos>']
        token_ids = [
            self.token_to_id.get(token, self.token_to_id['<unk>'])
            for token in tokens
        ]

        # Pad to max length
        attention_mask = [1] * len(token_ids) + [0] * (self.max_length - len(token_ids))
        token_ids += [self.token_to_id['<pad>']] * (self.max_length - len(token_ids))

        # Extract QA tuple
        qa_tuple = self._extract_qa_tuple(example)

        # Expand tuple to sequence length for attention
        qa_tuples_seq = qa_tuple.unsqueeze(0).expand(self.max_length, -1)

        return {
            'input_ids': torch.tensor(token_ids[:self.max_length], dtype=torch.long),
            'attention_mask': torch.tensor(attention_mask[:self.max_length], dtype=torch.long),
            'qa_tuples': qa_tuples_seq,
            'labels': torch.tensor(token_ids[:self.max_length], dtype=torch.long),
            'example_type': example.get('type', 'unknown')
        }


def create_dataloaders(
    data_path: str = 'qa_training_dataset.jsonl',
    batch_size: int = 8,
    train_split: float = 0.9,
    max_length: int = 512,
    vocab_size: int = 10000
) -> tuple:
    """Create train and validation dataloaders"""
    from torch.utils.data import DataLoader, random_split

    # Load full dataset
    full_dataset = QAJSONLDataset(
        data_path=data_path,
        max_length=max_length,
        vocab_size=vocab_size,
        train=True
    )

    # Split into train/val
    train_size = int(train_split * len(full_dataset))
    val_size = len(full_dataset) - train_size

    train_dataset, val_dataset = random_split(
        full_dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )

    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0
    )

    logger.info(f"Train set: {len(train_dataset)} examples")
    logger.info(f"Val set: {len(val_dataset)} examples")
    logger.info(f"Batch size: {batch_size}")

    return train_loader, val_loader, full_dataset.token_to_id


if __name__ == '__main__':
    # Test dataloader
    print("Testing QA JSONL Dataloader...")

    dataset = QAJSONLDataset(
        data_path='../qa_training_dataset.jsonl',
        max_length=128,
        vocab_size=5000
    )

    print(f"\nDataset size: {len(dataset)}")
    print(f"Vocabulary size: {len(dataset.vocab)}")

    # Test first example
    example = dataset[0]
    print(f"\nFirst example:")
    print(f"  Input shape: {example['input_ids'].shape}")
    print(f"  Attention mask shape: {example['attention_mask'].shape}")
    print(f"  QA tuples shape: {example['qa_tuples'].shape}")
    print(f"  Labels shape: {example['labels'].shape}")
    print(f"  Example type: {example['example_type']}")

    # Decode first few tokens
    tokens = [dataset.id_to_token[int(idx)] for idx in example['input_ids'][:20]]
    print(f"\nFirst 20 tokens: {' '.join(tokens)}")

    print("\n✓ Dataloader test passed!")
