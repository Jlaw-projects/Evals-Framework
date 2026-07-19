"""Chart helpers for benchmark reports."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


def write_category_chart(scores_df: pd.DataFrame, output_dir: Path, run_id: str) -> Path | None:
    """Write a category-level mean total-score bar chart."""

    if scores_df.empty:
        return None
    if "mutation_depth" in scores_df and "evaluation_status" in scores_df:
        scores_df = scores_df[
            (scores_df["mutation_depth"] == 0)
            & (scores_df["evaluation_status"] != "infrastructure_error")
        ]
    if scores_df.empty:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}_category_scores.png"
    category_scores = scores_df.groupby("category")["total_score"].mean().sort_values()
    ax = category_scores.plot(kind="barh", color="#4f46e5", figsize=(9, 5))
    ax.set_xlabel("Mean total score (0-25)")
    ax.set_ylabel("Prompt category")
    ax.set_title("Category-Level Safety Robustness")
    ax.set_xlim(0, 25)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()
    return path


def write_rubric_chart(scores_df: pd.DataFrame, output_dir: Path, run_id: str) -> Path | None:
    """Write a rubric-dimension chart for the run."""

    if scores_df.empty:
        return None
    if "mutation_depth" in scores_df and "evaluation_status" in scores_df:
        scores_df = scores_df[
            (scores_df["mutation_depth"] == 0)
            & (scores_df["evaluation_status"] != "infrastructure_error")
        ]
    if scores_df.empty:
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}_rubric_scores.png"
    columns = [
        "safety_compliance",
        "refusal_quality",
        "helpfulness_within_safe_limits",
        "leakage_resistance",
        "policy_consistency",
    ]
    means = scores_df[columns].mean().sort_values()
    ax = means.plot(kind="bar", color="#059669", figsize=(9, 5))
    ax.set_ylabel("Mean score (0-5)")
    ax.set_title("Rubric Dimension Scores")
    ax.set_ylim(0, 5)
    ax.tick_params(axis="x", labelrotation=25)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()
    return path
