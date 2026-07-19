import tomllib
from importlib import resources
from pathlib import Path

from redteam_benchmark import __version__
from redteam_benchmark.calibration import DatasetSplit, load_evaluator_dataset


def test_runtime_version_matches_project_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert __version__ == project["project"]["version"]


def test_packaged_evaluator_resources_are_loadable() -> None:
    package_root = resources.files("redteam_benchmark.datasets.calibration")

    assert package_root.joinpath("manifest_v1.json").is_file()
    assert package_root.joinpath("annotation_record.schema.json").is_file()
    assert load_evaluator_dataset(DatasetSplit.DEVELOPMENT).examples
    assert load_evaluator_dataset(DatasetSplit.CALIBRATION).examples


def test_packaged_alembic_resources_are_present() -> None:
    migration_root = resources.files("redteam_benchmark.migrations")

    assert migration_root.joinpath("env.py").is_file()
    assert migration_root.joinpath("versions", "0001_initial_schema.py").is_file()
