from __future__ import annotations

from typing import Any, Dict, Type

import torch
from muutils.json_serialize import (
    serializable_dataclass,
    SerializableDataclass,
    serializable_field,
)
from muutils.tensor_utils import TORCH_OPTIMIZERS_MAP  # type: ignore[import]
from transformer_lens import HookedTransformer  # type: ignore[import]
from transformer_lens import HookedTransformerConfig
from transformers import PreTrainedTokenizer

from maze_transformer.training.dataset import GPTDatasetConfig
from maze_transformer.training.mazedataset import MazeDatasetConfig
from maze_transformer.training.tokenizer import HuggingMazeTokenizer


@serializable_dataclass(kw_only=True)
class BaseGPTConfig(SerializableDataclass):
    """
    Add a name property and serialization to HookedTransformerConfig
    """

    name: str
    act_fn: str
    d_model: int
    d_head: int
    n_layers: int


# ==================================================


def _optimizer_save_fn(x: Type[torch.optim.Optimizer]) -> str:
    x_name: str = x.__name__
    assert x_name in TORCH_OPTIMIZERS_MAP
    assert TORCH_OPTIMIZERS_MAP[x_name] == x
    return x_name


@serializable_dataclass(kw_only=True)
class TrainConfig(SerializableDataclass):
    """full training configuration"""

    name: str

    optimizer: Type[torch.optim.Optimizer] = serializable_field(  # type: ignore
        default_factory=lambda: torch.optim.RMSprop,
        serialization_fn=_optimizer_save_fn,
        loading_fn=lambda data: TORCH_OPTIMIZERS_MAP[data["optimizer"]],
    )

    optimizer_kwargs: dict[str, Any] = serializable_field(  # type: ignore
        default_factory=lambda: dict(lr=0.000001)
    )

    batch_size: int = serializable_field(default=128)

    dataloader_cfg: dict = serializable_field(  # type: ignore
        default_factory=lambda: dict(
            shuffle=True,
            num_workers=16,  # make this smaller if you're not running on a big cluster probably
            persistent_workers=True,
            drop_last=True,
            # collate_fn = None, # we pad the tensors in the Dataset object
            # batch_size = None, # see batchsize in the encompassing TrainConfig
        )
    )

    print_loss_interval: int = serializable_field(default=1000)
    checkpoint_interval: int = serializable_field(default=50000)


# actual configuration setups
# ==================================================

_GPT_CONFIGS_LIST: list[BaseGPTConfig] = [
    BaseGPTConfig(
        name="tiny-v1",
        act_fn="gelu",
        d_model=32,
        d_head=16,
        n_layers=4,
    ),
    BaseGPTConfig(
        name="gpt2-small",
        act_fn="gelu",
        d_model=384,  # half of gpt2-small
        d_head=64,  # match gpt-2 small
        n_layers=12,  # half of gpt2-small
    ),
    # this one is just for integration tests
    BaseGPTConfig(
        name="nano-v1",
        act_fn="gelu",
        d_model=8,
        d_head=4,
        n_layers=2,
    ),
]

GPT_CONFIGS: dict[str, BaseGPTConfig] = {cfg.name: cfg for cfg in _GPT_CONFIGS_LIST}

_TRAINING_CONFIG_LIST: list[TrainConfig] = [
    TrainConfig(
        name="integration-v1",
        optimizer=torch.optim.RMSprop,
        optimizer_kwargs=dict(lr=0.0001),
        batch_size=16,
        dataloader_cfg=dict(
            shuffle=True,
            num_workers=2,
            persistent_workers=True,
            drop_last=False,
        ),
        print_loss_interval=100,
        checkpoint_interval=1000,
    ),
    TrainConfig(
        name="tiny-v1",
        optimizer=torch.optim.RMSprop,
        optimizer_kwargs=dict(lr=0.000001),
        batch_size=32,
        dataloader_cfg=dict(
            shuffle=True,
            num_workers=8,
            persistent_workers=True,
            drop_last=True,
        ),
        print_loss_interval=1000,
        checkpoint_interval=5000,
    ),
    TrainConfig(
        name="gpt2-small",
        optimizer=torch.optim.AdamW,
        optimizer_kwargs=dict(lr=6e-4, weight_decay=1e-1, betas=(0.9, 0.95)),
        batch_size=64,
        dataloader_cfg=dict(
            shuffle=True,
            num_workers=16,
            persistent_workers=True,
            drop_last=True,
        ),
        print_loss_interval=50,
        checkpoint_interval=10000,
    ),
]


TRAINING_CONFIGS: dict[str, TrainConfig] = {
    cfg.name: cfg for cfg in _TRAINING_CONFIG_LIST
}


@serializable_dataclass(kw_only=True)
class ConfigHolder(SerializableDataclass):
    """
    Handles any logic that moves data between the configs below it.
    """

    name: str = serializable_field(default="default")
    train_cfg: TrainConfig
    dataset_cfg: MazeDatasetConfig
    model_cfg: BaseGPTConfig
    tokenizer: PreTrainedTokenizer | None = serializable_field(
        default=None,
        serialization_fn=lambda x: repr(x) if x is not None else None,
        loading_fn=lambda data: None if data["tokenizer"] is None else NotImplementedError,
    )
        # loading_fn=lambda data: HuggingMazeTokenizer(
        #     token_arr=["<PADDING>", "(0,0)"],
        #     seq_len_max=100,
        #     # token_arr = data["dataset_cfg"]["token_arr"].copy(),
        #     # seq_len_max = data["dataset_cfg"]["seq_len_max"],
        #     # MazeDatasetConfig.load(data["dataset_cfg"])
        # ),
    # )

    # def create_model(self) -> HookedTransformer:
    #     hooked_transformer_cfg = HookedTransformerConfig(
    #         act_fn=self.model_cfg.act_fn,
    #         d_model=self.model_cfg.d_model,
    #         d_head=self.model_cfg.d_head,
    #         n_layers=self.model_cfg.n_layers,
    #         n_ctx=self.dataset_cfg.seq_len_max,
    #         d_vocab=len(self.dataset_cfg.token_arr),
    #     )
    #     if self.tokenizer is None and isinstance(self.dataset_cfg, MazeDatasetConfig):
    #         self.tokenizer = HuggingMazeTokenizer(self.dataset_cfg)
    #     return HookedTransformer(cfg=hooked_transformer_cfg, tokenizer=self.tokenizer)
