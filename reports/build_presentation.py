"""Build an editable, evidence-led presentation for the forecasting project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image as PILImage, ImageChops
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "Day_Ahead_Electricity_Forecasting_Presentation.pptx"
ASSETS = ROOT / "reports" / "presentation_assets"
PREDICTIONS = ROOT / "outputs" / "backtest_predictions.csv"
PRICES = ROOT / "data" / "day_ahead_prices.csv"
METRICS = ROOT / "outputs" / "metrics.json"

SW, SH = 13.333, 7.5
BG = "F5F4EF"
PANEL = "FFFFFF"
PANEL_ALT = "E8EEEB"
INK = "20333D"
MUTED = "5D6D73"
TEAL = "1B7770"
BLUE = "416C88"
ORANGE = "B46A3B"
RED = "A84F45"
GRID = "D1D9D6"
FONT = "Aptos"


def rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def add_text(
    slide: Any,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 16,
    color: str = INK,
    bold: bool = False,
    align: Any = PP_ALIGN.LEFT,
    valign: Any = MSO_ANCHOR.TOP,
) -> Any:
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = shape.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(0)
    frame.margin_right = Inches(0)
    frame.margin_top = Inches(0)
    frame.margin_bottom = Inches(0)
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    return shape


def add_rect(
    slide: Any,
    x: float,
    y: float,
    w: float,
    h: float,
    color: str,
    *,
    shape_type: MSO_SHAPE = MSO_SHAPE.RECTANGLE,
) -> Any:
    shape = slide.shapes.add_shape(
        shape_type, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(color)
    shape.line.fill.background()
    return shape


def add_rule(
    slide: Any,
    x: float,
    y: float,
    w: float,
    color: str = GRID,
    thickness: float = 0.012,
) -> None:
    add_rect(slide, x, y, w, thickness, color)


def add_picture(slide: Any, path: Path, x: float, y: float, w: float, h: float) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Presentation image is missing: {path}")
    with PILImage.open(path) as image:
        image_ratio = image.width / image.height
    box_ratio = w / h
    if image_ratio > box_ratio:
        picture_w = w
        picture_h = w / image_ratio
        picture_x = x
        picture_y = y + (h - picture_h) / 2
    else:
        picture_h = h
        picture_w = h * image_ratio
        picture_x = x + (w - picture_w) / 2
        picture_y = y
    slide.shapes.add_picture(
        str(path),
        Inches(picture_x),
        Inches(picture_y),
        Inches(picture_w),
        Inches(picture_h),
    )


def add_footer(slide: Any, index: int, source: str = "DAY-AHEAD FORECASTING  •  TSA LAB AAT") -> None:
    add_rule(slide, 0.75, 7.08, 11.83)
    add_text(slide, source, 0.78, 7.16, 10.7, 0.16, size=8, color=MUTED)
    add_text(
        slide,
        f"{index:02d}",
        12.05,
        7.14,
        0.5,
        0.2,
        size=9,
        color=TEAL,
        bold=True,
        align=PP_ALIGN.RIGHT,
    )


def new_slide(prs: Presentation, title: str, section: str) -> Any:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(BG)
    add_text(slide, section.upper(), 0.75, 0.38, 7.4, 0.22, size=9, color=TEAL, bold=True)
    add_text(slide, title, 0.75, 0.72, 11.9, 0.54, size=25, color=INK, bold=True)
    add_rule(slide, 0.75, 1.41, 11.83)
    return slide


def add_fact(
    slide: Any,
    x: float,
    y: float,
    label: str,
    value: str,
    detail: str,
    width: float = 2.7,
) -> None:
    add_text(slide, label.upper(), x, y, width, 0.2, size=9, color=TEAL, bold=True)
    add_text(slide, value, x, y + 0.29, width, 0.45, size=23, color=INK, bold=True)
    add_text(slide, detail, x, y + 0.8, width, 0.55, size=11, color=MUTED)


def add_numbered_point(
    slide: Any,
    x: float,
    y: float,
    number: str,
    title: str,
    body: str,
    width: float,
    accent: str = TEAL,
) -> None:
    add_text(slide, number, x, y, 0.52, 0.28, size=12, color=accent, bold=True)
    add_text(slide, title, x + 0.62, y, width - 0.62, 0.3, size=14, color=INK, bold=True)
    add_text(slide, body, x + 0.62, y + 0.4, width - 0.62, 0.7, size=11, color=MUTED)


def add_table(
    slide: Any,
    rows: list[list[str]],
    x: float,
    y: float,
    w: float,
    h: float,
    widths: list[float],
) -> None:
    table_shape = slide.shapes.add_table(
        len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(h)
    )
    table = table_shape.table
    for column, width in zip(table.columns, widths):
        column.width = Inches(width)
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            cell = table.cell(row_index, column_index)
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(
                PANEL_ALT if row_index == 0 else (PANEL if row_index == 1 else BG)
            )
            cell.margin_left = Inches(0.09)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.05)
            cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            paragraph = cell.text_frame.paragraphs[0]
            paragraph.alignment = PP_ALIGN.LEFT if column_index == 0 else PP_ALIGN.CENTER
            run = paragraph.add_run()
            run.text = value
            run.font.name = FONT
            run.font.size = Pt(9 if row_index == 0 else 10)
            run.font.bold = row_index == 0 or column_index == 0
            run.font.color.rgb = rgb(TEAL if row_index == 0 else INK)


def save_figures(
    predictions: pd.DataFrame,
    prices: pd.DataFrame,
    metrics: dict[str, Any],
) -> dict[str, Path]:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name in ("dashboard_top", "forecast_chart", "selected_day_table", "model_comparison"):
        screenshot = ASSETS / f"{name}.png"
        if screenshot.is_file():
            with PILImage.open(screenshot) as image:
                page = image.convert("RGB")
                white = PILImage.new("RGB", page.size, (255, 255, 255))
                bounds = ImageChops.difference(page, white).getbbox()
                if bounds:
                    page.crop(bounds).save(ASSETS / f"{name}_cropped.png")

    plt.rcParams.update(
        {
            "figure.facecolor": f"#{BG}",
            "axes.facecolor": f"#{PANEL}",
            "axes.edgecolor": f"#{GRID}",
            "axes.labelcolor": f"#{MUTED}",
            "xtick.color": f"#{MUTED}",
            "ytick.color": f"#{MUTED}",
            "text.color": f"#{INK}",
            "grid.color": f"#{GRID}",
            "font.family": "Arial",
            "font.size": 10,
        }
    )
    paths = {
        "eda": ASSETS / "presentation_eda.png",
        "forecast": ASSETS / "presentation_forecast.png",
        "metrics": ASSETS / "presentation_metrics.png",
    }

    frame = prices.copy()
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    daily = frame.set_index("timestamp_utc")["price_eur_mwh"].resample("D").mean()
    hourly = frame.assign(hour=frame["timestamp_utc"].dt.hour).groupby("hour")[
        "price_eur_mwh"
    ].median()
    fig, axes = plt.subplots(
        2, 1, figsize=(10, 5.2), gridspec_kw={"height_ratios": [1.35, 1]}
    )
    fig.subplots_adjust(hspace=0.46, left=0.1, right=0.98, top=0.94, bottom=0.1)
    axes[0].plot(daily.index, daily, color=f"#{BLUE}", linewidth=1.35)
    axes[0].set_title("Daily average price", loc="left", fontsize=12, fontweight="bold")
    axes[0].set_ylabel("EUR/MWh")
    axes[0].xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    axes[0].grid(alpha=0.45)
    axes[0].spines[["top", "right"]].set_visible(False)
    axes[1].plot(hourly.index, hourly.values, color=f"#{ORANGE}", marker="o", markersize=3, linewidth=1.8)
    axes[1].set_title("Median price by UTC hour", loc="left", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Hour of day (UTC)")
    axes[1].set_ylabel("EUR/MWh")
    axes[1].set_xticks(range(0, 24, 2))
    axes[1].grid(alpha=0.45)
    axes[1].spines[["top", "right"]].set_visible(False)
    fig.savefig(paths["eda"], dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    recent = predictions.tail(7 * 24)
    times = pd.to_datetime(recent["timestamp_utc"], utc=True)
    fig, ax = plt.subplots(figsize=(11, 4.4))
    fig.subplots_adjust(left=0.09, right=0.98, top=0.91, bottom=0.18)
    ax.fill_between(
        times,
        recent["sarima_garch_lower"].to_numpy(),
        recent["sarima_garch_upper"].to_numpy(),
        color=f"#{BLUE}",
        alpha=0.15,
        label="SARIMA–GARCH 80% interval",
    )
    ax.fill_between(
        times,
        recent["qgb_lower"].to_numpy(),
        recent["qgb_upper"].to_numpy(),
        color=f"#{ORANGE}",
        alpha=0.14,
        label="Quantile 10th–90th interval",
    )
    ax.plot(times, recent["actual"], color=f"#{INK}", linewidth=1.6, label="Actual")
    ax.plot(times, recent["sarima_garch_forecast"], color=f"#{BLUE}", linewidth=1.35, label="SARIMA–GARCH")
    ax.plot(times, recent["qgb_forecast"], color=f"#{ORANGE}", linewidth=1.35, label="Quantile median")
    ax.set_title("Last seven held-out days", loc="left", fontsize=12, fontweight="bold")
    ax.set_ylabel("EUR/MWh")
    ax.set_xlabel("Delivery time (UTC)")
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.grid(alpha=0.4)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.18), frameon=False, fontsize=8)
    fig.savefig(paths["forecast"], dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    model_names = ["SARIMA–GARCH", "Quantile boosting"]
    colors = [f"#{BLUE}", f"#{ORANGE}"]
    values = [
        [metrics["sarima_garch"]["mae"], metrics["quantile_boosting"]["mae"]],
        [metrics["sarima_garch"]["rmse"], metrics["quantile_boosting"]["rmse"]],
    ]
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.35))
    fig.subplots_adjust(left=0.23, right=0.97, top=0.82, bottom=0.21, wspace=0.65)
    for ax, title, data in zip(axes, ["MAE (lower is better)", "RMSE (lower is better)"], values):
        bars = ax.barh(model_names[::-1], data[::-1], color=colors[::-1], height=0.5)
        ax.set_title(title, fontsize=11, fontweight="bold", loc="left")
        ax.set_xlabel("EUR/MWh")
        ax.set_xlim(0, max(data) * 1.25)
        ax.grid(axis="x", alpha=0.4)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0, pad=5)
        ax.spines[["top", "right", "left"]].set_visible(False)
        for bar, value in zip(bars, data[::-1]):
            ax.text(value + max(data) * 0.02, bar.get_y() + bar.get_height() / 2, f"{value:.2f}", va="center", color=f"#{INK}", fontsize=9)
    fig.savefig(paths["metrics"], dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)
    return paths


def build() -> Path:
    for path in (PREDICTIONS, PRICES, METRICS):
        if not path.is_file():
            raise FileNotFoundError(f"Required project result is missing: {path}")
    predictions = pd.read_csv(PREDICTIONS, parse_dates=["timestamp_utc"])
    prices = pd.read_csv(PRICES, parse_dates=["timestamp_utc"])
    metadata = json.loads(METRICS.read_text(encoding="utf-8"))
    metrics = metadata["metrics"]
    sarima = metrics["sarima_garch"]
    quantile = metrics["quantile_boosting"]
    figures = save_figures(predictions, prices, metrics)

    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    prs.core_properties.title = "Day-Ahead Electricity Price Forecasting"
    prs.core_properties.subject = "SARIMA-GARCH volatility and quantile prediction intervals"
    prs.core_properties.author = "Time Series Analysis Lab AAT"
    prs.core_properties.keywords = "electricity price, SARIMA, GARCH, quantile gradient boosting, forecasting"

    # 1. Cover
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(BG)
    add_text(slide, "TIME SERIES ANALYSIS  /  LAB AAT", 0.82, 0.56, 5.5, 0.25, size=10, color=TEAL, bold=True)
    add_text(slide, "Day-ahead electricity\nprice forecasting", 0.82, 1.22, 6.15, 1.5, size=35, color=INK, bold=True)
    add_text(
        slide,
        "Volatility and prediction intervals using SARIMA–GARCH and quantile gradient boosting",
        0.85,
        3.03,
        5.9,
        0.8,
        size=18,
        color=MUTED,
    )
    add_rule(slide, 0.85, 4.17, 5.72, TEAL, 0.025)
    add_text(slide, "Germany–Luxembourg (DE-LU)  ·  Hourly prices in UTC", 0.85, 4.42, 5.75, 0.33, size=13, color=INK, bold=True)
    add_text(
        slide,
        f"{metadata['test_days']}-day chronological holdout  |  {metadata['test_observations']:,} hourly forecasts",
        0.85,
        4.91,
        5.8,
        0.36,
        size=12,
        color=MUTED,
    )
    add_picture(slide, figures["forecast"], 6.95, 1.25, 5.65, 3.75)
    add_text(slide, "PRESENTED BY  [STUDENT NAME]  ·  USN  [USN]", 0.85, 6.48, 5.8, 0.23, size=9, color=MUTED, bold=True)
    add_text(slide, "B. M. S. College of Engineering  |  Department of Machine Learning", 0.85, 6.82, 7.8, 0.2, size=9, color=MUTED)
    add_footer(slide, 1, "DAY-AHEAD FORECASTING  •  PROJECT PRESENTATION")

    # 2. Problem and objective
    slide = new_slide(prs, "A day-ahead forecast must describe both price and uncertainty", "Problem and objective")
    add_text(
        slide,
        "The question",
        0.85,
        1.78,
        4.9,
        0.28,
        size=12,
        color=TEAL,
        bold=True,
    )
    add_text(
        slide,
        "Before delivery begins, what might each hour cost tomorrow?",
        0.85,
        2.2,
        4.85,
        1.45,
        size=26,
        color=INK,
        bold=True,
    )
    add_rule(slide, 6.05, 1.87, 0.015, GRID, 4.2)
    add_numbered_point(slide, 6.48, 1.92, "01", "Estimate", "Produce 24 hourly point forecasts for one selected test day.", 5.15, BLUE)
    add_numbered_point(slide, 6.48, 3.18, "02", "Quantify", "Show an 80% prediction interval, not just a single price.", 5.15, ORANGE)
    add_numbered_point(slide, 6.48, 4.44, "03", "Evaluate", "Compare forecasts with held-out prices after the day is complete.", 5.15, TEAL)
    add_text(
        slide,
        "Application context: procurement, flexible demand and storage planning. The dashboard is an evaluation tool, not a trading system.",
        0.86,
        5.75,
        11.2,
        0.56,
        size=13,
        color=MUTED,
    )
    add_footer(slide, 2)

    # 3. Dataset and EDA
    slide = new_slide(prs, "The study uses hourly DE-LU prices from a public market source", "Data")
    add_picture(slide, figures["eda"], 0.76, 1.72, 7.55, 4.75)
    add_fact(slide, 8.75, 1.88, "Observations", f"{len(prices):,}", "Hourly prices; timestamps stored in UTC.", 3.6)
    data_start = pd.to_datetime(prices["timestamp_utc"], utc=True).min()
    data_end = pd.to_datetime(prices["timestamp_utc"], utc=True).max()
    add_fact(slide, 8.75, 3.44, "Coverage", f"{data_start:%b %Y} – {data_end:%b %Y}", "The full series spans the training and test periods.", 3.8)
    add_text(
        slide,
        "15-minute API observations are averaged to the hour. Negative prices are retained. Data: Energy-Charts price API; attribution to Bundesnetzagentur / SMARD, CC BY 4.0.",
        8.75,
        5.22,
        3.85,
        1.05,
        size=11,
        color=MUTED,
    )
    add_footer(slide, 3, "SOURCE: ENERGY-CHARTS PRICE API  •  DE-LU BIDDING ZONE")

    # 4. Literature and gap
    slide = new_slide(prs, "Prior work motivates the model choices and the comparison", "Literature and research gap")
    add_text(slide, "PRICE DEPENDENCE", 0.85, 1.82, 3.2, 0.25, size=10, color=BLUE, bold=True)
    add_text(slide, "Autoregressive models capture useful intraday price structure. [1, 2]", 0.85, 2.2, 3.25, 0.88, size=14, color=INK)
    add_rule(slide, 4.35, 1.82, 0.015, GRID, 2.7)
    add_text(slide, "CHANGING VARIANCE", 4.75, 1.82, 3.2, 0.25, size=10, color=ORANGE, bold=True)
    add_text(slide, "Volatility and probabilistic forecasts matter alongside point error. [1, 3, 4]", 4.75, 2.2, 3.35, 0.88, size=14, color=INK)
    add_rule(slide, 8.37, 1.82, 0.015, GRID, 2.7)
    add_text(slide, "REPRODUCIBLE EVALUATION", 8.78, 1.82, 3.2, 0.25, size=10, color=TEAL, bold=True)
    add_text(slide, "Benchmarking requires common test dates and consistent measures. [5]", 8.78, 2.2, 3.4, 0.88, size=14, color=INK)
    add_rule(slide, 0.85, 3.48, 11.7, TEAL, 0.025)
    add_text(slide, "Research question", 0.85, 3.82, 2.2, 0.25, size=11, color=TEAL, bold=True)
    add_text(
        slide,
        "On the same long chronological DE-LU holdout, how do a seasonal SARIMA–GARCH interval and a direct quantile interval compare?",
        0.85,
        4.25,
        10.8,
        0.92,
        size=21,
        color=INK,
        bold=True,
    )
    add_text(
        slide,
        "This is a focused classroom comparison, not a claim that the model combination is new or universally superior.",
        0.85,
        5.68,
        10.8,
        0.4,
        size=12,
        color=MUTED,
    )
    add_footer(slide, 4, "RELATED WORK: GARCIA ET AL. (2005); ZIEL (2016); NOWOTARSKI & WERON (2018); UNIEJEWSKI ET AL. (2018); LAGO ET AL. (2021)")

    # 5. Test design
    slide = new_slide(prs, "Both models are tested on the same future-only dates", "Evaluation design")
    add_text(slide, "Chronological split  ·  no random shuffle", 0.87, 1.77, 5.0, 0.3, size=14, color=MUTED)
    add_rect(slide, 1.05, 2.52, 3.15, 0.24, BLUE)
    add_rect(slide, 4.2, 2.52, 8.0, 0.24, TEAL)
    add_rect(slide, 1.05, 2.41, 0.08, 0.46, BLUE, shape_type=MSO_SHAPE.OVAL)
    add_rect(slide, 4.12, 2.41, 0.22, 0.46, ORANGE, shape_type=MSO_SHAPE.OVAL)
    add_rect(slide, 12.1, 2.41, 0.22, 0.46, TEAL, shape_type=MSO_SHAPE.OVAL)
    add_text(slide, "INITIAL TRAINING", 1.05, 3.12, 2.6, 0.2, size=9, color=BLUE, bold=True)
    add_text(slide, "180 days  ·  4,320 hourly observations", 1.05, 3.43, 3.0, 0.58, size=13, color=INK, bold=True)
    add_text(slide, "01 Oct 2024 – 29 Mar 2025", 1.05, 4.13, 3.0, 0.3, size=11, color=MUTED)
    add_text(slide, "ROLLING HOLDOUT", 4.55, 3.12, 3.0, 0.2, size=9, color=TEAL, bold=True)
    add_text(slide, "520 days  ·  12,480 hourly forecasts", 4.55, 3.43, 4.2, 0.58, size=17, color=INK, bold=True)
    add_text(slide, "30 Mar 2025 – 31 Aug 2026  ·  24 hours per forecast origin", 4.55, 4.13, 6.1, 0.3, size=11, color=MUTED)
    add_rule(slide, 0.92, 4.88, 11.25, GRID, 0.012)
    add_numbered_point(slide, 0.95, 5.22, "01", "Forecast first", "Use information available before each delivery day.", 3.55, BLUE)
    add_numbered_point(slide, 4.78, 5.22, "02", "Update second", "Add that day's actuals only after forecasting.", 3.55, ORANGE)
    add_numbered_point(slide, 8.55, 5.22, "03", "Score together", "Evaluate both models on the same 520 days.", 3.6, TEAL)
    add_footer(slide, 5)

    # 6. SARIMA–GARCH
    slide = new_slide(prs, "SARIMA models the daily pattern; GARCH tracks residual volatility", "Model 1 · baseline")
    add_text(slide, "SEASONAL MEAN", 0.88, 1.88, 4.5, 0.25, size=10, color=BLUE, bold=True)
    add_text(slide, "SARIMA(1,0,1) × (1,0,1,24)", 0.88, 2.32, 5.35, 0.46, size=21, color=INK, bold=True)
    add_text(
        slide,
        "An autoregressive and moving-average baseline with a 24-hour seasonal cycle, fit on the most recent 180 training days.",
        0.88,
        3.02,
        5.1,
        0.86,
        size=13,
        color=MUTED,
    )
    add_rule(slide, 6.47, 1.88, 0.015, GRID, 4.1)
    add_text(slide, "CONDITIONAL VARIANCE", 6.92, 1.88, 4.7, 0.25, size=10, color=ORANGE, bold=True)
    add_text(slide, "σ²ₜ = ω + αε²ₜ₋₁ + βσ²ₜ₋₁", 6.92, 2.32, 5.0, 0.46, size=23, color=INK, bold=True)
    add_text(
        slide,
        "GARCH(1,1) updates uncertainty from recent residuals. The nominal 80% interval uses forecast mean ± 1.645 standard deviations.",
        6.92,
        3.02,
        5.0,
        0.92,
        size=13,
        color=MUTED,
    )
    add_rule(slide, 0.88, 4.55, 11.4, TEAL, 0.025)
    add_text(
        slide,
        "Assumption to check",
        0.88,
        4.9,
        2.3,
        0.25,
        size=11,
        color=TEAL,
        bold=True,
    )
    add_text(
        slide,
        "Standardized innovations are treated as approximately normal for interval construction. Held-out coverage tests how well this assumption works.",
        0.88,
        5.33,
        10.8,
        0.72,
        size=15,
        color=INK,
    )
    add_footer(slide, 6, "SARIMAX ORDER: (1,0,1) × (1,0,1,24)  •  GARCH(1,1)")

    # 7. Quantile boosting
    slide = new_slide(prs, "Quantile boosting estimates the centre and both sides directly", "Model 2 · proposed comparison")
    quantile_centres = [(1.2, "0.10", "LOWER QUANTILE", BLUE), (5.0, "0.50", "MEDIAN FORECAST", TEAL), (8.8, "0.90", "UPPER QUANTILE", ORANGE)]
    for x, value, label, color in quantile_centres:
        add_text(slide, f"τ = {value}", x, 1.92, 3.0, 0.45, size=22, color=color, bold=True, align=PP_ALIGN.CENTER)
        add_rule(slide, x + 0.4, 2.55, 2.2, color, 0.04)
        add_text(slide, label, x, 2.76, 3.0, 0.24, size=9, color=MUTED, bold=True, align=PP_ALIGN.CENTER)
    add_text(slide, "10th–90th percentiles form the nominal 80% prediction interval.", 1.1, 3.35, 10.9, 0.38, size=15, color=INK, bold=True, align=PP_ALIGN.CENTER)
    add_rule(slide, 0.9, 4.05, 11.3, GRID, 0.012)
    add_text(slide, "INPUT FEATURES", 0.9, 4.38, 2.5, 0.25, size=10, color=TEAL, bold=True)
    add_text(slide, "Past prices at 24, 48 and 168 hours; recent 24- and 168-hour summaries; hour, weekday and month.", 0.9, 4.78, 5.2, 0.85, size=13, color=INK)
    add_rule(slide, 6.45, 4.34, 0.015, GRID, 1.5)
    add_text(slide, "WHY QUANTILES?", 6.9, 4.38, 2.5, 0.25, size=10, color=ORANGE, bold=True)
    add_text(slide, "Quantile loss allows an asymmetric interval without assuming normal forecast errors. Models use 150 shallow boosting trees.", 6.9, 4.78, 5.0, 0.85, size=13, color=INK)
    add_footer(slide, 7, "GRADIENT BOOSTING  •  QUANTILE LOSS AT τ = 0.10, 0.50 AND 0.90")

    # 8. Metrics
    slide = new_slide(prs, "Accuracy and interval quality answer different questions", "Evaluation measures")
    add_fact(slide, 0.92, 1.95, "Point error", "MAE", "Typical absolute miss; reported in EUR/MWh.", 2.7)
    add_fact(slide, 3.93, 1.95, "Large errors", "RMSE", "Penalizes larger misses more strongly.", 2.7)
    add_fact(slide, 6.94, 1.95, "Calibration", "Coverage", "Share inside a nominal 80% interval.", 2.7)
    add_fact(slide, 9.95, 1.95, "Sharpness", "Width", "Average interval size; smaller is not useful alone.", 2.7)
    add_rule(slide, 0.92, 3.65, 11.3, GRID, 0.012)
    add_text(slide, "Additional checks", 0.92, 4.0, 2.1, 0.25, size=11, color=TEAL, bold=True)
    add_text(
        slide,
        "sMAPE is reported instead of MAPE because prices may be zero or negative. Pinball loss scores the lower and upper quantile forecasts.",
        0.92,
        4.42,
        10.8,
        0.76,
        size=15,
        color=INK,
    )
    add_text(
        slide,
        "Coverage is interpreted against 80%; it does not measure interval width or point accuracy.",
        0.92,
        5.67,
        10.8,
        0.36,
        size=12,
        color=MUTED,
    )
    add_footer(slide, 8)

    # 9. Metrics table
    slide = new_slide(prs, "On this holdout, SARIMA–GARCH has lower point error", "Results · full held-out test")
    rows = [
        ["MODEL", "MAE", "RMSE", "sMAPE", "80% COVERAGE", "MEAN WIDTH", "PINBALL 10", "PINBALL 90"],
        [
            "SARIMA–GARCH",
            f"{sarima['mae']:.2f}",
            f"{sarima['rmse']:.2f}",
            f"{sarima['smape_percent']:.1f}%",
            f"{sarima['coverage_80']:.1%}",
            f"{sarima['mean_interval_width']:.2f}",
            f"{sarima['pinball_10']:.2f}",
            f"{sarima['pinball_90']:.2f}",
        ],
        [
            "Quantile boosting",
            f"{quantile['mae']:.2f}",
            f"{quantile['rmse']:.2f}",
            f"{quantile['smape_percent']:.1f}%",
            f"{quantile['coverage_80']:.1%}",
            f"{quantile['mean_interval_width']:.2f}",
            f"{quantile['pinball_10']:.2f}",
            f"{quantile['pinball_90']:.2f}",
        ],
    ]
    add_table(slide, rows, 0.75, 1.86, 11.85, 1.75, [2.28, 1.25, 1.25, 1.22, 1.55, 1.48, 1.36, 1.36])
    add_picture(slide, figures["metrics"], 0.9, 4.02, 6.1, 2.35)
    add_text(slide, "SARIMA–GARCH: lower MAE and RMSE.", 7.45, 4.24, 4.7, 0.45, size=16, color=BLUE, bold=True)
    add_text(slide, "Quantile boosting: coverage nearer 80% and slightly narrower intervals.", 7.45, 5.0, 4.7, 0.76, size=16, color=ORANGE, bold=True)
    add_text(slide, "The preferred model depends on whether point error or interval behaviour matters more.", 7.45, 6.0, 4.7, 0.48, size=11, color=MUTED)
    add_footer(slide, 9, "PRICE ERRORS / WIDTH / LOSS: EUR/MWh  •  sMAPE / COVERAGE: %  •  SAME 520-DAY HOLDOUT")

    # 10. Forecast chart
    slide = new_slide(prs, "The final test week shows where point forecasts and intervals differ", "Forecast example")
    add_picture(slide, figures["forecast"], 0.82, 1.75, 11.65, 4.45)
    add_text(
        slide,
        "Actual prices are shown only for retrospective evaluation. Shaded regions are nominal 80% intervals; sharp price moves remain difficult for both models.",
        0.88,
        6.35,
        11.3,
        0.4,
        size=12,
        color=MUTED,
    )
    add_footer(slide, 10, "HELD-OUT PERIOD  •  UTC DELIVERY HOURS")

    # 11. Forecast explorer
    slide = new_slide(prs, "The forecast explorer turns a test date into 24 hourly outputs", "Interactive dashboard · input and output")
    dashboard = ASSETS / "forecast_chart_cropped.png"
    add_picture(slide, dashboard, 0.78, 1.7, 7.1, 4.9)
    add_numbered_point(slide, 8.3, 1.92, "01", "Choose a test date", "The selector covers the 520 stored holdout dates, not arbitrary future dates.", 4.0, BLUE)
    add_numbered_point(slide, 8.3, 3.22, "02", "Inspect next-day estimates", "View 24 hourly forecasts, optional 80% bounds and the selected-day table.", 4.0, TEAL)
    add_numbered_point(slide, 8.3, 4.52, "03", "Compare with actuals", "Held-out prices appear for evaluation only; they are not forecast inputs.", 4.0, ORANGE)
    add_text(slide, "You can also show either model, hide actuals or intervals, choose line/step style, and use a linear or symmetric-log price axis.", 8.92, 5.9, 3.25, 0.66, size=11, color=MUTED)
    add_footer(slide, 11, "LIVE DEMO: python -m streamlit run app.py")

    # 12. Currency and history explorer
    slide = new_slide(prs, "Currency and chart controls change the display, not the forecast", "Interactive dashboard · display and exploration")
    scorecard = ASSETS / "model_comparison_cropped.png"
    add_picture(slide, scorecard, 0.78, 1.7, 6.5, 4.9)
    add_text(slide, "CURRENCY AND UNITS", 7.7, 1.82, 4.5, 0.22, size=10, color=TEAL, bold=True)
    add_text(
        slide,
        "Choose listed currencies or enter a three-letter code. INR/kWh is the default when live rates are available; EUR/MWh remains the source unit.",
        7.7,
        2.2,
        4.5,
        0.8,
        size=12,
        color=INK,
    )
    add_text(
        slide,
        "Rates are published ECB reference rates via Frankfurter. A positive manual rate is available; if rates are offline, EUR remains usable.",
        7.7,
        3.15,
        4.5,
        0.78,
        size=12,
        color=MUTED,
    )
    add_rule(slide, 7.7, 4.13, 4.45)
    add_text(slide, "HISTORY AND DOWNLOADS", 7.7, 4.38, 4.5, 0.22, size=10, color=ORANGE, bold=True)
    add_text(
        slide,
        "Explore hourly, daily or weekly prices, rolling averages, typical UTC-hour prices and price distributions. Download the visible history or selected-day forecasts as CSV.",
        7.7,
        4.78,
        4.5,
        0.9,
        size=12,
        color=INK,
    )
    add_text(
        slide,
        "INR is a display conversion of DE-LU prices—not an Indian electricity-market quote. Model inputs and stored results remain unchanged.",
        7.7,
        5.87,
        4.5,
        0.55,
        size=10,
        color=MUTED,
    )
    add_footer(slide, 12, "PRICE-VALUED DISPLAYS CAN BE CONVERTED  •  PERCENTAGES ARE UNCHANGED")

    # 13. Selected day output
    slide = new_slide(prs, "A selected day can be checked row by row", "Interactive dashboard · output detail")
    selected_day = ASSETS / "selected_day_table_cropped.png"
    add_picture(slide, selected_day, 0.78, 1.86, 7.6, 4.9)
    add_text(slide, "24 HOURLY ROWS", 8.85, 1.95, 3.4, 0.23, size=10, color=TEAL, bold=True)
    add_text(
        slide,
        "Each row reports one UTC delivery hour. The selected display currency and unit appear in price-valued columns.",
        8.85,
        2.34,
        3.35,
        0.78,
        size=13,
        color=INK,
    )
    add_rule(slide, 8.85, 3.38, 3.35)
    add_text(slide, "EVALUATION ONLY", 8.85, 3.66, 3.4, 0.23, size=10, color=ORANGE, bold=True)
    add_text(
        slide,
        "Actual prices are included to measure the forecast after delivery. They are never used to build that same day's input features.",
        8.85,
        4.05,
        3.35,
        0.84,
        size=13,
        color=INK,
    )
    add_text(
        slide,
        "The daily CSV is downloadable in the selected display unit.",
        8.85,
        5.35,
        3.35,
        0.5,
        size=11,
        color=MUTED,
    )
    add_footer(slide, 13, "EXAMPLE OUTPUT: 31 AUG 2026 UTC  •  INR/KWH DISPLAY")

    # 14. Interpretation and limits
    slide = new_slide(prs, "The result is useful within a clearly defined scope", "Conclusion and limitations")
    add_text(slide, "WHAT THE TEST SHOWS", 0.9, 1.88, 4.6, 0.24, size=10, color=TEAL, bold=True)
    add_numbered_point(slide, 0.9, 2.3, "01", "Point accuracy", "SARIMA–GARCH has lower MAE and RMSE in this holdout.", 5.35, BLUE)
    add_numbered_point(slide, 0.9, 3.5, "02", "Interval behaviour", "Quantile boosting is closer to 80% coverage and slightly narrower.", 5.35, ORANGE)
    add_text(slide, "LIMITS TO KEEP IN VIEW", 6.75, 1.88, 4.6, 0.24, size=10, color=ORANGE, bold=True)
    add_text(
        slide,
        "One bidding zone and one historical period; no weather, demand or generation inputs; UTC days do not resolve local daylight-saving delivery days.",
        6.75,
        2.3,
        5.1,
        0.95,
        size=14,
        color=INK,
    )
    add_rule(slide, 6.75, 3.55, 5.1)
    add_text(
        slide,
        "The dashboard's currency controls are for readability. An INR value is converted DE-LU data and should not be interpreted as an Indian market forecast.",
        6.75,
        3.88,
        5.1,
        0.92,
        size=12,
        color=MUTED,
    )
    add_text(slide, "Next: add external drivers, test more zones and seasons, calibrate intervals, and evaluate decision value.", 0.9, 5.72, 11.1, 0.6, size=14, color=INK, bold=True)
    add_footer(slide, 14)

    # 15. References
    slide = new_slide(prs, "References and data attribution", "Sources")
    references = [
        "[1] Garcia, R. C. et al. (2005). A GARCH forecasting model to predict day-ahead electricity prices. IEEE Transactions on Power Systems. doi:10.1109/TPWRS.2005.846044",
        "[2] Ziel, F. (2016). Forecasting electricity spot prices using Lasso. IEEE Transactions on Power Systems. doi:10.1109/TPWRS.2016.2521545",
        "[3] Nowotarski, J. & Weron, R. (2018). Recent advances in electricity price forecasting: probabilistic forecasting. Renewable & Sustainable Energy Reviews. doi:10.1016/j.rser.2017.05.234",
        "[4] Uniejewski, B., Weron, R. & Ziel, F. (2018). Variance stabilizing transformations for electricity spot price forecasting. IEEE Transactions on Power Systems. doi:10.1109/TPWRS.2017.2734563",
        "[5] Lago, J. et al. (2021). Forecasting day-ahead electricity prices: algorithms, best practices and open-access benchmark. Applied Energy. doi:10.1016/j.apenergy.2021.116983",
    ]
    for index, reference in enumerate(references):
        add_text(slide, reference, 0.9, 1.78 + index * 0.68, 11.35, 0.56, size=10, color=INK)
    add_rule(slide, 0.9, 5.35, 11.35)
    add_text(
        slide,
        "Data: Energy-Charts price API, DE-LU zone; attribution to Bundesnetzagentur / SMARD; CC BY 4.0. Exchange-rate service: Frankfurter, which distributes ECB reference rates.",
        0.9,
        5.62,
        11.1,
        0.66,
        size=11,
        color=MUTED,
    )
    add_text(
        slide,
        "All reported model results are computed from the original EUR/MWh backtest. Dashboard currency conversion affects presentation only.",
        0.9,
        6.48,
        11.1,
        0.28,
        size=10,
        color=TEAL,
        bold=True,
    )
    add_footer(slide, 15, "END")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build())
