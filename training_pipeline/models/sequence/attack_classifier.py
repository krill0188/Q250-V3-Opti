"""
Sequence Models for FAN-GHETS24, FANET
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class AttentionPooling(nn.Module):
    """Attention-based 시퀀스 풀링"""

    def __init__(self, hidden_dim: int, num_heads: int = 8, dropout: float = 0.1):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = hidden_dim // num_heads
        assert hidden_dim % num_heads == 0

        self.q_proj = nn.Linear(hidden_dim, hidden_dim)
        self.k_proj = nn.Linear(hidden_dim, hidden_dim)
        self.v_proj = nn.Linear(hidden_dim, hidden_dim)
        self.out_proj = nn.Linear(hidden_dim, hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.scale = self.head_dim**-0.5

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, T, H) - padded sequences
            lengths: (B,) - actual sequence lengths
        Returns:
            (B, H) - pooled representation
        """
        B, T, H = x.shape

        # Multi-head attention with self
        q = self.q_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)

        # Attention scores
        attn = torch.matmul(q, k.transpose(-2, -1)) * self.scale  # (B, heads, T, T)

        # Length-based masking
        mask = torch.arange(T, device=x.device).unsqueeze(0) >= lengths.unsqueeze(1)  # (B, T)
        mask = mask.unsqueeze(1).unsqueeze(2)  # (B, 1, 1, T)
        attn = attn.masked_fill(mask, -1e9)

        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)

        # Apply attention
        out = torch.matmul(attn, v)  # (B, heads, T, head_dim)
        out = out.transpose(1, 2).contiguous().view(B, T, H)
        out = self.out_proj(out)

        # Global average pooling over valid timesteps
        mask_valid = torch.arange(T, device=x.device).unsqueeze(0) < lengths.unsqueeze(1)  # (B, T)
        mask_valid = mask_valid.unsqueeze(-1).float()  # (B, T, 1)
        out = (out * mask_valid).sum(dim=1) / lengths.unsqueeze(1).float()  # (B, H)

        return out


class BiLSTMAttentionClassifier(nn.Module):
    """BiLSTM + Attention 시퀀스 분류기"""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 256,
        num_layers: int = 2,
        num_classes: int = 4,
        dropout: float = 0.3,
        bidirectional: bool = True,
        attention_heads: int = 8,
        fc_hidden: int = 128,
    ):
        super().__init__()

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        self.num_directions = 2 if bidirectional else 1

        # LSTM
        self.lstm = nn.LSTM(
            input_dim,
            hidden_dim,
            num_layers,
            batch_first=True,
            bidirectional=bidirectional,
            dropout=dropout if num_layers > 1 else 0,
        )

        # Attention pooling
        lstm_out_dim = hidden_dim * self.num_directions
        self.attention = AttentionPooling(lstm_out_dim, attention_heads, dropout)

        # Classifier
        self.classifier = nn.Sequential(
            nn.LayerNorm(lstm_out_dim),
            nn.Dropout(dropout),
            nn.Linear(lstm_out_dim, fc_hidden),
            nn.GELU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(fc_hidden, num_classes),
        )

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (B, T, D) - padded sequences
            lengths: (B,) - actual sequence lengths
        Returns:
            (B, num_classes) - logits
        """
        # Pack padded sequence for efficient LSTM
        packed = nn.utils.rnn.pack_padded_sequence(
            x, lengths.cpu(), batch_first=True, enforce_sorted=False
        )

        # LSTM
        packed_out, _ = self.lstm(packed)

        # Unpack
        out, _ = nn.utils.rnn.pad_packed_sequence(packed_out, batch_first=True)
        # out: (B, T, H * num_directions)

        # Attention pooling
        pooled = self.attention(out, lengths)  # (B, H * num_directions)

        # Classification
        logits = self.classifier(pooled)
        return logits


class LSTMClassifier(nn.Module):
    """Simple LSTM Classifier (baseline)"""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 256,
        num_layers: int = 2,
        num_classes: int = 4,
        dropout: float = 0.3,
        bidirectional: bool = True,
    ):
        super().__init__()

        self.lstm = nn.LSTM(
            input_dim,
            hidden_dim,
            num_layers,
            batch_first=True,
            bidirectional=bidirectional,
            dropout=dropout if num_layers > 1 else 0,
        )

        lstm_out_dim = hidden_dim * (2 if bidirectional else 1)
        self.classifier = nn.Sequential(
            nn.LayerNorm(lstm_out_dim),
            nn.Dropout(dropout),
            nn.Linear(lstm_out_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        packed = nn.utils.rnn.pack_padded_sequence(
            x, lengths.cpu(), batch_first=True, enforce_sorted=False
        )
        packed_out, (h_n, _) = self.lstm(packed)

        # Use last hidden state (bidirectional: concat last forward + last backward)
        if self.lstm.bidirectional:
            h_n = h_n.view(self.lstm.num_layers, 2, x.size(0), self.lstm.hidden_size)
            last_h = torch.cat([h_n[-1, 0], h_n[-1, 1]], dim=-1)  # (B, 2*H)
        else:
            last_h = h_n[-1]  # (B, H)

        return self.classifier(last_h)


class TransformerClassifier(nn.Module):
    """Transformer Encoder 기반 분류기"""

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 256,
        num_layers: int = 4,
        num_classes: int = 4,
        num_heads: int = 8,
        dropout: float = 0.1,
        max_seq_len: int = 2048,
    ):
        super().__init__()

        self.input_proj = nn.Linear(input_dim, hidden_dim)
        self.pos_encoding = nn.Parameter(torch.randn(1, max_seq_len, hidden_dim) * 0.02)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers)

        self.classifier = nn.Sequential(
            nn.LayerNorm(hidden_dim),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(hidden_dim // 2, num_classes),
        )

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        B, T, D = x.shape

        # Input projection + positional encoding
        x = self.input_proj(x) + self.pos_encoding[:, :T, :]

        # Length-based attention mask
        mask = torch.arange(T, device=x.device).unsqueeze(0) >= lengths.unsqueeze(1)  # (B, T)

        # Transformer
        out = self.transformer(x, src_key_padding_mask=mask)  # (B, T, H)

        # Global average pooling over valid timesteps
        mask_valid = (~mask).unsqueeze(-1).float()
        pooled = (out * mask_valid).sum(dim=1) / lengths.unsqueeze(1).float()

        return self.classifier(pooled)


class CNN1DClassifier(nn.Module):
    """1D CNN 기반 분류기"""

    def __init__(
        self,
        input_dim: int,
        num_classes: int = 4,
        channels: list = [64, 128, 256],
        kernel_sizes: list = [3, 5, 7],
        dropout: float = 0.3,
    ):
        super().__init__()

        self.convs = nn.ModuleList()
        in_ch = input_dim
        for out_ch, k in zip(channels, kernel_sizes):
            self.convs.append(
                nn.Sequential(
                    nn.Conv1d(in_ch, out_ch, kernel_size=k, padding=k // 2),
                    nn.BatchNorm1d(out_ch),
                    nn.GELU(),
                    nn.MaxPool1d(2),
                )
            )
            in_ch = out_ch

        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(channels[-1], channels[-1] // 2),
            nn.GELU(),
            nn.Dropout(dropout * 0.5),
            nn.Linear(channels[-1] // 2, num_classes),
        )

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        # x: (B, T, D) -> (B, D, T)
        x = x.transpose(1, 2)

        for conv in self.convs:
            x = conv(x)

        x = self.global_pool(x).squeeze(-1)  # (B, C)
        return self.classifier(x)


def get_model(model_type: str, **kwargs) -> nn.Module:
    """모델 팩토리"""
    models = {
        "bilstm_attention": BiLSTMAttentionClassifier,
        "lstm": LSTMClassifier,
        "transformer": TransformerClassifier,
        "1dcnn": CNN1DClassifier,
    }
    if model_type not in models:
        raise ValueError(f"Unknown model type: {model_type}. Available: {list(models.keys())}")
    return models[model_type](**kwargs)
