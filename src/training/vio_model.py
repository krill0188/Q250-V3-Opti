#!/usr/bin/env python3
"""
VIO (Visual-Inertial Odometry) Model for UZH-FPV Dataset
CNN + LSTM / Transformer for IMU + Camera fusion
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional


class IMUEncoder(nn.Module):
    """IMU sequence encoder (1000Hz -> lower rate)"""
    
    def __init__(
        self,
        input_dim: int = 6,  # acc(3) + gyro(3)
        hidden_dim: int = 128,
        num_layers: int = 2,
        output_dim: int = 256,
        dropout: float = 0.3
    ):
        super().__init__()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        # Downsample IMU from 1000Hz to ~100Hz using conv
        self.downsample = nn.Sequential(
            nn.Conv1d(input_dim, 64, kernel_size=10, stride=10, padding=0),  # 1000->100Hz
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Conv1d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU(),
        )
        
        # LSTM for temporal modeling
        self.lstm = nn.LSTM(
            input_size=128,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0
        )
        
        # Output projection
        self.output_proj = nn.Sequential(
            nn.Linear(hidden_dim * 2, output_dim),
            nn.ReLU(),
            nn.Dropout(0.3)
        )
    
    def forward(self, imu_seq: torch.Tensor) -> torch.Tensor:
        """
        Args:
            imu_seq: (B, T_imu, 6) - IMU sequence at 1000Hz
        Returns:
            (B, T_cam, output_dim) - IMU features at camera rate (~20Hz)
        """
        B, T_imu, _ = imu_seq.shape
        
        # (B, T, 6) -> (B, 6, T)
        x = imu_seq.transpose(1, 2)
        
        # Downsample to camera rate
        x = self.downsample(x)  # (B, 128, T_cam)
        
        # (B, C, T) -> (B, T, C)
        x = x.transpose(1, 2)
        
        # LSTM
        lstm_out, _ = self.lstm(x)  # (B, T_cam, hidden*2)
        
        # Output projection
        out = self.output_proj(lstm_out)  # (B, T_cam, output_dim)
        
        return out


class VisualEncoder(nn.Module):
    """Visual encoder for camera images"""
    
    def __init__(
        self,
        input_channels: int = 1,  # grayscale
        output_dim: int = 256,
        backbone: str = 'resnet18'
    ):
        super().__init__()
        
        if backbone == 'resnet18':
            from torchvision.models import resnet18
            self.backbone = resnet18(pretrained=True)
            # Modify first layer for grayscale
            self.backbone.conv1 = nn.Conv2d(
                input_channels, 64, kernel_size=7, stride=2, padding=3, bias=False
            )
            feat_dim = 512
        elif backbone == 'mobilenet_v2':
            from torchvision.models import mobilenet_v2
            self.backbone = mobilenet_v2(pretrained=True)
            self.backbone.features[0][0] = nn.Conv2d(
                input_channels, 32, kernel_size=3, stride=2, padding=1, bias=False
            )
            feat_dim = 1280
        else:
            raise ValueError(f"Unknown backbone: {backbone}")
        
        # Remove final FC layer
        self.backbone = nn.Sequential(*list(self.backbone.children())[:-1])
        
        # Output projection
        self.proj = nn.Sequential(
            nn.Linear(feat_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, output_dim)
        )
    
    def forward(self, images: torch.Tensor) -> torch.Tensor:
        """
        Args:
            images: (B, T, C, H, W) - sequence of images
        Returns:
            (B, T, output_dim)
        """
        B, T, C, H, W = images.shape
        
        # Flatten batch and time
        x = images.view(B * T, C, H, W)
        
        # Backbone
        feats = self.backbone(x)  # (B*T, feat_dim, 1, 1)
        feats = feats.view(B * T, -1)
        
        # Project
        out = self.proj(feats)  # (B*T, output_dim)
        
        # Reshape back
        out = out.view(B, -1, out.size(-1))
        
        return out


class VIOFusion(nn.Module):
    """Fusion module for IMU + Visual features"""
    
    def __init__(
        self,
        imu_dim: int = 256,
        visual_dim: int = 256,
        hidden_dim: int = 512,
        output_dim: int = 256,
        num_layers: int = 2,
        fusion_type: str = 'attention'  # 'attention', 'concat', 'cross_attention'
    ):
        super().__init__()
        self.fusion_type = fusion_type
        
        if fusion_type == 'attention':
            # Self-attention fusion
            self.fusion = nn.MultiheadAttention(
                embed_dim=imu_dim + visual_dim,
                num_heads=8,
                batch_first=True
            )
            self.norm = nn.LayerNorm(imu_dim + visual_dim)
            self.output_proj = nn.Linear(imu_dim + visual_dim, output_dim)
            
        elif fusion_type == 'cross_attention':
            # Cross attention: IMU queries visual
            self.imu_to_visual = nn.MultiheadAttention(
                embed_dim=imu_dim,
                num_heads=4,
                batch_first=True
            )
            self.visual_to_imu = nn.MultiheadAttention(
                embed_dim=visual_dim,
                num_heads=4,
                batch_first=True
            )
            self.output_proj = nn.Linear(imu_dim + visual_dim, output_dim)
            
        elif fusion_type == 'concat':
            # Simple concatenation + MLP
            self.fusion_mlp = nn.Sequential(
                nn.Linear(imu_dim + visual_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(0.3),
                nn.Linear(hidden_dim, output_dim)
            )
        
        # Temporal modeling after fusion
        self.temporal_lstm = nn.LSTM(
            input_size=output_dim,
            hidden_size=output_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.3
        )
        self.final_proj = nn.Linear(output_dim * 2, output_dim)
    
    def forward(
        self, 
        imu_feat: torch.Tensor,  # (B, T, imu_dim)
        visual_feat: torch.Tensor  # (B, T, visual_dim)
    ) -> torch.Tensor:
        B, T, _ = imu_feat.shape
        
        if self.fusion_type == 'attention':
            # Concatenate and apply self-attention
            combined = torch.cat([imu_feat, visual_feat], dim=-1)  # (B, T, imu+visual)
            attn_out, _ = self.fusion(combined, combined, combined)
            fused = self.norm(combined + attn_out)
            fused = self.output_proj(fused)
            
        elif self.fusion_type == 'cross_attention':
            # IMU attends to visual, visual attends to IMU
            imu_attended, _ = self.imu_to_visual(imu_feat, visual_feat, visual_feat)
            visual_attended, _ = self.visual_to_imu(visual_feat, imu_feat, imu_feat)
            combined = torch.cat([imu_attended, visual_attended], dim=-1)
            fused = self.output_proj(combined)
            
        elif self.fusion_type == 'concat':
            combined = torch.cat([imu_feat, visual_feat], dim=-1)
            fused = self.fusion_mlp(combined)
        
        # Temporal modeling
        lstm_out, _ = self.temporal_lstm(fused)
        out = self.final_proj(lstm_out)
        
        return out


class VIOModel(nn.Module):
    """Complete VIO Model: IMU + Visual -> Pose (position + orientation)"""
    
    def __init__(
        self,
        imu_input_dim: int = 6,
        visual_channels: int = 1,
        imu_hidden: int = 128,
        visual_output: int = 256,
        fusion_dim: int = 256,
        pose_output: int = 7,  # tx, ty, tz, qx, qy, qz, qw
        fusion_type: str = 'attention',
        visual_backbone: str = 'resnet18'
    ):
        super().__init__()
        
        # Encoders
        self.imu_encoder = IMUEncoder(
            input_dim=imu_input_dim,
            hidden_dim=128,
            output_dim=256
        )
        
        self.visual_encoder = VisualEncoder(
            input_channels=visual_channels,
            output_dim=256,
            backbone=visual_backbone
        )
        
        self.fusion = VIOFusion(
            imu_dim=256,
            visual_dim=256,
            output_dim=256,
            fusion_type=fusion_type
        )
        
        # Pose regressor
        self.pose_head = nn.Sequential(
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 7)  # 7D pose
        )
    
    def forward(
        self,
        imu_seq: torch.Tensor,    # (B, T_imu, 6)
        images: torch.Tensor      # (B, T_cam, C, H, W)
    ) -> torch.Tensor:
        """
        Args:
            imu_seq: IMU sequence at 1000Hz
            images: Camera images at ~20Hz
        Returns:
            poses: (B, T_cam, 7) - 7D poses (translation + quaternion)
        """
        # Encode IMU (downsampled to camera rate)
        imu_feat = self.imu_encoder(imu_seq)  # (B, T_cam, 256)
        
        # Encode visual
        visual_feat = self.visual_encoder(images)  # (B, T_cam, 256)
        
        # Fuse
        fused = self.fusion(imu_feat, visual_feat)  # (B, T_cam, 256)
        
        # Regress pose
        poses = self.pose_head(fused)  # (B, T_cam, 7)
        
        return poses


class VIOLoss(nn.Module):
    """VIO Loss: translation + rotation"""
    
    def __init__(
        self,
        trans_weight: float = 1.0,
        rot_weight: float = 1.0,
        use_quat_norm: bool = True
    ):
        super().__init__()
        self.trans_weight = trans_weight
        self.rot_weight = rot_weight
        self.use_quat_norm = use_quat_norm
    
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """
        Args:
            pred: (B, T, 7) - [tx, ty, tz, qx, qy, qz, qw]
            target: (B, T, 7)
        """
        # Translation loss (L2)
        pred_trans = pred[..., :3]
        target_trans = target[..., :3]
        trans_loss = F.mse_loss(pred_trans, target_trans)
        
        # Rotation loss (quaternion distance)
        pred_rot = pred[..., 3:]
        target_rot = target[..., 3:]
        
        if self.use_quat_norm:
            # Normalize quaternions
            pred_rot = F.normalize(pred_rot, p=2, dim=-1)
            target_rot = F.normalize(target_rot, p=2, dim=-1)
        
        # Quaternion distance: 1 - |q1·q2|
        dot = torch.sum(pred_rot * target_rot, dim=-1)
        dot = torch.clamp(torch.abs(dot), 0, 1)
        rot_loss = torch.mean(1 - dot)
        
        total_loss = self.trans_weight * trans_loss + self.rot_weight * rot_loss
        return total_loss


def create_vio_model(config: dict = None) -> VIOModel:
    """Factory function to create VIO model from config"""
    config = config or {}
    return VIOModel(
        imu_input_dim=config.get('imu_input_dim', 6),
        visual_channels=config.get('visual_channels', 1),
        imu_hidden=config.get('imu_hidden', 128),
        visual_output=config.get('visual_output', 256),
        fusion_dim=config.get('fusion_dim', 256),
        pose_output=config.get('pose_output', 7),
        fusion_type=config.get('fusion_type', 'attention'),
        visual_backbone=config.get('visual_backbone', 'resnet18')
    )


if __name__ == '__main__':
    # Test model
    device = torch.device('cpu')
    
    model = VIOModel(
        imu_input_dim=6,
        visual_channels=1,
        fusion_type='attention'
    ).to(device)
    
    print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Dummy inputs
    B, T_imu, T_cam = 2, 5000, 100  # 1000Hz IMU for 5s, 20Hz cam for 5s
    imu_seq = torch.randn(B, T_imu, 6).to(device)
    images = torch.randn(B, T_cam, 1, 240, 320).to(device)
    
    with torch.no_grad():
        poses = model(imu_seq, images)
    
    print(f"Input IMU: {imu_seq.shape}")
    print(f"Input Images: {images.shape}")
    print(f"Output Poses: {poses.shape}")
    
    # Test loss
    loss_fn = VIOLoss()
    target = torch.randn_like(poses)
    loss = loss_fn(poses, target)
    print(f"Loss: {loss.item():.4f}")
    
    print("\nVIO Model test passed!")