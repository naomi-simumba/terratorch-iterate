"""
This module defines all the types expected at input. Used for type checking by jsonargparse.
"""
import enum
from dataclasses import dataclass, field
from typing import Any

import torch
from terratorch.datasets import HLSBands
from terratorch.tasks import (
    IBMClassificationTask,
    IBMPixelwiseRegressionTask,
    IBMSemanticSegmentationTask,
)
from torchgeo.datamodules import BaseDataModule

valid_task_types = type[
    IBMSemanticSegmentationTask | IBMClassificationTask | IBMPixelwiseRegressionTask
]


class TaskTypeEnum(enum.Enum):
    """
    Enum for the type of task to be performed. segmentation, regression or classification.
    """

    segmentation = "segmentation"
    regression = "regression"
    classification = "classification"

    def get_class_from_enum(
        self,
    ) -> valid_task_types:
        match self:
            case TaskTypeEnum.segmentation:
                return IBMSemanticSegmentationTask
            case TaskTypeEnum.regression:
                return IBMPixelwiseRegressionTask
            case TaskTypeEnum.classification:
                return IBMClassificationTask
            case _:
                raise TypeError("Task type does not exist")


class ParameterTypeEnum(enum.Enum):
    """
    Enum for the type of parameter allowed in ParameterBounds. integer or real.
    """

    integer = "int"
    real = "real"


@dataclass
class ParameterBounds:
    """
    Dataclass defining a numerical range to search over.

    Args:
        min (float | int): Minimum.
        max (float | int): Maximum.
        type (ParameterTypeEnum): Whether the range is in the space of integers or real numbers.
        log (bool): Whether to search over the log space (useful for parameters that vary wildly in scale, e.g. learning rate)
    """

    min: float | int
    max: float | int
    type: ParameterTypeEnum
    log: bool = False


# jsonargparse does not seem to support recursive type defs, so support up to one level of nesting
optimization_space_type = dict[str, list | ParameterBounds]


@dataclass
class Backbone:
    """
    Description of backbone to be used.

    Overriding the backbone path can be done with:
    ```
    backbone:
        backbone_args:
            pretrained_cfg_overlay:
                file: <path>
    ```

    Using a backbone with no pretraining can be done with:
    ```
    backbone:
    backbone_args:
        pretrained: False
    ```

    Args:
        backbone (str | torch.nn.Module): Name of the backbone in TerraTorch or torch.nn.Module to pass to the model factory
        model_factory (str): Name of the model factory to be used in TerraTorch
        backbone_args (dict): Arguments to be passed to the backbone.
    """

    backbone: str | torch.nn.Module
    model_factory: str = "PrithviModelFactory"
    backbone_args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """
    Description of task.

    Args:
        name (str): Name for this task
        name (TaskTypeEnum): Type of task.
        bands (list[HLSBands | int]): Bands used in this task.
        datamodule (BaseDataModule): Datamodule to be used.
        decoder (str): Name of decoder in TerraTorch.
        loss (str): Name of loss.
        metric (str): Metric to optimize over for hyperparameter search. Defaults to "val/loss".
        lr (float): Learning rate. Defaults to 1e-3.
        max_epochs (int): Maximum number of epochs for each training job in this task.
        freeze_backbone (bool): Whether to freeze this backbone.
        num_classes (int | None): Number of classes. Needed only for classification or segmentation. Defaults to None.
        backbone_args (dict): Arguments to be passed to the backbone.
        decoder_args (dict): Arguments to be passed to the decoder.
        head_args (dict): Arguments to be passed to the head.
        ignore_index (int | None): Index to ignore in task.
        early_prune (bool): Whether to prune unpromising runs early. When this is true, a larger number of trials can / should be used. Defaults to False.
        optimization_except (set[str]): Keys from hyperparameter space to ignore for this task.
    """

    name: str
    type: TaskTypeEnum
    bands: list[HLSBands | int]
    datamodule: BaseDataModule
    decoder: str
    loss: str
    metric: str = "val/loss"
    lr: float = 1e-3
    max_epochs: int = 100
    freeze_backbone: bool = False
    num_classes: int | None = None
    backbone_args: dict[str, Any] = field(default_factory=dict)
    decoder_args: dict[str, Any] = field(default_factory=dict)
    head_args: dict[str, Any] = field(default_factory=dict)
    ignore_index: int | None = None
    early_prune: bool = False
    optimization_except: set[str] = field(default_factory=set)


def build_model_args(backbone: Backbone, task: Task) -> dict[str, Any]:
    args = {}
    args["backbone"] = backbone.backbone
    args["pretrained"] = backbone.backbone_args.pop("pretrained", True)
    for backbone_key, backbone_val in backbone.backbone_args.items():
        args[f"backbone_{backbone_key}"] = backbone_val

    # allow each task to specify / overwrite backbone keys
    for backbone_key, backbone_val in task.backbone_args.items():
        args[f"backbone_{backbone_key}"] = backbone_val

    args["decoder"] = task.decoder
    for decoder_key, decoder_val in task.decoder_args.items():
        args[f"decoder_{decoder_key}"] = decoder_val

    for head_key, head_val in task.head_args.items():
        args[f"head_{head_key}"] = head_val

    args["in_channels"] = len(task.bands)
    args["bands"] = task.bands

    if task.type != TaskTypeEnum.regression:
        if task.num_classes is not None:
            args["num_classes"] = task.num_classes
        else:
            if hasattr(task.datamodule, "num_classes"):
                args["num_classes"] = task.datamodule.num_classes
            elif hasattr(task.datamodule.dataset, "classes"):
                args["num_classes"] = len(task.datamodule.dataset.classes)
            else:
                raise Exception(
                    f"Could not infer num_classes. Please provide it explicitly for task {task.name}"
                )
    return args
