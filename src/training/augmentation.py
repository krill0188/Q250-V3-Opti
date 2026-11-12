#!/usr/bin/env python3
"""
Data Augmentation for Audio Classification
SpecAugment, Mixup, Time/Frequency Masking
"""

import random
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class SpecAugment:
    """SpecAugment for spectrogram augmentation (Park et al., 2019)"""
    
    def __init__(
        self,
        freq_mask_param: int = 8,
        time_mask_param: int = 16,
        num_freq_masks: int = 2,
        num_time_masks: int = 2,
        p: float = 0.5
    ):
        self.freq_mask_param = freq_mask_param
        self.time_mask_param = time_mask_param
        self.num_freq_masks = num_freq_masks
        self.num_time_masks = num_time_masks
        self.p = p
    
    def __call__(self, spec: torch.Tensor) -> torch.Tensor:
        """Apply SpecAugment to spectrogram
        
        Args:
            spec: (C, T, F) or (T, F) spectrogram tensor
        Returns:
            Augmented spectrogram
        """
        if random.random() > self.p:
            return spec
        
        # Handle both (T, F) and (C, T, F)
        if spec.dim() == 2:
            spec = spec.unsqueeze(0)  # (1, T, F)
            squeeze = True
        else:
            squeeze = False
        
        _, T, F = spec.shape
        spec_aug = spec.clone()
        
        # Frequency masks
        for _ in range(self.num_freq_masks):
            f = random.randint(0, min(self.freq_mask_param, F))
            f0 = random.randint(0, max(0, F - f))
            spec_aug[:, :, f0:f0+f] = 0
        
        # Time masks
        for _ in range(self.num_time_masks):
            t = random.randint(0, min(self.time_mask_param, T))
            t0 = random.randint(0, max(0, T - t))
            spec_aug[:, t0:t0+t, :] = 0
        
        if squeeze:
            spec_aug = spec_aug.squeeze(0)
        
        return spec_aug


class MixupAugment:
    """Mixup augmentation for audio classification (Zhang et al., 2017)"""
    
    def __init__(self, alpha: float = 0.2, p: float = 0.5):
        self.alpha = alpha
        self.p = p
    
    def __call__(self, batch_x: torch.Tensor, batch_y: torch.Tensor) -> tuple:
        """Apply Mixup to batch
        
        Args:
            batch_x: (B, C, T, F) input batch
            batch_y: (B,) labels
        Returns:
            mixed_x, mixed_y_a, mixed_y_b, lam
        """
        if random.random() > self.p:
            return batch_x, batch_y, batch_y, 1.0
        
        batch_size = batch_x.size(0)
        lam = np.random.beta(self.alpha, self.alpha)
        lam = max(lam, 1 - lam)  # Ensure lam >= 0.5
        
        index = torch.randperm(batch_size).to(batch_x.device)
        
        mixed_x = lam * batch_x + (1 - lam) * batch_x[index]
        y_a, y_b = batch_y, batch_y[index]
        
        return mixed_x, y_a, y_b, lam


class CutMixAugment:
    """CutMix augmentation for spectrograms (Yun et al., 2019)"""
    
    def __init__(self, alpha: float = 1.0, p: float = 0.5):
        self.alpha = alpha
        self.p = p
    
    def __call__(self, batch_x: torch.Tensor, batch_y: torch.Tensor) -> tuple:
        if random.random() > self.p:
            return batch_x, batch_y, batch_y, 1.0
        
        batch_size, _, T, F = batch_x.shape
        lam = np.random.beta(self.alpha, self.alpha)
        
        # Random patch
        cut_t = int(T * np.sqrt(1 - lam))
        cut_f = int(F * np.sqrt(1 - lam))
        
        t0 = random.randint(0, max(0, T - cut_t))
        f0 = random.randint(0, max(0, F - cut_f))
        
        index = torch.randperm(batch_size).to(batch_x.device)
        
        # Apply CutMix
        batch_x[:, t0:t0+cut_t, f0:f0+cut_f] = batch_x[index, t0:t0+cut_t, f0:f0+cut_f]
        
        # Adjust lambda based on actual patch area
        lam = 1 - (cut_t * cut_f) / (T * F)
        
        y_a, y_b = batch_y, batch_y[index]
        return batch_x, y_a, y_b, lam


class TimeFreqMasking:
    """Simple time/frequency masking (simpler SpecAugment variant)"""
    
    def __init__(
        self,
        time_mask_ratio: float = 0.1,
        freq_mask_ratio: float = 0.1,
        p: float = 0.5
    ):
        self.time_mask_ratio = time_mask_ratio
        self.freq_mask_ratio = freq_mask_ratio
        self.p = p
    
    def __call__(self, spec: torch.Tensor) -> torch.Tensor:
        if random.random() > self.p:
            return spec
        
        if spec.dim() == 2:
            spec = spec.unsqueeze(0)
            squeeze = True
        else:
            squeeze = False
        
        _, T, F = spec.shape
        spec_aug = spec.clone()
        
        # Time mask
        t_mask = int(T * self.time_mask_ratio)
        if t_mask > 0:
            t0 = random.randint(0, max(0, T - t_mask))
            spec_aug[:, t0:t0+t_mask, :] = 0
        
        # Freq mask
        f_mask = int(F * self.freq_mask_ratio)
        if f_mask > 0:
            f0 = random.randint(0, max(0, F - f_mask))
            spec_aug[:, :, f0:f0+f_mask] = 0
        
        if squeeze:
            spec_aug = spec_aug.squeeze(0)
        
        return spec_aug


class GaussianNoise:
    """Add Gaussian noise to spectrogram"""
    
    def __init__(self, std: float = 0.01, p: float = 0.3):
        self.std = std
        self.p = p
    
    def __call__(self, spec: torch.Tensor) -> torch.Tensor:
        if random.random() > self.p:
            return spec
        noise = torch.randn_like(spec) * self.std
        return spec + noise


class AugmentationPipeline:
    """Combined augmentation pipeline for training"""
    
    def __init__(self, config: dict = None):
        config = config or {}
        
        self.spec_augment = SpecAugment(
            freq_mask_param=config.get('freq_mask_param', 8),
            time_mask_param=config.get('time_mask_param', 16),
            num_freq_masks=config.get('num_freq_masks', 2),
            num_time_masks=config.get('num_time_masks', 2),
            p=config.get('specaugment_p', 0.5)
        )
        
        self.mixup = MixupAugment(
            alpha=config.get('mixup_alpha', 0.2),
            p=config.get('mixup_p', 0.5)
        )
        
        self.cutmix = CutMixAugment(
            alpha=config.get('cutmix_alpha', 1.0),
            p=config.get('cutmix_p', 0.3)
        )
        
        self.time_freq_mask = TimeFreqMasking(
            time_mask_ratio=config.get('time_mask_ratio', 0.1),
            freq_mask_ratio=config.get('freq_mask_ratio', 0.1),
            p=config.get('tf_mask_p', 0.3)
        )
        
        self.gaussian_noise = GaussianNoise(
            std=config.get('noise_std', 0.01),
            p=config.get('noise_p', 0.2)
        )
    
    def apply_spec_augment(self, spec: torch.Tensor) -> torch.Tensor:
        """Apply per-sample augmentations"""
        spec = self.spec_augment(spec)
        spec = self.time_freq_mask(spec)
        spec = self.gaussian_noise(spec)
        return spec
    
    def apply_batch_augment(self, batch_x: torch.Tensor, batch_y: torch.Tensor) -> tuple:
        """Apply batch-level augmentations (Mixup/CutMix)"""
        # Randomly choose one
        r = random.random()
        if r < 0.5:
            return self.mixup(batch_x, batch_y)
        elif r < 0.8:
            return self.cutmix(batch_x, batch_y)
        else:
            return batch_x, batch_y, batch_y, 1.0


def mixup_criterion(criterion, pred, y_a, y_b, lam):
    """Mixup/CutMix loss computation"""
    return lam * criterion(pred, y_a) + (1 - lam) * criterion(pred, y_b)


# Default configs
AUG_CONFIGS = {
    'light': {
        'specaugment_p': 0.3,
        'mixup_p': 0.3,
        'cutmix_p': 0.2,
        'tf_mask_p': 0.2,
        'noise_p': 0.1,
    },
    'medium': {
        'specaugment_p': 0.5,
        'mixup_p': 0.5,
        'cutmix_p': 0.3,
        'tf_mask_p': 0.3,
        'noise_p': 0.2,
    },
    'heavy': {
        'specaugment_p': 0.7,
        'mixup_p': 0.5,
        'cutmix_p': 0.4,
        'tf_mask_p': 0.4,
        'noise_p': 0.3,
    }
}


def get_augmentation_pipeline(level: str = 'medium') -> AugmentationPipeline:
    """Get augmentation pipeline by level"""
    config = AUG_CONFIGS.get(level, AUG_CONFIGS['medium'])
    return AugmentationPipeline(config)


if __name__ == '__main__':
    # Test augmentations
    import torch
    
    # Create dummy spectrogram (C=1, T=157, F=40)
    spec = torch.randn(1, 157, 40)
    batch_x = torch.randn(16, 1, 157, 40)
    batch_y = torch.randint(0, 3, (16,))
    
    # Test SpecAugment
    spec_aug = SpecAugment()
    spec_out = spec_aug(spec)
    print(f'SpecAugment: {spec.shape} -> {spec_out.shape}')
    
    # Test Mixup
    mixup = MixupAugment(alpha=0.2)
    mx, y_a, y_b, lam = mixup(batch_x, batch_y)
    print(f'Mixup: {batch_x.shape} -> {mx.shape}, lam={lam:.3f}')
    
    # Test CutMix
    cutmix = CutMixAugment()
    cx, y_a, y_b, lam = cutmix(batch_x, batch_y)
    print(f'CutMix: {batch_x.shape} -> {cx.shape}, lam={lam:.3f}')
    
    # Test pipeline
    pipeline = get_augmentation_pipeline('medium')
    spec_out = pipeline.apply_spec_augment(spec)
    print(f'Pipeline spec: {spec.shape} -> {spec_out.shape}')
    
    mx, y_a, y_b, lam = pipeline.apply_batch_augment(batch_x, batch_y)
    print(f'Pipeline batch: {batch_x.shape} -> {mx.shape}, lam={lam:.3f}')
    
    print('\nAll augmentations working!')