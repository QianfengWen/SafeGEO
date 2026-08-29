#!/usr/bin/env python3
"""Regenerate mitigation figures with descriptive strategy labels.

The plotting inputs are the paper's reported aggregate, package, and vertical
results under ``results/``.  Strategy codes are deliberately omitted from all
visible labels: the codes are implementation identifiers, not ordered levels.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.lines import Line2D


MODELS = ["Gemma", "Qwen", "Devstral"]
STRATEGIES = [
    "Defensive prompt",
    "Rationale elicitation",
    "Evidence breakdown",
    "Context balancing",
    "Instruction filtering",
]
PACKAGES = [
    "Caveat-\nburied FAQ",
    "Popularity-\nheavy profile",
    "Citation-\npadded note",
    "Independent\nbuyer guide",
    "False-fit\nchecklist",
    "Selective\ncomparison\nnote",
    "AI-directed\nsource text",
    "Full-stack\nrealistic",
]
PACKAGE_KEYS = [
    "Caveat-buried FAQ",
    "Popularity-heavy profile",
    "Citation-padded note",
    "Independent buyer guide",
    "False-fit checklist",
    "Selective comparison note",
    "AI-directed source text",
    "Full-stack realistic",
]
VERTICALS = [
    "AI meeting transcription",
    "Baby monitor",
    "Carry-on backpack",
    "Home air purifier",
    "Noise-canceling headphones",
    "Office chair",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def save(fig: mpl.figure.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.04, metadata={"Creator": "SafeGEO"})
    plt.close(fig)


def annotate_heatmap(
    ax: mpl.axes.Axes,
    values: np.ndarray,
    *,
    threshold: float = 28,
    fontsize: float = 10.0,
) -> None:
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            value = values[row, col]
            color = "white" if abs(value) >= threshold else "#202124"
            ax.text(col, row, f"{value:.1f}", ha="center", va="center", fontsize=fontsize, color=color)


def package_matrix(rows: list[dict[str, str]], model: str) -> np.ndarray:
    lookup = {
        (row["model"], row["strategy"], row["package"]): float(row["target_reduction_pp"])
        for row in rows
    }
    return np.array([[lookup[(model, strategy, package)] for package in PACKAGE_KEYS] for strategy in STRATEGIES])


def draw_main_heatmap(rows: list[dict[str, str]], path: Path) -> None:
    values = package_matrix(rows, "Gemma")
    cmap = LinearSegmentedColormap.from_list("safegeo_green", ["#fffaf0", "#d9f0d3", "#78c679", "#238443"])
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    image = ax.imshow(values, cmap=cmap, vmin=0, vmax=50, aspect="auto")
    annotate_heatmap(ax, values, threshold=36, fontsize=11.2)
    ax.set_xticks(
        range(len(PACKAGE_KEYS)),
        PACKAGE_KEYS,
        rotation=32,
        ha="right",
        fontsize=9.2,
    )
    ax.set_yticks(range(len(STRATEGIES)), STRATEGIES, fontsize=10.5)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.027, pad=0.02)
    colorbar.set_label("Target@3 reduction vs. No mitigation (pp)", fontsize=10)
    colorbar.ax.tick_params(labelsize=9)
    fig.subplots_adjust(left=0.26, right=0.9, bottom=0.32, top=0.98)
    save(fig, path)


def draw_aggregate_panels(rows: list[dict[str, str]], path: Path) -> None:
    lookup = {(row["model"], row["strategy"]): row for row in rows}
    metrics = [
        ("target_reduction_pp", "Target@3 reduction\nvs. No mitigation (pp)"),
        ("hcv_reduction_pp", "HCV@1 reduction\nvs. No mitigation (pp)"),
        ("undcg_delta_pp", "uNDCG@5 change\nvs. No mitigation (pp)"),
    ]
    cmap = mpl.colormaps["RdYlGn"]
    fig, axes = plt.subplots(1, 3, figsize=(12.2, 5.4), constrained_layout=False)
    for ax, (field, title) in zip(axes, metrics):
        values = np.array(
            [[float(lookup[(model, strategy)][field]) for strategy in STRATEGIES] for model in MODELS]
        )
        bound = max(10.0, float(np.ceil(np.abs(values).max() / 5.0) * 5.0))
        image = ax.imshow(values, cmap=cmap, norm=TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound), aspect="auto")
        for row in range(values.shape[0]):
            for col in range(values.shape[1]):
                value = values[row, col]
                ax.text(col, row, f"{value:+.1f}", ha="center", va="center", fontsize=9.5)
        ax.set_title(title, fontsize=11.5, pad=9)
        ax.set_xticks(range(len(STRATEGIES)), STRATEGIES, rotation=34, ha="right", fontsize=9.3)
        ax.set_yticks(range(len(MODELS)), MODELS, fontsize=10)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.025)
        colorbar.ax.tick_params(labelsize=8.5)
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.31, top=0.83, wspace=0.36)
    save(fig, path)


def draw_all_models_heatmap(rows: list[dict[str, str]], path: Path) -> None:
    matrices = [package_matrix(rows, model) for model in MODELS]
    bound = float(np.ceil(max(np.abs(matrix).max() for matrix in matrices) / 5.0) * 5.0)
    norm = TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound)
    model_titles = ["Gemma 4 31B IT", "Qwen3.6 27B", "Devstral Small 2\n24B Instruct"]
    fig, axes = plt.subplots(3, 1, figsize=(11.0, 9.4), constrained_layout=False)
    for index, (ax, model, values) in enumerate(zip(axes, model_titles, matrices)):
        image = ax.imshow(values, cmap="RdYlGn", norm=norm, aspect="auto")
        annotate_heatmap(ax, values, threshold=36, fontsize=10.0)
        ax.set_title(model, fontsize=12, pad=7, weight="semibold")
        if index == len(axes) - 1:
            ax.set_xticks(
                range(len(PACKAGE_KEYS)),
                PACKAGE_KEYS,
                rotation=28,
                ha="right",
                fontsize=9.0,
            )
        else:
            ax.set_xticks(range(len(PACKAGE_KEYS)), [])
        ax.set_yticks(range(len(STRATEGIES)), STRATEGIES, fontsize=9.5)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.subplots_adjust(left=0.22, right=0.88, bottom=0.19, top=0.96, hspace=0.38)
    colorbar_ax = fig.add_axes([0.91, 0.22, 0.016, 0.68])
    colorbar = fig.colorbar(image, cax=colorbar_ax)
    colorbar.set_label("Target@3 reduction vs. No mitigation (pp)", fontsize=10)
    colorbar.ax.tick_params(labelsize=9)
    save(fig, path)


def draw_tradeoff(rows: list[dict[str, str]], path: Path) -> None:
    colors = {"Gemma": "#2a6fbb", "Qwen": "#db4b3f", "Devstral": "#3d9b58"}
    markers = {
        "Defensive prompt": "o",
        "Rationale elicitation": "s",
        "Evidence breakdown": "^",
        "Context balancing": "D",
        "Instruction filtering": "P",
    }
    fig, ax = plt.subplots(figsize=(8.2, 5.8))
    for row in rows:
        if row["strategy"] == "No mitigation":
            continue
        ax.scatter(
            float(row["undcg_delta_pp"]),
            float(row["target_reduction_pp"]),
            s=75,
            c=colors[row["model"]],
            marker=markers[row["strategy"]],
            edgecolor="white",
            linewidth=0.7,
            zorder=3,
        )
    ax.axhline(0, color="#858585", linewidth=0.8)
    ax.axvline(0, color="#858585", linewidth=0.8)
    ax.grid(True, color="#e5e5e5", linewidth=0.7, zorder=0)
    ax.set_xlabel("uNDCG@5 change vs. No mitigation (pp)")
    ax.set_ylabel("Target@3 reduction vs. No mitigation (pp)")
    model_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=colors[model], markeredgecolor="white", markersize=8, label=model)
        for model in MODELS
    ]
    strategy_handles = [
        Line2D([0], [0], marker=markers[strategy], color="#4a4a4a", linestyle="none", markersize=7, label=strategy)
        for strategy in STRATEGIES
    ]
    first = ax.legend(handles=model_handles, title="Model", loc="upper left", frameon=True)
    ax.add_artist(first)
    ax.legend(handles=strategy_handles, title="Mitigation strategy", loc="lower right", ncols=2, fontsize=9.2, title_fontsize=10)
    fig.subplots_adjust(left=0.12, right=0.98, bottom=0.12, top=0.98)
    save(fig, path)


def draw_vertical_heatmap(rows: list[dict[str, str]], path: Path) -> None:
    lookup = {(row["model"], row["vertical"]): float(row["target_reduction_pp"]) for row in rows}
    values = np.array([[lookup[(model, vertical)] for vertical in VERTICALS] for model in MODELS])
    fig, ax = plt.subplots(figsize=(10.0, 3.5))
    image = ax.imshow(values, cmap="YlGn", vmin=0, vmax=60, aspect="auto")
    annotate_heatmap(ax, values, threshold=43, fontsize=10.5)
    ax.set_xticks(range(len(VERTICALS)), [vertical.replace(" ", "\n", 1) for vertical in VERTICALS], fontsize=9.5)
    ax.set_yticks(range(len(MODELS)), MODELS, fontsize=10.5)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.033, pad=0.018)
    colorbar.set_label("Evidence breakdown Target@3 reduction (pp)", fontsize=10)
    colorbar.ax.tick_params(labelsize=9)
    fig.subplots_adjust(left=0.085, right=0.91, bottom=0.28, top=0.98)
    save(fig, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.labelsize": 11,
            "pdf.fonttype": 42,
            "savefig.transparent": False,
        }
    )
    aggregate = read_rows(args.results_dir / "main_models_mitigation.csv")
    packages = read_rows(args.results_dir / "main_models_mitigation_by_package.csv")
    verticals = read_rows(args.results_dir / "main_models_evidence_breakdown_by_vertical.csv")

    draw_main_heatmap(packages, args.output_dir / "rq2_mitigation_heatmap_lightgreen_gemma.pdf")
    draw_main_heatmap(packages, args.output_dir / "main_fig5_mitigation_heatmap.pdf")
    draw_aggregate_panels(aggregate, args.output_dir / "app_fig_b11_mitigation_layer_reductions.pdf")
    draw_all_models_heatmap(packages, args.output_dir / "app_fig_b12_mitigation_package_reductions_all_models.pdf")
    draw_tradeoff(aggregate, args.output_dir / "app_fig_b13_mitigation_tradeoff.pdf")
    draw_vertical_heatmap(verticals, args.output_dir / "app_fig_b14_mitigation_vertical_l3.pdf")


if __name__ == "__main__":
    main()
