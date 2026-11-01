"""Build an editable presentation for the day-ahead electricity-price project."""

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
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "Day_Ahead_Electricity_Forecasting_Presentation.pptx"
ASSETS = ROOT / "reports" / "presentation_assets"
PREDICTIONS = ROOT / "outputs" / "backtest_predictions.csv"
PRICES = ROOT / "data" / "day_ahead_prices.csv"
METRICS = ROOT / "outputs" / "metrics.json"

SW, SH = 13.333, 7.5
BG = "081421"
PANEL = "102235"
PANEL_ALT = "142B40"
WHITE = "F4F7FA"
MUTED = "A8B9C8"
TEAL = "45D6C1"
BLUE = "58A6FF"
ORANGE = "FFA45B"
RED = "F27575"
GREEN = "7FE0A0"
GRID = "294055"
FONT = "Aptos"


def rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def add_box(
    slide: Any,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    radius: bool = True,
    line: str | None = None,
) -> Any:
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x),
        Inches(y),
        Inches(w),
        Inches(h),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    shape.line.fill.background() if line is None else None
    if line:
        shape.line.color.rgb = rgb(line)
        shape.line.width = Pt(0.8)
    if radius:
        shape.adjustments[0] = 0.12
    return shape


def add_text(
    slide: Any,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 16,
    color: str = WHITE,
    bold: bool = False,
    font: str = FONT,
    align: Any = PP_ALIGN.LEFT,
    valign: Any = MSO_ANCHOR.TOP,
    margin: float = 0,
    fit: bool = False,
) -> Any:
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(margin)
    frame.margin_right = Inches(margin)
    frame.margin_top = Inches(margin)
    frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    if fit:
        frame.fit_text(font_family=font, max_size=Pt(size), bold=bold)
    return box


def add_rich_lines(
    slide: Any,
    lines: list[tuple[str, str, bool]],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    size: float = 16,
    spacing: float = 9,
) -> Any:
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = Inches(0)
    frame.margin_top = frame.margin_bottom = Inches(0)
    for index, (text, color, bold) in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        paragraph.space_after = Pt(spacing)
        paragraph.level = 0
        run = paragraph.add_run()
        run.text = text
        run.font.name = FONT
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = rgb(color)
    return box


def new_slide(prs: Presentation, title: str, kicker: str | None = None) -> Any:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(BG)
    add_box(slide, 0.48, 0.43, 0.08, 0.36, TEAL, radius=False)
    if kicker:
        add_text(slide, kicker.upper(), 0.72, 0.42, 4.2, 0.22, size=9, color=TEAL, bold=True)
    add_text(slide, title, 0.72, 0.72, 11.9, 0.56, size=26, bold=True)
    return slide


def add_footer(slide: Any, index: int, source: str = "DAY-AHEAD FORECASTING  •  TSA LAB AAT") -> None:
    add_box(slide, 0.62, 7.12, 12.08, 0.012, GRID, radius=False)
    add_text(slide, source, 0.68, 7.18, 10.7, 0.17, size=8, color=MUTED)
    add_text(slide, f"{index:02d}", 12.12, 7.16, 0.48, 0.2, size=9, color=TEAL, bold=True, align=PP_ALIGN.RIGHT)


def add_card(
    slide: Any,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    body: str,
    accent: str = TEAL,
    *,
    title_size: int = 16,
    body_size: int = 12,
) -> None:
    add_box(slide, x, y, w, h, PANEL)
    add_box(slide, x + 0.2, y + 0.23, 0.055, h - 0.46, accent, radius=False)
    add_text(slide, title, x + 0.4, y + 0.2, w - 0.62, 0.36, size=title_size, color=WHITE, bold=True)
    add_text(slide, body, x + 0.4, y + 0.68, w - 0.65, h - 0.85, size=body_size, color=MUTED)


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


def add_pill(slide: Any, text: str, x: float, y: float, w: float, color: str) -> None:
    add_box(slide, x, y, w, 0.34, PANEL_ALT)
    add_text(slide, text, x + 0.08, y + 0.035, w - 0.16, 0.24, size=9, color=color, bold=True, align=PP_ALIGN.CENTER)


def add_arrow(slide: Any, x1: float, y1: float, x2: float, y2: float, color: str = TEAL) -> None:
    shape = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(x1),
        Inches(y1),
        Inches(x2),
        Inches(y2),
    )
    shape.line.color.rgb = rgb(color)
    shape.line.width = Pt(2)
    shape.line.end_arrowhead = True


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
            "text.color": f"#{WHITE}",
            "grid.color": f"#{GRID}",
            "font.family": "DejaVu Sans",
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
    hourly = frame.assign(hour=frame["timestamp_utc"].dt.hour).groupby("hour")["price_eur_mwh"].median()
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 5.3), sharex=False, gridspec_kw={"height_ratios": [1.35, 1]})
    fig.subplots_adjust(hspace=0.46, left=0.09, right=0.98, top=0.91, bottom=0.1)
    axes[0].plot(daily.index, daily, color=f"#{BLUE}", linewidth=1.6)
    axes[0].fill_between(daily.index, daily.to_numpy(), color=f"#{BLUE}", alpha=0.12)
    axes[0].set_title("Daily average price  |  Oct 2024 – Aug 2026", loc="left", fontsize=12, fontweight="bold")
    axes[0].set_ylabel("EUR/MWh")
    axes[0].xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    axes[0].xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    axes[0].grid(alpha=0.45)
    axes[1].plot(hourly.index, hourly.values, color=f"#{ORANGE}", marker="o", markersize=4, linewidth=2)
    axes[1].set_title("Intraday shape  |  median by UTC hour", loc="left", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Hour of day (UTC)")
    axes[1].set_ylabel("EUR/MWh")
    axes[1].set_xticks(range(0, 24, 2))
    axes[1].grid(alpha=0.45)
    fig.savefig(paths["eda"], dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    recent = predictions.tail(7 * 24)
    times = pd.to_datetime(recent["timestamp_utc"], utc=True)
    fig, ax = plt.subplots(figsize=(11, 4.1))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.91, bottom=0.17)
    ax.fill_between(times, recent["sarima_garch_lower"].to_numpy(), recent["sarima_garch_upper"].to_numpy(), color=f"#{BLUE}", alpha=0.15, label="SARIMA–GARCH 80% interval")
    ax.fill_between(times, recent["qgb_lower"].to_numpy(), recent["qgb_upper"].to_numpy(), color=f"#{ORANGE}", alpha=0.14, label="Quantile 10th–90th interval")
    ax.plot(times, recent["actual"], color=f"#{WHITE}", linewidth=1.8, label="Actual")
    ax.plot(times, recent["sarima_garch_forecast"], color=f"#{BLUE}", linewidth=1.4, label="SARIMA–GARCH")
    ax.plot(times, recent["qgb_forecast"], color=f"#{ORANGE}", linewidth=1.4, label="Quantile median")
    ax.set_title("Last seven held-out days  |  actual, forecasts and uncertainty", loc="left", fontsize=12, fontweight="bold")
    ax.set_ylabel("EUR/MWh")
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.grid(alpha=0.4)
    ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.15), frameon=False, fontsize=8)
    fig.savefig(paths["forecast"], dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)

    model_names = ["SARIMA–GARCH", "Quantile GB"]
    colors = [f"#{BLUE}", f"#{ORANGE}"]
    values = [
        [
            metrics["sarima_garch"]["mae"],
            metrics["quantile_boosting"]["mae"],
        ],
        [
            metrics["sarima_garch"]["rmse"],
            metrics["quantile_boosting"]["rmse"],
        ],
    ]
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.8))
    fig.subplots_adjust(left=0.2, right=0.9, top=0.83, bottom=0.2, wspace=0.55)
    for ax, title, data in zip(axes, ["MAE  |  lower is better", "RMSE  |  lower is better"], values):
        bars = ax.barh(model_names[::-1], data[::-1], color=colors[::-1], height=0.48)
        ax.set_title(title, fontsize=12, fontweight="bold", loc="left")
        ax.set_xlabel("EUR/MWh")
        ax.set_xlim(0, max(data) * 1.24)
        ax.grid(axis="x", alpha=0.4)
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0, pad=6)
        for bar, value in zip(bars, data[::-1]):
            ax.text(value + max(data) * 0.02, bar.get_y() + bar.get_height() / 2, f"{value:.2f}", va="center", color=f"#{WHITE}", fontsize=10, fontweight="bold")
        ax.spines[["top", "right", "left"]].set_visible(False)
    fig.savefig(paths["metrics"], dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)
    return paths


def add_table(slide: Any, rows: list[list[str]], x: float, y: float, w: float, h: float, widths: list[float] | None = None) -> None:
    table_shape = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(h))
    table = table_shape.table
    if widths:
        for column, width in zip(table.columns, widths):
            column.width = Inches(width)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = rgb(PANEL_ALT if r == 0 else (PANEL if r % 2 else "0D1D2D"))
            cell.margin_left = Inches(0.12)
            cell.margin_right = Inches(0.1)
            cell.margin_top = Inches(0.07)
            cell.margin_bottom = Inches(0.05)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            frame = cell.text_frame
            frame.clear()
            frame.word_wrap = True
            paragraph = frame.paragraphs[0]
            paragraph.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
            run = paragraph.add_run()
            run.text = value
            run.font.name = FONT
            run.font.size = Pt(11 if r else 10)
            run.font.bold = r == 0 or c == 0
            run.font.color.rgb = rgb(TEAL if r == 0 else WHITE)


def build() -> Path:
    for path in (PREDICTIONS, PRICES, METRICS):
        if not path.is_file():
            raise FileNotFoundError(f"Required project result is missing: {path}")
    predictions = pd.read_csv(PREDICTIONS, parse_dates=["timestamp_utc"])
    prices = pd.read_csv(PRICES, parse_dates=["timestamp_utc"])
    metadata = json.loads(METRICS.read_text(encoding="utf-8"))
    test_metrics = metadata["metrics"]
    sarima_metrics = test_metrics["sarima_garch"]
    quantile_metrics = test_metrics["quantile_boosting"]
    figures = save_figures(predictions, prices, test_metrics)

    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)
    prs.core_properties.title = "Day-Ahead Electricity Price Forecasting"
    prs.core_properties.subject = "SARIMA-GARCH volatility and quantile prediction intervals"
    prs.core_properties.author = "Time Series Analysis Lab AAT"
    prs.core_properties.keywords = "electricity price, SARIMA, GARCH, quantile gradient boosting, forecasting"

    # 1 — Cover
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(BG)
    add_box(slide, 9.18, 0, 4.15, 7.5, PANEL, radius=False)
    add_text(slide, "TIME SERIES ANALYSIS  /  LAB AAT", 0.78, 0.62, 5.5, 0.3, size=10, color=TEAL, bold=True)
    add_text(slide, "DAY-AHEAD\nELECTRICITY PRICE\nFORECASTING", 0.78, 1.24, 7.9, 2.08, size=32, bold=True)
    add_text(slide, "Volatility & prediction intervals with\nSARIMA–GARCH and quantile gradient boosting", 0.82, 3.58, 7.8, 0.92, size=18, color=MUTED)
    add_pill(slide, "REAL DE-LU MARKET DATA", 0.82, 5.0, 2.25, TEAL)
    add_pill(slide, f"{metadata['test_days']}-DAY CHRONOLOGICAL TEST", 3.2, 5.0, 2.85, BLUE)
    add_text(slide, "Presented by  [Student name]   •   USN  [USN]", 0.82, 6.36, 7.6, 0.28, size=11, color=MUTED)
    add_picture(slide, figures["forecast"], 9.43, 2.02, 3.65, 2.38)
    add_text(slide, "POINT FORECAST + UNCERTAINTY", 9.47, 1.5, 3.3, 0.3, size=10, color=TEAL, bold=True)
    add_text(slide, "A decision-support study — not a trading guarantee.", 9.47, 4.62, 3.36, 0.68, size=12, color=MUTED)
    add_text(slide, "B. M. S. College of Engineering  |  Department of Machine Learning", 0.82, 6.82, 7.8, 0.22, size=9, color=MUTED)

    # 2 — Executive takeaway
    slide = new_slide(prs, "One experiment. Two useful trade-offs.", "Executive takeaway")
    add_text(slide, "A fair comparison on the same future-only test period.", 0.74, 1.47, 9, 0.4, size=17, color=MUTED)
    add_card(slide, 0.74, 2.05, 3.83, 2.02, "BEST POINT ACCURACY", f"SARIMA–GARCH MAE\n€{sarima_metrics['mae']:.2f}/MWh", BLUE, body_size=17)
    add_card(slide, 4.74, 2.05, 3.83, 2.02, "CLOSEST TO 80% COVERAGE", f"Quantile boosting\n{quantile_metrics['coverage_80']:.1%} observed coverage", ORANGE, body_size=17)
    add_card(slide, 8.74, 2.05, 3.83, 2.02, "LONG OUT-OF-SAMPLE TEST", f"{metadata['test_days']} days  •  {metadata['test_observations']:,} hourly forecasts", TEAL, body_size=16)
    add_box(slide, 0.74, 4.42, 11.83, 1.35, PANEL_ALT)
    add_text(slide, "Bottom line", 1.02, 4.69, 1.5, 0.29, size=13, color=TEAL, bold=True)
    add_text(slide, "SARIMA–GARCH wins on point error; quantile boosting is slightly better calibrated and narrower.", 2.45, 4.61, 9.55, 0.58, size=18, bold=True)
    add_text(slide, "Evidence is limited to this zone, data window, feature set, and evaluation design.", 1.02, 6.05, 10.4, 0.31, size=12, color=MUTED)
    add_footer(slide, 2)

    # 3 — Why this problem
    slide = new_slide(prs, "Electricity prices are not an ordinary time series", "Problem & motivation")
    add_text(slide, "The operational question", 0.75, 1.48, 5.4, 0.32, size=17, color=TEAL, bold=True)
    add_text(slide, "What might each hour cost tomorrow — and how uncertain is that estimate?", 0.75, 1.94, 5.6, 1.18, size=24, bold=True)
    add_card(slide, 6.66, 1.5, 5.9, 1.25, "REPEATING DAILY SHAPE", "Hourly cycles vary by time of day and day of week.", BLUE)
    add_card(slide, 6.66, 2.96, 5.9, 1.25, "VOLATILITY CLUSTERS", "Calm periods can be followed by sharp, irregular changes.", ORANGE)
    add_card(slide, 6.66, 4.42, 5.9, 1.25, "SPIKES & NEGATIVE PRICES", "Outliers and prices below zero make naive averages risky.", RED)
    add_text(slide, "A point estimate alone hides the risk of being wrong.", 0.77, 4.05, 5.3, 0.86, size=20, color=MUTED)
    add_pill(slide, "APPLICATION: PROCUREMENT  •  FLEXIBLE DEMAND  •  STORAGE PLANNING", 0.77, 5.39, 5.56, TEAL)
    add_footer(slide, 3, "SCOPE: HOURLY DE-LU DAY-AHEAD PRICES  •  UTC")

    # 4 — Dataset and EDA
    slide = new_slide(prs, "A real, volatile market signal", "Dataset & exploratory analysis")
    add_picture(slide, figures["eda"], 0.72, 1.42, 7.8, 4.55)
    add_card(slide, 8.8, 1.55, 3.72, 1.16, "MARKET", "Germany–Luxembourg (DE-LU)\nEnergy-Charts / SMARD", TEAL, body_size=11)
    add_card(slide, 8.8, 2.92, 3.72, 1.16, "OBSERVATIONS", "16,800 hourly prices\n1 Oct 2024 – 31 Aug 2026 (UTC)", BLUE, body_size=11)
    add_card(slide, 8.8, 4.29, 3.72, 1.16, "PREPARATION", "15-minute values averaged hourly; negative prices retained.", ORANGE, body_size=11)
    add_text(slide, "Source: Energy-Charts price API • Attribution: Bundesnetzagentur / SMARD • CC BY 4.0", 0.78, 6.34, 11.9, 0.26, size=10, color=MUTED)
    add_footer(slide, 4)

    # 5 — Research and gap
    slide = new_slide(prs, "What prior work tells us — and what this study tests", "Literature & research gap")
    add_card(slide, 0.76, 1.48, 3.8, 1.58, "PRICE DEPENDENCE", "Autoregressive structures capture useful intraday effects. [1, 2]", BLUE)
    add_card(slide, 4.78, 1.48, 3.8, 1.58, "VOLATILITY MATTERS", "GARCH is a recognized tool for changing price uncertainty. [3]", ORANGE)
    add_card(slide, 8.8, 1.48, 3.8, 1.58, "PROBABILISTIC VALUE", "Evaluate both calibration and interval sharpness—not error alone. [4, 5]", TEAL)
    add_box(slide, 0.76, 3.44, 11.84, 1.33, PANEL_ALT)
    add_text(slide, "CLASSROOM-SCALE GAP", 1.02, 3.68, 2.4, 0.27, size=11, color=TEAL, bold=True)
    add_text(slide, "Put a seasonal SARIMA–GARCH interval and a direct quantile interval through the same long, chronological DE-LU test.", 3.25, 3.63, 8.8, 0.63, size=17, bold=True)
    add_text(slide, "This is a focused comparison, not a claim that the model combination is new or universally superior.", 1.02, 5.17, 10.9, 0.55, size=14, color=MUTED)
    add_footer(slide, 5, "LITERATURE: GARCIA ET AL. (2005); ZIEL (2016); NOWOTARSKI & WERON (2018); UNIEJEWSKI ET AL. (2018); LAGO ET AL. (2021)")

    # 6 — Test design
    slide = new_slide(prs, "Test the future as it would arrive", "Evaluation design")
    total_days = (metadata["training_observations"] + metadata["test_observations"]) // 24
    add_text(slide, f"{total_days} complete UTC days  •  No random shuffle", 0.78, 1.45, 8.4, 0.38, size=17, color=MUTED)
    add_box(slide, 0.78, 2.26, 3.05, 1.35, PANEL_ALT)
    add_text(slide, "INITIAL TRAINING", 1.05, 2.54, 2.5, 0.27, size=12, color=BLUE, bold=True, align=PP_ALIGN.CENTER)
    add_text(slide, "180 days", 1.05, 2.91, 2.5, 0.42, size=22, bold=True, align=PP_ALIGN.CENTER)
    add_box(slide, 3.92, 2.26, 8.58, 1.35, "11354A")
    add_text(slide, f"ROLLING HOLDOUT  •  {metadata['test_days']} DAYS  •  {metadata['test_observations']:,} HOURLY FORECASTS", 4.22, 2.48, 7.9, 0.28, size=12, color=TEAL, bold=True, align=PP_ALIGN.CENTER)
    test_start = pd.Timestamp(metadata["test_start"]).strftime("%d %b %Y")
    test_end = pd.Timestamp(metadata["test_end"]).strftime("%d %b %Y")
    add_text(slide, f"{test_start}  →  {test_end}", 4.22, 2.91, 7.9, 0.42, size=21, bold=True, align=PP_ALIGN.CENTER)
    add_arrow(slide, 3.83, 2.93, 3.91, 2.93)
    add_card(slide, 0.78, 4.12, 3.78, 1.46, "ORIGIN", "At each day boundary, use information available before delivery.", BLUE)
    add_card(slide, 4.78, 4.12, 3.78, 1.46, "FORECAST", "Predict the next 24 hourly prices and interval bounds.", TEAL)
    add_card(slide, 8.78, 4.12, 3.78, 1.46, "UPDATE", "Only after forecasting, add the day's actuals to history.", ORANGE)
    add_text(slide, "Leakage control: day-ahead target values never build that same day's input features.", 0.82, 6.05, 11.6, 0.32, size=14, color=GREEN, bold=True)
    add_footer(slide, 6)

    # 7 — Baseline
    slide = new_slide(prs, "Baseline: model the mean, then its changing variance", "Model 1 · SARIMA–GARCH")
    add_card(slide, 0.78, 1.48, 5.62, 1.15, "SEASONAL MEAN", "SARIMA(1,0,1) × (1,0,1,24) models dependence and the daily cycle.", BLUE, body_size=13)
    add_card(slide, 6.82, 1.48, 5.62, 1.15, "CONDITIONAL VOLATILITY", "GARCH(1,1) updates uncertainty using recent forecast residuals.", ORANGE, body_size=13)
    add_box(slide, 0.78, 2.98, 11.66, 1.27, PANEL_ALT)
    add_text(slide, "σ²ₜ = ω + αε²ₜ₋₁ + βσ²ₜ₋₁", 1.05, 3.22, 6.0, 0.47, size=25, color=WHITE, bold=True)
    add_text(slide, "80% interval ≈ forecast mean ± 1.645 × forecast standard deviation", 6.92, 3.23, 5.0, 0.52, size=14, color=MUTED, bold=True)
    add_rich_lines(
        slide,
        [
            ("WHY THIS BASELINE?", TEAL, True),
            ("Interpretable statistical model with explicit daily seasonality.", WHITE, False),
            ("GARCH widens or narrows bounds as estimated residual volatility changes.", WHITE, False),
            ("Normal standardized innovations are an assumption; test coverage checks calibration.", MUTED, False),
        ],
        1.02, 4.69, 10.95, 1.42, size=14, spacing=8,
    )
    add_footer(slide, 7, "MODEL FIT/UPDATE: INITIAL 180-DAY WINDOW; DAILY FORECAST BEFORE STATE UPDATE")

    # 8 — Quantile boosting
    slide = new_slide(prs, "Enhancement: learn the price distribution directly", "Model 2 · Quantile gradient boosting")
    add_text(slide, "Three quantile learners", 0.82, 1.49, 4.3, 0.36, size=17, color=TEAL, bold=True)
    for x, q, label, color in [(0.92, "τ = 0.10", "LOWER BOUND", BLUE), (4.72, "τ = 0.50", "MEDIAN", TEAL), (8.52, "τ = 0.90", "UPPER BOUND", ORANGE)]:
        add_box(slide, x, 2.1, 3.25, 1.1, PANEL_ALT)
        add_text(slide, q, x + 0.15, 2.3, 2.95, 0.35, size=20, color=color, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, label, x + 0.15, 2.72, 2.95, 0.22, size=10, color=MUTED, bold=True, align=PP_ALIGN.CENTER)
    add_text(slide, "10th–90th percentile = nominal 80% prediction interval", 1.0, 3.48, 10.9, 0.32, size=15, color=WHITE, align=PP_ALIGN.CENTER)
    add_card(slide, 0.82, 4.12, 5.62, 1.53, "PAST-PRICE SIGNALS", "24h, 48h and 168h lags • trailing mean and standard deviation", BLUE, body_size=13)
    add_card(slide, 6.82, 4.12, 5.62, 1.53, "CALENDAR SIGNALS", "Hour, weekday and month cycles • 150 shallow boosting trees", ORANGE, body_size=13)
    add_text(slide, "Quantile loss allows asymmetric bounds; it does not assume errors are normally distributed.", 0.86, 6.08, 11.5, 0.3, size=13, color=MUTED)
    add_footer(slide, 8)

    # 9 — Shared test protocol
    slide = new_slide(prs, "Same dates. Same targets. Same scorecard.", "Reproducible protocol")
    steps = [
        ("01", "OBSERVE", "Public hourly DE-LU prices\nUTC, 2024–2026", BLUE),
        ("02", "TRAIN", "180 initial days\nchronological history", TEAL),
        ("03", "FORECAST", "Two models × 24 hours\nfor each test day", ORANGE),
        ("04", "UPDATE", "Add actuals after the\nforecast is complete", GREEN),
        ("05", "EVALUATE", "Point error + interval\ncoverage, width, loss", BLUE),
    ]
    xs = [0.72, 3.22, 5.72, 8.22, 10.72]
    for (number, title, body, color), x in zip(steps, xs):
        add_box(slide, x, 2.15, 1.93, 2.26, PANEL)
        add_text(slide, number, x + 0.15, 2.37, 1.63, 0.35, size=20, color=color, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, title, x + 0.13, 2.91, 1.67, 0.29, size=11, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
        add_text(slide, body, x + 0.17, 3.39, 1.59, 0.72, size=11, color=MUTED, align=PP_ALIGN.CENTER)
    for x in [2.78, 5.28, 7.78, 10.28]:
        add_arrow(slide, x, 3.24, x + 0.38, 3.24)
    add_card(slide, 1.02, 4.98, 5.32, 1.1, "POINT FORECAST METRICS", "MAE • RMSE • sMAPE (instead of MAPE for zero/negative prices)", BLUE, body_size=11)
    add_card(slide, 6.92, 4.98, 5.32, 1.1, "INTERVAL METRICS", "80% coverage • mean width • 10th / 90th pinball loss", ORANGE, body_size=11)
    add_footer(slide, 9)

    # 10 — Results
    slide = new_slide(prs, "Results: accuracy vs. interval calibration", "520-day test · measured outcome")
    add_picture(slide, figures["metrics"], 0.68, 1.44, 6.25, 3.6)
    rows = [
        ["TEST METRIC", "SARIMA–GARCH", "QUANTILE GB"],
        [
            "80% interval coverage",
            f"{sarima_metrics['coverage_80']:.1%}",
            f"{quantile_metrics['coverage_80']:.1%}",
        ],
        [
            "Mean interval width",
            f"€{sarima_metrics['mean_interval_width']:.2f}/MWh",
            f"€{quantile_metrics['mean_interval_width']:.2f}/MWh",
        ],
        [
            "10th-percentile pinball",
            f"{sarima_metrics['pinball_10']:.2f}",
            f"{quantile_metrics['pinball_10']:.2f}",
        ],
        [
            "90th-percentile pinball",
            f"{sarima_metrics['pinball_90']:.2f}",
            f"{quantile_metrics['pinball_90']:.2f}",
        ],
    ]
    add_table(slide, rows, 7.14, 1.65, 5.36, 3.32, [2.33, 1.54, 1.49])
    add_box(slide, 0.82, 5.39, 11.66, 0.84, PANEL_ALT)
    add_text(slide, f"Point error favors SARIMA–GARCH ({sarima_metrics['mae']:.2f} vs. {quantile_metrics['mae']:.2f} MAE).", 1.06, 5.64, 4.2, 0.42, size=13, color=BLUE, bold=True)
    add_text(slide, f"Quantile coverage: {quantile_metrics['coverage_80']:.1%} (nominal target 80%).", 5.34, 5.64, 6.8, 0.34, size=14, color=ORANGE, bold=True)
    add_text(slide, "Coverage and width must be read together: neither metric alone proves an interval is useful.", 0.87, 6.52, 11.5, 0.26, size=12, color=MUTED)
    add_footer(slide, 10)

    # 11 — Forecast trace
    slide = new_slide(prs, "What the forecasts look like in practice", "Actual vs. forecast · last 7 test days")
    add_picture(slide, figures["forecast"], 0.82, 1.55, 11.6, 4.25)
    add_pill(slide, "BLACK  ACTUAL", 0.94, 6.0, 1.64, WHITE)
    add_pill(slide, "BLUE  SARIMA–GARCH", 2.76, 6.0, 2.25, BLUE)
    add_pill(slide, "ORANGE  QUANTILE MEDIAN", 5.18, 6.0, 2.66, ORANGE)
    add_text(slide, "Shaded bands = nominal 80% prediction intervals. Spikes remain hard to anticipate.", 8.1, 6.04, 4.1, 0.34, size=11, color=MUTED)
    add_footer(slide, 11)

    # 12 — App screenshot/dashboard
    slide = new_slide(prs, "A working input → output demo", "Interactive dashboard")
    dashboard_screenshot = ASSETS / "dashboard_top_cropped.png"
    if dashboard_screenshot.is_file():
        add_picture(slide, dashboard_screenshot, 0.72, 1.47, 8.65, 4.98)
        add_card(slide, 9.68, 1.64, 2.88, 1.1, "INPUT", "Choose a held-out UTC test date.", TEAL, body_size=11)
        add_card(slide, 9.68, 2.98, 2.88, 1.1, "OUTPUT", "24 hourly forecasts + 80% bounds.", BLUE, body_size=11)
        add_card(slide, 9.68, 4.32, 2.88, 1.1, "EVALUATE", "Actuals and daily errors shown separately.", ORANGE, body_size=11)
    else:
        add_box(slide, 0.76, 1.53, 7.6, 4.8, PANEL_ALT, line=GRID)
        add_text(slide, "INTERACTIVE DEMO", 1.08, 1.94, 6.8, 0.32, size=12, color=TEAL, bold=True)
        add_text(slide, "Date selector → 24-hour forecast table → interval coverage and error", 1.08, 2.52, 6.65, 1.0, size=23, bold=True)
        add_text(slide, "The selector chooses a historical holdout day. It does not retrain the models.", 1.08, 4.23, 6.5, 0.78, size=14, color=MUTED)
        add_card(slide, 8.72, 1.72, 3.72, 1.2, "INPUT", "Choose a held-out UTC test date.", TEAL)
        add_card(slide, 8.72, 3.18, 3.72, 1.2, "OUTPUT", "24 hourly forecasts and intervals.", BLUE)
        add_card(slide, 8.72, 4.64, 3.72, 1.2, "DEMO", "Run locally with Streamlit.", ORANGE)
    add_text(slide, "INR is a display conversion of DE-LU prices—not an Indian market quote.", 9.68, 5.95, 2.88, 0.55, size=10, color=MUTED)
    add_text(slide, "Live demo: select 2026-08-31 UTC → inspect the hourly table → explain actuals are for evaluation only.", 0.8, 6.65, 11.8, 0.25, size=11, color=MUTED)
    add_footer(slide, 12, "DASHBOARD: app.py  •  RUN: python -m streamlit run app.py")

    # 13 — Genuine hourly-output screenshots
    slide = new_slide(prs, "Inspect a test day, hour by hour", "Dashboard screenshots")
    selected_screenshot = ASSETS / "selected_day_table_cropped.png"
    forecast_screenshot = ASSETS / "forecast_chart_cropped.png"
    if selected_screenshot.is_file() and forecast_screenshot.is_file():
        add_text(slide, "SELECTED DATE + FORECAST TABLE", 0.82, 1.42, 5.7, 0.27, size=10, color=TEAL, bold=True)
        add_text(slide, "ACTUALS VS. FORECASTS + INTERVALS", 6.85, 1.42, 5.7, 0.27, size=10, color=ORANGE, bold=True)
        add_picture(slide, selected_screenshot, 0.75, 1.82, 5.95, 4.3)
        add_picture(slide, forecast_screenshot, 6.68, 1.82, 5.95, 4.3)
        add_text(slide, "Actuals are for evaluation only. Scroll the live table to inspect all 24 hourly rows.", 0.83, 6.28, 11.7, 0.33, size=12, color=MUTED)
    else:
        add_card(slide, 0.85, 1.7, 5.6, 2.0, "SELECTED-DAY OUTPUT", "24 hourly actuals, point forecasts, and lower/upper prediction bounds.", TEAL)
        add_card(slide, 6.85, 1.7, 5.6, 2.0, "FORECAST CHART", "Actual values, model predictions, and uncertainty bands.", ORANGE)
        add_text(slide, "Run the dashboard locally to interact with the date selector and scroll the hourly table.", 0.9, 4.7, 11.5, 0.45, size=15, color=MUTED)
    add_footer(slide, 13, "REAL DASHBOARD CAPTURES  •  HELD-OUT ACTUALS ARE FOR EVALUATION ONLY")

    # 14 — Scorecard screenshot
    slide = new_slide(prs, "Compare models in the live scorecard", "Dashboard screenshot")
    comparison_screenshot = ASSETS / "model_comparison_cropped.png"
    if comparison_screenshot.is_file():
        add_picture(slide, comparison_screenshot, 0.72, 1.55, 7.25, 4.75)
    else:
        add_picture(slide, figures["metrics"], 0.72, 1.55, 7.25, 4.75)
    add_card(
        slide,
        8.18,
        1.75,
        4.25,
        1.42,
        "LOWER POINT ERROR",
        f"SARIMA–GARCH MAE: €{sarima_metrics['mae']:.2f}/MWh",
        BLUE,
        body_size=13,
    )
    add_card(
        slide,
        8.18,
        3.48,
        4.25,
        1.42,
        "COVERAGE NEAR 80%",
        f"Quantile boosting: {quantile_metrics['coverage_80']:.1%}",
        ORANGE,
        body_size=13,
    )
    add_text(slide, "Select a metric in the app to compare scorecards in the chosen display currency.", 0.82, 6.48, 11.7, 0.3, size=12, color=MUTED)
    add_footer(slide, 14, "FULL-TEST METRICS  •  RAW RESULTS STAY IN EUR/MWh; APP SCORECARD VALUES CAN BE CONVERTED")

    # 15 — Scope and future work
    slide = new_slide(prs, "Clear limits make the result more credible", "Limitations & next steps")
    add_card(slide, 0.78, 1.52, 5.66, 1.28, "SINGLE ZONE + HISTORICAL WINDOW", "One DE-LU holdout cannot establish general performance.", ORANGE, body_size=13)
    add_card(slide, 6.82, 1.52, 5.66, 1.28, "PRICE-ONLY FEATURES", "No weather, demand, generation, fuel or neighboring-zone inputs.", BLUE, body_size=13)
    add_card(slide, 0.78, 3.12, 5.66, 1.28, "UTC DELIVERY DAYS", "UTC 24-hour blocks differ from local market days at daylight-saving changes.", RED, body_size=13)
    add_card(slide, 6.82, 3.12, 5.66, 1.28, "INTERVAL ASSUMPTION", "Normal standardized GARCH innovations may miss asymmetric tails.", TEAL, body_size=13)
    add_box(slide, 0.78, 4.88, 11.7, 1.07, PANEL_ALT)
    add_text(slide, "NEXT", 1.04, 5.21, 0.85, 0.28, size=12, color=TEAL, bold=True)
    add_text(slide, "Add external drivers • test multiple zones/seasons • calibrate intervals • evaluate decision value", 2.0, 5.17, 9.95, 0.38, size=15, bold=True)
    add_text(slide, "SDG 7 is the primary connection; SDG 13 is secondary through energy-system planning. Forecasts alone do not achieve either goal.", 0.83, 6.28, 11.8, 0.42, size=12, color=MUTED)
    add_footer(slide, 15)

    # 16 — Close / references
    slide = new_slide(prs, "Takeaway: forecast the price and the risk", "Conclusion")
    add_text(slide, "01", 0.86, 1.58, 0.72, 0.38, size=18, color=TEAL, bold=True)
    add_text(slide, "Chronological testing makes the comparison meaningful.", 1.68, 1.57, 8.7, 0.4, size=18, bold=True)
    add_text(slide, "02", 0.86, 2.44, 0.72, 0.38, size=18, color=BLUE, bold=True)
    add_text(slide, "SARIMA–GARCH delivered lower point error in this holdout.", 1.68, 2.43, 8.7, 0.4, size=18, bold=True)
    add_text(slide, "03", 0.86, 3.31, 0.72, 0.38, size=18, color=ORANGE, bold=True)
    add_text(slide, "Quantile boosting gave coverage closer to the 80% target.", 1.68, 3.30, 8.7, 0.4, size=18, bold=True)
    add_text(slide, "The right model depends on the decision and the cost of forecast errors.", 1.7, 4.03, 9.8, 0.44, size=16, color=MUTED)
    add_box(slide, 0.78, 4.9, 11.66, 1.08, PANEL_ALT)
    add_text(slide, "QUESTIONS?", 1.08, 5.25, 3.5, 0.36, size=24, color=TEAL, bold=True)
    add_text(slide, "Thank you  •  [Student name]  •  [USN]", 6.8, 5.29, 4.9, 0.32, size=14, color=WHITE, align=PP_ALIGN.RIGHT)
    add_footer(slide, 16)

    # 17 — References
    slide = new_slide(prs, "References & data attribution", "Sources")
    references = [
        "[1] Garcia et al. (2005). A GARCH forecasting model to predict day-ahead electricity prices. IEEE Transactions on Power Systems. doi:10.1109/TPWRS.2005.846044",
        "[2] Ziel (2016). Forecasting electricity spot prices using Lasso. IEEE Transactions on Power Systems. doi:10.1109/TPWRS.2016.2521545",
        "[3] Nowotarski & Weron (2018). Recent advances in electricity price forecasting: probabilistic forecasting. Renewable & Sustainable Energy Reviews. doi:10.1016/j.rser.2017.05.234",
        "[4] Uniejewski, Weron & Ziel (2018). Variance stabilizing transformations for electricity spot price forecasting. IEEE Transactions on Power Systems. doi:10.1109/TPWRS.2017.2734563",
        "[5] Lago et al. (2021). Forecasting day-ahead electricity prices: algorithms, best practices and open-access benchmark. Applied Energy. doi:10.1016/j.apenergy.2021.116983",
        "Data: Energy-Charts price API, DE-LU bidding zone; attribution to Bundesnetzagentur / SMARD; CC BY 4.0. https://api.energy-charts.info/",
        "Methods/software: statsmodels SARIMAX; arch GARCH; scikit-learn GradientBoostingRegressor quantile loss.",
    ]
    lines = [(item, WHITE if i < 5 else MUTED, i < 5) for i, item in enumerate(references)]
    add_rich_lines(slide, lines, 0.88, 1.55, 11.5, 4.96, size=12, spacing=10)
    add_text(slide, f"All performance values are computed from the included {metadata['test_days']}-day held-out predictions.", 0.9, 6.58, 11.2, 0.24, size=10, color=TEAL)
    add_footer(slide, 17)

    prs.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build())
