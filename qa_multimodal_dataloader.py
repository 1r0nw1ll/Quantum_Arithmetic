#!/usr/bin/env python3
"""
QA Multimodal Dataloader for CIFAR-10 and Domain-Specific Datasets
Loads CIFAR-10 images and domain-specific data (HSI, LIDAR, MS)
"""

import torch
from torch.utils.data import Dataset, DataLoader
import pickle
import numpy as np
from pathlib import Path
import torchvision.transforms as transforms
from typing import Tuple, Optional
from scipy.io import loadmat

class CIFAR10QADataset(Dataset):
    """CIFAR-10 dataset adapted for QA-JEPA training"""

    def __init__(self, root_dir: str, train: bool = True, transform=None):
        self.root_dir = Path(root_dir)
        self.train = train
        self.transform = transform or transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
        ])

        # Load CIFAR-10 data
        self.data, self.labels = self._load_cifar10()

    def _load_cifar10(self) -> Tuple[np.ndarray, np.ndarray]:
        """Load CIFAR-10 batches"""
        data_list = []
        labels_list = []

        if self.train:
            batch_files = [f'data_batch_{i}' for i in range(1, 6)]
        else:
            batch_files = ['test_batch']

        for batch_file in batch_files:
            batch_path = self.root_dir / 'cifar-10-batches-py' / batch_file
            with open(batch_path, 'rb') as f:
                batch = pickle.load(f, encoding='bytes')

            data_list.append(batch[b'data'])
            labels_list.extend(batch[b'labels'])

        data = np.concatenate(data_list, axis=0)
        data = data.reshape(-1, 3, 32, 32).transpose(0, 2, 3, 1)  # [N, H, W, C]
        labels = np.array(labels_list)

        return data, labels

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        image = self.data[idx]  # [32, 32, 3]
        label = self.labels[idx]

        # Convert to float and normalize to [0,1] if not already
        if isinstance(image, torch.Tensor):
            image = image.float()
        else:
            image = torch.from_numpy(image).float().permute(2, 0, 1) / 255.0

        # Flatten for encoder input
        image_flat = image.view(-1).unsqueeze(0)  # [1, 3072]

        # QA tuple placeholder (random for now, will be predicted)
        qa_tuple = torch.randn(4)

        return {
            'image': image_flat,  # [1, 3072]
            'qa_tuple': qa_tuple,
            'label': label,
            'domain': 'cifar'
        }


class DomainSpecificDataset(Dataset):
    """Dataset for domain-specific multimodal data (HSI, LIDAR, MS)"""

    def __init__(self, data_dir: str, domain: str):
        self.data_dir = Path(data_dir)
        self.domain = domain

        # Load domain data
        self.data, self.labels = self._load_domain_data()

    def _load_domain_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """Load domain-specific data from .mat files"""
        if self.domain == 'hsi':
            data_file = self.data_dir / 'HSI_Tr.mat'
            label_file = self.data_dir / 'TrLabel.mat'
        elif self.domain == 'lidar':
            data_file = self.data_dir / 'LIDAR_Tr.mat'
            label_file = self.data_dir / 'TrLabel.mat'
        elif self.domain == 'ms':
            data_file = self.data_dir / 'MS_Tr.mat'
            label_file = self.data_dir / 'TrLabel.mat'
        else:
            raise ValueError(f"Unknown domain: {self.domain}")

        # Load .mat files
        data_mat = loadmat(str(data_file))
        label_mat = loadmat(str(label_file))

        # Extract data (assuming standard MATLAB variable names)
        data_key = list(data_mat.keys())[-1]  # Last key is usually the data
        label_key = list(label_mat.keys())[-1]

        data = data_mat[data_key]  # Shape depends on domain
        labels = label_mat[label_key].flatten()

        return data, labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        sample = self.data[idx]  # Shape varies by domain
        label = self.labels[idx]

        # Convert to tensor and flatten
        if isinstance(sample, np.ndarray):
            sample = torch.from_numpy(sample).float()
        elif not isinstance(sample, torch.Tensor):
            sample = torch.tensor(sample, dtype=torch.float32)

        # Flatten and add sequence dim
        sample_flat = sample.reshape(-1).unsqueeze(0)  # [1, D]

        # QA tuple placeholder
        qa_tuple = torch.randn(4)

        return {
            'image': sample_flat,
            'qa_tuple': qa_tuple,
            'label': label,
            'domain': self.domain
        }


def create_multimodal_dataloaders(
    data_dir: str = 'data',
    batch_size: int = 32,
    num_workers: int = 2,
    include_domains: bool = True
) -> Tuple[DataLoader, DataLoader]:
    """Create train and test dataloaders for CIFAR-10 and domain-specific data"""

    datasets = []

    # CIFAR-10
    try:
        cifar_train = CIFAR10QADataset(data_dir, train=True)
        cifar_test = CIFAR10QADataset(data_dir, train=False)
        datasets.append(('cifar', cifar_train, cifar_test))
        print(f"✓ Loaded CIFAR-10: {len(cifar_train)} train, {len(cifar_test)} test")
    except Exception as e:
        print(f"⚠️ Could not load CIFAR-10: {e}")

    # Domain-specific datasets
    if include_domains:
        multimodal_dir = Path('multimodal_data')  # At root level
        if multimodal_dir.exists():
            domains = ['hsi', 'lidar', 'ms']
            for domain in domains:
                try:
                    dataset = DomainSpecificDataset(multimodal_dir, domain)
                    datasets.append((domain, dataset, None))  # No separate test for now
                    print(f"✓ Loaded {domain.upper()}: {len(dataset)} samples")
                except Exception as e:
                    print(f"⚠️ Could not load {domain.upper()}: {e}")
        else:
            print("⚠️ multimodal_data directory not found")

    # Combine all datasets
    if not datasets:
        raise ValueError("No datasets could be loaded")

    # For simplicity, use CIFAR for train/test, domains for additional training
    train_datasets = [ds for name, ds, _ in datasets if ds is not None]
    test_datasets = [ds for _, _, ds in datasets if ds is not None]

    # Concatenate datasets
    from torch.utils.data import ConcatDataset
    train_dataset = ConcatDataset(train_datasets)
    test_dataset = ConcatDataset(test_datasets) if test_datasets else train_dataset

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True
    )

    return train_loader, test_loader


if __name__ == '__main__':
    # Test the dataloader
    train_loader, test_loader = create_multimodal_dataloaders()

    print(f"Train dataset size: {len(train_loader.dataset)}")
    print(f"Test dataset size: {len(test_loader.dataset)}")

    # Test one batch
    batch = next(iter(train_loader))
    print(f"Batch image shape: {batch['image'].shape}")
    print(f"Batch QA tuple shape: {batch['qa_tuple'].shape}")
    print(f"Batch labels shape: {batch['label'].shape}")
    print(f"Domains in batch: {set(batch['domain'])}")

    print("✓ Multimodal dataloader ready!")