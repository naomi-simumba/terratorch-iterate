import logging
import uuid
from pathlib import Path
from typing import Any, List
from jsonargparse import ArgumentParser
from benchmark.backbone_benchmark import benchmark_backbone
from benchmark.benchmark_types import Defaults, Task
from benchmark.repeat_best_experiment import rerun_best_from_backbone
from benchmark.utils import get_logger


def main():
    print("Running terratorch-iterate...")
    parser = ArgumentParser()

    parser.add_argument('--defaults', type=Defaults)  # to ignore model
    parser.add_argument('--optimization_space', type=dict)  # to ignore model
    parser.add_argument('--experiment_name', type=str)  # to ignore model
    parser.add_argument('--run_name', type=str)  # to ignore model
    parser.add_argument('--save_models', type=bool)  # to ignore model
    parser.add_argument('--storage_uri', type=str)  # to ignore model
    parser.add_argument('--ray_storage_path', type=str)  # to ignore model
    parser.add_argument('--n_trials', type=int)  # to ignore model
    parser.add_argument('--run_repetitions', type=int)  # to ignore model
    parser.add_argument('--tasks', type=list[Task])
    parser.add_argument("--parent_run_id", type=str)
    parser.add_argument("--output_path", type=str)
    parser.add_argument("--logger", type=str)
    parser.add_argument("--config", action="config")
    parser.add_argument("--hpo", help="optimize hyperparameters", action="store_true")
    parser.add_argument("--repeat", help="repeat best experiments", action="store_true")

    args = parser.parse_args()
    paths: List[Any] = args.config
    path = paths[0]
    repeat = args.repeat
    assert isinstance(repeat, bool), f"Error! {repeat=} is not a bool"
    hpo = args.hpo
    assert isinstance(hpo, bool), f"Error! {hpo=} is not a bool"

    assert (
        hpo is True or repeat is True
    ), f"Error! either {repeat=} or {hpo=} must be True"

    config = parser.parse_path(path)

    config_init = parser.instantiate_classes(config)
    # validate the objects
    experiment_name = config_init.experiment_name
    assert isinstance(experiment_name, str), f"Error! {experiment_name=} is not a str"
    run_name = config_init.run_name
    if run_name is not None:
        assert isinstance(run_name, str), f"Error! {run_name=} is not a str"
    # validate defaults
    defaults = config_init.defaults
    assert isinstance(defaults, Defaults), f"Error! {defaults=} is not a Defaults"

    tasks = config_init.tasks
    assert isinstance(tasks, list), f"Error! {tasks=} is not a list"
    for t in tasks:
        assert isinstance(t, Task), f"Error! {t=} is not a Task"
        # if there is not specific terratorch_task specified, then use default terratorch_task
        if t.terratorch_task is None:
            t.terratorch_task = defaults.terratorch_task
    # defaults.trainer_args["max_epochs"] = 5
    storage_uri = config_init.storage_uri
    assert isinstance(storage_uri, str), f"Error! {storage_uri=} is not a str"

    optimization_space = config_init.optimization_space
    assert isinstance(
        optimization_space, dict
    ), f"Error! {optimization_space=} is not a dict"

    # ray_storage_path is optional
    ray_storage_path = config_init.ray_storage_path
    if ray_storage_path is not None:
        assert isinstance(
            ray_storage_path, str
        ), f"Error! {ray_storage_path=} is not a str"

    n_trials = config_init.n_trials
    assert isinstance(n_trials, int) and n_trials > 0, f"Error! {n_trials=} is invalid"
    run_repetitions = config_init.run_repetitions

    parent_run_id = config_init.parent_run_id
    if parent_run_id is not None:
        assert isinstance(parent_run_id, str), f"Error! {parent_run_id=} is not a str"

    output = config_init.output_path
    if output is None:
        storage_uri_path = Path(storage_uri)
        assert (
            storage_uri_path.exists() and storage_uri_path.is_dir()
        ), f"Error! Unable to create new output_path based on storage_uri_path because the latter does not exist: {storage_uri_path}"
        unique_id = uuid.uuid4().hex
        output_path = storage_uri_path.parents[0] / f"{unique_id}_repeated_exp"
        output_path.mkdir(parents=True, exist_ok=True)
        output = str(output_path)

    logger_path = config_init.logger
    if logger_path is None:
        storage_uri_path = Path(storage_uri)

        logger = get_logger(log_folder=f"{str(storage_uri_path.parents[0])}/job_logs")
    else:
        logging.config.fileConfig(fname=logger_path, disable_existing_loggers=False)
        logger = logging.getLogger("terratorch-iterate")
    if repeat and not hpo:
        logger.info("Rerun best experiments...")
        rerun_best_from_backbone(
            logger=logger,
            parent_run_id=parent_run_id,
            output_path=str(output_path),
            defaults=defaults,
            tasks=tasks,
            experiment_name=experiment_name,
            storage_uri=storage_uri,
            optimization_space=optimization_space,
            run_repetitions=run_repetitions,
        )
    else:
        if not repeat and hpo:
            run_repetitions = 0

        # run_repetions is an optional parameter
        benchmark_backbone(
            defaults=defaults,
            tasks=tasks,
            experiment_name=experiment_name,
            storage_uri=storage_uri,
            ray_storage_path=ray_storage_path,
            run_name=run_name,
            optimization_space=optimization_space,
            n_trials=n_trials,
            run_repetitions=run_repetitions,
        )


if __name__ == "__main__":
    main()
