"""Render the short Track B readout from saved case tables, without fitting models.

From the repository root:
    PYTHONPATH=mould-ac-degradation/src python -m bq2.report_figures
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from .paths import find_repo_root


BLUE = "#326B9D"
ORANGE = "#B86F24"
INK = "#273442"
VARIANTS = ("with_fills", "without_fills")


def _axes_style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#DFE4E8", linewidth=.7)
    ax.tick_params(colors=INK)


def _counts(rows, reference="reference_days", evaluation="evaluation_days"):
    return "; ".join(
        f"{label}: {int(rows.loc[variant, reference])} / {int(rows.loc[variant, evaluation])} days"
        for variant, label in zip(VARIANTS, ("with fills", "observed only"))
    )


def render_report_figures(case_dir=None, figure_dir=None):
    """Export two descriptive figures; original tables and plots are read-only.

    Input versions can select different cohorts. Values are plotted as saved;
    no new adjustment, interval or physical fault classification is introduced.
    """
    analysis = find_repo_root() / "mould-ac-degradation"
    case_dir = Path(case_dir) if case_dir is not None else analysis / "outputs/bq2-case-investigation"
    figure_dir = Path(figure_dir) if figure_dir is not None else analysis / "reports/track-b/figures"
    energy = pd.read_csv(case_dir / "energy_decomposition.csv")
    matched = pd.read_csv(case_dir / "matched_states.csv")
    figure_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "operation": figure_dir / "runtime_and_power.png",
        "moisture": figure_dir / "f7z2_sustained_moisture.png",
    }

    style = {"font.family": "DejaVu Sans", "font.size": 12,
             "axes.labelcolor": INK, "text.color": INK, "figure.facecolor": "white"}
    with plt.rc_context(style):
        fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
        zones = ("F3-Z4", "F5-Z4")
        x = np.arange(len(zones))
        width = .23
        for ax, metric, title, unit, limit, precision in (
            (axes[0], "on_hours", "Time above the AC-on threshold", "Hours/day", 9, 2),
            (axes[1], "on_power", "Average power while above the threshold", "kW", 25, 1),
        ):
            rows = [energy.loc[energy.zone_id.eq(zone)].set_index("variant").loc[list(VARIANTS)]
                    for zone in zones]
            # These two zones have identical 2018 cohorts across input versions.
            # Keep that requirement explicit before showing one reference bar.
            for zone, cohort in zip(zones, rows):
                fields = [f"{metric}_2018", "reference_days"]
                if not cohort[fields].nunique().eq(1).all():
                    raise ValueError(f"{zone}: 2018 input versions differ; plot both references")
            values = [
                [r.loc["with_fills", f"{metric}_2018"] for r in rows],
                [r.loc["with_fills", f"{metric}_2019"] for r in rows],
                [r.loc["without_fills", f"{metric}_2019"] for r in rows],
            ]
            for offset, series, color, hatch in zip(
                (-width, 0, width), values, (BLUE, ORANGE, "white"), (None, None, "///")
            ):
                bars = ax.bar(x + offset, series, width, color=color,
                              edgecolor=ORANGE if hatch else color, hatch=hatch, linewidth=1)
                ax.bar_label(bars, fmt=f"%.{precision}f", padding=4, fontsize=11)
            ax.set(xticks=x, xticklabels=zones, ylabel=unit, ylim=(0, limit), title=title)
            _axes_style(ax)
        fig.suptitle("F3-Z4 ran more continuously; F5-Z4 drew more power", fontsize=17, y=.98)
        fig.legend(handles=[Patch(facecolor=BLUE, label="2018 reference (both input versions)"),
                            Patch(facecolor=ORANGE, label="2019 with fills"),
                            Patch(facecolor="white", edgecolor=ORANGE, hatch="///",
                                  label="2019 observed only")],
                   loc="upper center", bbox_to_anchor=(.5, .91), ncol=3, frameon=False, fontsize=11)
        counts = []
        for zone in zones:
            rows = energy.loc[energy.zone_id.eq(zone)].set_index("variant")
            counts.append(f"{zone} — {_counts(rows)}")
        note = ("July–August 2018 / 2019. Counts below are reference / evaluation days.\n"
                + "\n".join(counts)
                + "\nComplete days; 2019 days selected by the screen's support rules. Descriptive, unadjusted means; no confidence intervals.")
        fig.text(.035, .025, note, fontsize=9.5, va="bottom", linespacing=1.5)
        fig.subplots_adjust(top=.72, bottom=.31, left=.075, right=.98, wspace=.3)
        fig.savefig(paths["operation"], dpi=180, facecolor="white")
        plt.close(fig)

        moisture = matched.loc[
            matched.zone_id.eq("F7-Z2") & matched.state.eq("steady_on")
            & matched.specification.eq("primary") & matched.metric.eq("indoor_w_gkg")
        ].set_index("variant").loc[list(VARIANTS)]
        if not moisture.reportable.eq(True).all():
            raise ValueError("F7-Z2 primary sustained-on comparison is not reportable")
        fig, ax = plt.subplots(figsize=(10, 5.9))
        x = np.arange(2)
        width = .28
        for offset, field, color, year in (
            (-width / 2, "reference_mean", BLUE, "2018 reference"),
            (width / 2, "observed_mean", ORANGE, "2019 evaluation"),
        ):
            bars = ax.bar(x + offset, moisture[field], width, color=color, label=year)
            ax.bar_label(bars, fmt="%.2f", padding=5)
        for pos, (_, row) in zip(x, moisture.iterrows()):
            ax.text(pos, 12.1, f"+{row.mean_change:.2f} g/kg", ha="center", weight="bold", fontsize=14)
        ax.set(xticks=x, xticklabels=["With fills", "Observed only"], ylim=(0, 13),
               ylabel="Indoor moisture (g/kg dry air)")
        _axes_style(ax)
        fig.legend(*ax.get_legend_handles_labels(), loc="upper center",
                   bbox_to_anchor=(.5, .875), ncol=2, frameon=False)
        fig.suptitle("F7-Z2 recorded wetter air while the AC was running", fontsize=17, y=.98)
        fig.text(.5, .91, "July–August 2018 / 2019 • sustained-on hours matched on weather, clock hour and plug activity",
                 ha="center", fontsize=10.5)
        note = (f"Reference / evaluation: {_counts(moisture, 'reference_days', 'matched_days')}.\n"
                "Day-weighted descriptive means; cohorts differ and no confidence intervals are estimated here.\n"
                "Cross-year sensor-error scenarios can erase the moisture increase; reduced AC dehumidification is unconfirmed.")
        fig.text(.075, .025, note, fontsize=9.5, va="bottom", linespacing=1.5)
        fig.subplots_adjust(top=.79, bottom=.25, left=.1, right=.97)
        fig.savefig(paths["moisture"], dpi=180, facecolor="white")
        plt.close(fig)
    return paths


if __name__ == "__main__":
    for name, path in render_report_figures().items():
        print(f"{name}: {path}")
