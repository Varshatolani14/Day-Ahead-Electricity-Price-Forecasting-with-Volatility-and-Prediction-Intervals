"""Generate the TSA AAT report in the supplied template's section order."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    LongTable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TITLE = (
    "Day-Ahead Electricity Price Forecasting with Volatility and Prediction "
    "Intervals Using SARIMA-GARCH and Quantile Gradient Boosting"
)

CONTENTS = [
    "1. ABSTRACT",
    "2. INTRODUCTION AND PROBLEM IDENTIFICATION",
    "2.1 Application Domain",
    "2.2 Problem Statement",
    "2.3 Need for Forecasting",
    "2.4 Objectives",
    "2.5 Scope of the Study",
    "3. LITERATURE REVIEW AND RESEARCH GAP",
    "3.1 Review of Existing Research",
    "3.2 Research Gap",
    "3.3 Proposed Approach",
    "4. DATASET DESCRIPTION AND EXPLORATORY DATA ANALYSIS",
    "4.1 Dataset Source",
    "4.2 Variables and Data Description",
    "4.3 Data Preparation",
    "4.4 Exploratory Data Analysis",
    "5. BASELINE FORECASTING MODEL",
    "5.1 Model Selection",
    "5.2 Model Methodology",
    "5.3 Implementation",
    "5.4 Baseline Results",
    "6. PROPOSED MODEL AND ENHANCEMENT",
    "6.1 Motivation for Improvement",
    "6.2 Proposed Enhancement",
    "6.3 Methodology and Implementation",
    "6.4 Expected Advantage",
    "6.5 Proposed Model Results",
    "7. PERFORMANCE EVALUATION AND COMPARISON",
    "7.1 Evaluation Measures",
    "7.2 Comparative Results",
    "7.3 Interpretation of Results",
    "8. CONCLUSION AND FUTURE SCOPE",
    "8.1 Conclusion",
    "8.2 Future Scope",
    "8.3 SDG Addressed",
    "9. REFERENCES",
    "10. TEAM CONTRIBUTION",
]

# The first column identifies each paper and describes its research problem and data.
# The remaining columns follow the literature-review fields in the supplied rubric.
PAPERS = [
    [
        "Paper 1 — Garcia et al. (2005). Problem: next-day spot-price prediction. "
        "Data: deregulated mainland Spain and California electricity markets.",
        "GARCH-based day-ahead price forecasting, modelling conditional "
        "heteroskedasticity.",
        "Empirical day-ahead price-forecast results are reported for both "
        "markets. The accessible bibliographic abstract does not name a "
        "specific error statistic.",
        "Shows that GARCH methods can be applied to electricity-market price "
        "forecasting, where uncertainty changes over time.",
        "Older market regimes and two market datasets; historical results "
        "may not generalize to current market design or other zones.",
        "doi.org/10.1109/TPWRS.2005.846044",
    ],
    [
        "Paper 2 — Ziel (2016). Problem: next-day electricity spot-price "
        "forecasting with intraday dependence. Data: German/Austrian EPEX "
        "prices; out-of-sample period 969 days.",
        "Twenty-four LASSO linear regressions with autoregressive and "
        "intraday price features.",
        "Out-of-sample MAE and RMSE; both are appropriate when prices can "
        "be negative.",
        "LASSO can select useful lag effects while shrinking parameters; "
        "the paper reports benefits against two popular approaches.",
        "A point-forecast method; it does not directly provide calibrated "
        "prediction intervals.",
        "doi.org/10.1109/TPWRS.2016.2521545",
    ],
    [
        "Paper 3 — Nowotarski & Weron (2018). Problem: estimating "
        "probabilistic electricity-price forecasts. Data: review of "
        "published markets and studies; no single common dataset.",
        "Review and taxonomy of probabilistic forecasting methods, "
        "including quantile, interval, and density forecasts.",
        "Reviews probabilistic forecast evaluation and the need to assess "
        "both calibration and sharpness; measures depend on the studies.",
        "Explains why distributions or prediction intervals add useful "
        "risk information beyond a single point forecast.",
        "A literature review rather than one controlled model experiment; "
        "underlying studies differ in data and test design.",
        "doi.org/10.1016/j.rser.2017.05.234",
    ],
    [
        "Paper 4 — Uniejewski, Weron & Ziel (2018). Problem: price spikes "
        "and changing variance, including near-zero or negative prices. "
        "Data: 12 datasets from diverse power markets.",
        "Sixteen variance-stabilizing transformations tested with "
        "regression and neural-network model classes.",
        "Comparative forecasting study across datasets and model classes; "
        "the article compares out-of-sample forecast accuracy.",
        "The probability-integral transform combined with a standard "
        "Gaussian distribution performed best among the tested transforms.",
        "Transformation performance depends on the data and fitted "
        "distribution; the study does not compare the exact two-model "
        "pipeline used here.",
        "doi.org/10.1109/TPWRS.2017.2734563",
    ],
    [
        "Paper 5 — Lago et al. (2021). Problem: reproducible, rigorous "
        "comparison of day-ahead forecasting methods. Data: multi-year, "
        "multi-market public benchmark datasets.",
        "Literature survey, comparison of statistical and deep-learning "
        "methods, and an open-access benchmark/toolbox.",
        "Discusses MAE, RMSE, and MAPE for point forecasts and recommends "
        "consistent test periods, benchmarks, and statistical testing.",
        "Identifies common weaknesses in electricity-price comparisons "
        "and supplies datasets, forecasts, and tools for reproducible "
        "benchmarking.",
        "Benchmark coverage is limited to its included markets and "
        "periods; results do not guarantee performance under later "
        "market regimes.",
        "doi.org/10.1016/j.apenergy.2021.116983",
    ],
]

REFERENCES = [
    "Garcia, R. C., Contreras, J., van Akkeren, M., & Garcia, J. B. C. "
    "(2005). A GARCH forecasting model to predict day-ahead electricity "
    "prices. IEEE Transactions on Power Systems, 20(2), 867-874. "
    "https://doi.org/10.1109/TPWRS.2005.846044",
    "Ziel, F. (2016). Forecasting electricity spot prices using Lasso: "
    "On capturing the autoregressive intraday structure. IEEE Transactions "
    "on Power Systems, 31(6), 4977-4987. "
    "https://doi.org/10.1109/TPWRS.2016.2521545",
    "Nowotarski, J., & Weron, R. (2018). Recent advances in electricity "
    "price forecasting: A review of probabilistic forecasting. Renewable "
    "and Sustainable Energy Reviews, 81, 1548-1568. "
    "https://doi.org/10.1016/j.rser.2017.05.234",
    "Uniejewski, B., Weron, R., & Ziel, F. (2018). Variance stabilizing "
    "transformations for electricity spot price forecasting. IEEE "
    "Transactions on Power Systems, 33(2), 2219-2229. "
    "https://doi.org/10.1109/TPWRS.2017.2734563",
    "Lago, J., Marcjasz, G., De Schutter, B., & Weron, R. (2021). "
    "Forecasting day-ahead electricity prices: A review of state-of-the-art "
    "algorithms, best practices and an open-access benchmark. Applied "
    "Energy, 293, 116983. https://doi.org/10.1016/j.apenergy.2021.116983",
    "Bundesnetzagentur / SMARD. Energy-Charts price API, DE-LU bidding "
    "zone. Data supplied under CC BY 4.0. https://api.energy-charts.info/",
    "Statsmodels. SARIMAX documentation. "
    "https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html",
    "ARCH. arch_model documentation. https://arch.readthedocs.io/",
    "Scikit-learn. GradientBoostingRegressor documentation. "
    "https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.GradientBoostingRegressor.html",
]

SARIMA_CODE = """sarima = SARIMAX(
    train.tail(180 * 24),
    order=(1, 0, 1),
    seasonal_order=(1, 0, 1, 24),
    trend="c",
    enforce_stationarity=False,
    enforce_invertibility=False,
).fit(disp=False)
forecast_24h = sarima.get_forecast(steps=24).predicted_mean

residuals = sarima.resid.dropna()
scale = residuals.std()
garch = arch_model(
    residuals / scale, mean="Zero", vol="GARCH",
    p=1, q=1, rescale=False
).fit(disp="off")"""

QUANTILE_CODE = """models = {}
for tau in (0.10, 0.50, 0.90):
    models[tau] = GradientBoostingRegressor(
        loss="quantile", alpha=tau,
        n_estimators=150, learning_rate=0.05,
        max_depth=2, min_samples_leaf=15,
        subsample=0.8, random_state=42,
    ).fit(X_train, y_train)

q10, q50, q90 = (models[q].predict(X_day)
                 for q in (0.10, 0.50, 0.90))"""


def _report_content(
    prices_path: Path,
    forecasts_path: Path,
    metrics_path: Path,
) -> dict[str, Any]:
    prices_frame = pd.read_csv(prices_path, parse_dates=["timestamp_utc"])
    forecasts = pd.read_csv(forecasts_path, parse_dates=["timestamp_utc"])
    metadata = json.loads(metrics_path.read_text(encoding="utf-8"))
    prices = pd.to_numeric(prices_frame["price_eur_mwh"], errors="raise")
    metrics = metadata["metrics"]
    preferred = min(metrics, key=lambda model: metrics[model]["mae"])
    names = {
        "sarima_garch": "SARIMA-GARCH",
        "quantile_boosting": "Quantile Gradient Boosting",
    }
    data_start = pd.Timestamp(prices_frame["timestamp_utc"].min())
    data_end = pd.Timestamp(prices_frame["timestamp_utc"].max())
    abstract = (
        "Day-ahead electricity prices show daily patterns, price spikes, "
        "negative values, and changing uncertainty. This project forecasts "
        "hourly DE-LU prices from the public Energy-Charts/SMARD dataset, "
        "covering 1 October 2024 to 31 August 2026. Existing research uses "
        "autoregressive price models, volatility models, and probabilistic "
        "forecasting, but comparisons can be difficult when markets, test "
        "periods, and evaluation procedures differ. This study compares a "
        "seasonal SARIMA-GARCH baseline with quantile gradient boosting "
        "on the same chronological rolling day-ahead test. The first 180 "
        "days initialize training; the following "
        f"{metadata['test_days']} days provide "
        f"{metadata['test_observations']:,} held-out hourly forecasts. "
        "SARIMA models the conditional mean and GARCH models changing "
        "residual variance. Three gradient-boosting models directly estimate "
        "the 10th, 50th, and 90th conditional price quantiles. SARIMA-GARCH "
        "achieved MAE "
        f"{metrics['sarima_garch']['mae']:.2f} EUR/MWh; quantile boosting "
        f"achieved {metrics['quantile_boosting']['mae']:.2f} EUR/MWh. Their "
        "80% interval coverages were "
        f"{metrics['sarima_garch']['coverage_80']:.1%} and "
        f"{metrics['quantile_boosting']['coverage_80']:.1%}, respectively. "
        "The results show the value of reporting both point accuracy and "
        "uncertainty, but apply only to this zone, data window, and feature set. "
        "An interactive dashboard supports test-day, model, history, and display-unit "
        "exploration. Currency conversion changes displayed values only; INR remains "
        "a converted DE-LU price, not an Indian-market forecast."
    )
    return {
        "metadata": metadata,
        "metrics": metrics,
        "names": names,
        "preferred_name": names[preferred],
        "prices": prices,
        "forecasts": forecasts,
        "data_rows": len(prices_frame),
        "data_start": data_start,
        "data_end": data_end,
        "mean": float(prices.mean()),
        "median": float(prices.median()),
        "std": float(prices.std()),
        "minimum": float(prices.min()),
        "maximum": float(prices.max()),
        "negative_count": int((prices < 0).sum()),
        "zero_count": int((prices == 0).sum()),
        "missing_count": int(prices.isna().sum()),
        "abstract": abstract,
    }


def _section_content(content: dict[str, Any]) -> list[tuple[str, list[str]]]:
    meta = content["metadata"]
    start = content["data_start"]
    end = content["data_end"]
    n = content["data_rows"]
    sarima = content["metrics"]["sarima_garch"]
    qgb = content["metrics"]["quantile_boosting"]
    return [
        (
            "2. INTRODUCTION AND PROBLEM IDENTIFICATION",
            [
                (
                    "2.1 Application Domain",
                    "The application domain is smart-city energy systems and electricity "
                    "markets. Day-ahead prices guide electricity procurement and inform "
                    "decisions by suppliers, consumers, storage operators, and grid "
                    "planners. Prediction intervals add a practical view of price risk.",
                ),
                (
                    "2.2 Problem Statement",
                    "Using hourly DE-LU day-ahead prices available before a delivery day, "
                    "forecast all 24 hourly prices for that day and provide uncertainty "
                    "intervals. Forecasts must be evaluated against actual held-out prices "
                    "without using those prices to construct that day's prediction.",
                ),
                (
                    "2.3 Need for Forecasting",
                    "A day-ahead estimate helps plan bids, energy purchases, flexible "
                    "demand, and storage schedules. Lower and upper bounds help decision "
                    "makers consider adverse and favorable price outcomes rather than "
                    "relying on a single estimate.",
                ),
                (
                    "2.4 Objectives",
                    "1. Obtain and validate an attributed market-price dataset. "
                    "2. Explore trend, hourly seasonality, negative values, and price "
                    "variation. 3. Implement a SARIMA-GARCH baseline. 4. Implement "
                    "10th/50th/90th quantile gradient boosting. 5. Compare both models "
                    "using chronological out-of-sample point and interval metrics.",
                ),
                (
                    "2.5 Scope of the Study",
                    f"The study covers one DE-LU hourly UTC price series from {start:%Y-%m-%d} "
                    f"through {end:%Y-%m-%d}. The first 180 days initialize the models; "
                    f"the next {meta['test_days']} complete days are evaluated as rolling "
                    "24-hour forecasts. No weather, load, generation, fuel, or neighboring "
                    "market inputs are used. UTC days do not exactly match local market "
                    "days at daylight-saving changes. The dashboard date selector is "
                    "limited to this stored held-out period; it does not produce forecasts "
                    "for arbitrary historical or future dates. Currency and MWh/kWh "
                    "selections change display values only. INR is a converted DE-LU "
                    "price, not a forecast for India.",
                ),
            ],
        ),
        (
            "3. LITERATURE REVIEW AND RESEARCH GAP",
            [
                (
                    "3.2 Research Gap",
                    "Research demonstrates that price lags, changing volatility, and "
                    "probabilistic forecasts matter [1-5]. Published comparisons may "
                    "use different markets, time periods, benchmarks, and error measures, "
                    "making results hard to compare. This project addresses a bounded "
                    "classroom gap: evaluate a seasonal SARIMA-GARCH interval and a direct "
                    "quantile-boosting interval on the same long chronological DE-LU "
                    "holdout, and report both point error and interval quality. It does "
                    "not claim that this model comparison has never been studied.",
                ),
                (
                    "3.3 Proposed Approach",
                    "Use one public price series; aggregate to hourly UTC; reserve the "
                    "first 180 days for initialization; issue rolling next-day forecasts "
                    "for the remaining complete days; compare SARIMA-GARCH with three "
                    "quantile-boosting models using the same actual prices and evaluation "
                    "measures.",
                ),
            ],
        ),
        (
            "4. DATASET DESCRIPTION AND EXPLORATORY DATA ANALYSIS",
            [
                (
                    "4.1 Dataset Source",
                    "Energy-Charts public price API, DE-LU bidding zone; API attribution "
                    "to Bundesnetzagentur / SMARD. License: CC BY 4.0. The supplied "
                    "reproducible CSV contains "
                    f"{n:,} hourly observations, from {start:%Y-%m-%d %H:%M UTC} "
                    f"through {end:%Y-%m-%d %H:%M UTC}.",
                ),
                (
                    "4.2 Variables and Data Description",
                    "timestamp_utc is the observation timestamp in UTC. price_eur_mwh "
                    "is the market price in EUR/MWh. Descriptive statistics: mean "
                    f"{content['mean']:.2f}, median {content['median']:.2f}, standard "
                    f"deviation {content['std']:.2f}, minimum {content['minimum']:.2f}, "
                    f"and maximum {content['maximum']:.2f} EUR/MWh. The series includes "
                    f"{content['negative_count']} negative-price hours and "
                    f"{content['zero_count']} zero-price hours.",
                ),
                (
                    "4.3 Data Preparation",
                    "Convert API epoch timestamps to UTC; retain valid price values; "
                    "restrict the request to the documented date range; average the "
                    "source's 15-minute observations to hourly means; check a continuous "
                    "hourly index; and retain negative prices. Lag and rolling features "
                    "for a forecast are shifted so only prices available at least 24 hours "
                    "before the target are used. No random train/test split is used.",
                ),
                (
                    "4.4 Exploratory Data Analysis",
                    "The daily average-price plot shows broad level changes and occasional "
                    "large movements. The median-by-UTC-hour plot shows an intraday "
                    "pattern. Extreme and negative observations are genuine market "
                    "values, not removed outliers. These observations motivate a 24-hour "
                    "seasonal SARIMA component, lagged/calendar features, and explicit "
                    "conditional-uncertainty estimates.",
                ),
            ],
        ),
        (
            "5. BASELINE FORECASTING MODEL",
            [
                (
                    "5.1 Model Selection",
                    "SARIMA provides an interpretable statistical baseline for serial "
                    "dependence and daily seasonality. GARCH is added to model "
                    "time-varying variance in the baseline's forecast residuals. This "
                    "directly addresses volatility while keeping the mean model compact.",
                ),
                (
                    "5.2 Model Methodology",
                    "The baseline is SARIMA(1,0,1)x(1,0,1,24), estimated on the most "
                    "recent 180 pre-test days. In lag notation, "
                    "phi(B)Phi(B^24)(y_t-c)=theta(B)Theta(B^24)epsilon_t. Standardized "
                    "SARIMA residuals are modelled by GARCH(1,1): "
                    "epsilon_t=sigma_t z_t and "
                    "sigma_t^2=omega+alpha epsilon_(t-1)^2+beta sigma_(t-1)^2. "
                    "The nominal 80% interval is forecast mean +/- 1.645 forecast "
                    "standard deviations. This interval assumes approximately normal "
                    "standardized innovations; the test coverage checks that assumption "
                    "empirically.",
                ),
                (
                    "5.3 Implementation",
                    "Fit SARIMAX and GARCH using only initial training data. Generate "
                    "the next 24-hour mean and variance forecast. After the whole day-ahead "
                    "forecast is recorded, extend the state-space model with that day's "
                    "actual prices without re-estimating parameters, and update GARCH "
                    "variance from resulting residuals. Repeat for each test day. "
                    "Full implementation: src/forecasting.py; execution: main.py. The "
                    "Streamlit dashboard lets users select a held-out UTC test date, "
                    "chart window, models, actual-price visibility, interval visibility, "
                    "line or step charts, and linear or symmetric-log axes. Its scorecard "
                    "and history explorer offer selectable metrics, hourly/daily/weekly "
                    "aggregation, rolling averages, typical UTC-hour views, price "
                    "distributions, and CSV downloads. Users can select display currency "
                    "and MWh/kWh. Available currencies use published ECB reference rates "
                    "through Frankfurter; users may enter a positive manual rate for "
                    "another three-letter currency code, while EUR remains available offline. These "
                    "conversions affect displayed price-valued results and downloads only; "
                    "source EUR/MWh data, model fitting, stored forecasts, interval "
                    "coverage, and percentage metrics remain unchanged.",
                ),
                (
                    "5.4 Baseline Results",
                    f"Over {meta['test_days']} test days "
                    f"({meta['test_observations']:,} hours), SARIMA-GARCH obtained MAE "
                    f"{sarima['mae']:.2f} EUR/MWh, RMSE {sarima['rmse']:.2f} EUR/MWh, "
                    f"sMAPE {sarima['smape_percent']:.2f}%, 80% interval coverage "
                    f"{sarima['coverage_80']:.1%}, and mean interval width "
                    f"{sarima['mean_interval_width']:.2f} EUR/MWh. See the forecast plot "
                    "and comparative table.",
                ),
            ],
        ),
        (
            "6. PROPOSED MODEL AND ENHANCEMENT",
            [
                (
                    "6.1 Motivation for Improvement",
                    "The SARIMA-GARCH interval uses a symmetric parametric construction "
                    "around the mean and assumes a standardized innovation distribution. "
                    "Electricity-price errors can be asymmetric and affected by spikes, "
                    "so direct estimation of conditional quantiles provides a useful "
                    "alternative for comparison.",
                ),
                (
                    "6.2 Proposed Enhancement",
                    "Fit three separate GradientBoostingRegressor models with quantile "
                    "loss at tau=0.10, 0.50, and 0.90. The 50th percentile is the point "
                    "forecast; the 10th and 90th percentiles define a nominal 80% "
                    "prediction interval.",
                ),
                (
                    "6.3 Methodology and Implementation",
                    "Features include 24-, 48-, and 168-hour lagged prices; the mean and "
                    "standard deviation of the preceding 24 prices available at the "
                    "forecast origin; the mean of the preceding 168 available prices; "
                    "and cyclical hour, weekday, and month features. Each model uses "
                    "150 estimators, learning rate 0.05, depth 2, minimum leaf size 15, "
                    "subsample 0.8, and random seed 42. The quantile objective is "
                    "rho_tau(u)=u(tau-I[u<0]), where u=y-yhat. Quantile outputs are "
                    "ordered to prevent crossing. Complete code: src/forecasting.py.",
                ),
                (
                    "6.4 Expected Advantage",
                    "Direct quantile loss does not require the lower and upper bounds "
                    "to be symmetric around a point forecast. Calendar and weekly-lag "
                    "features represent effects not explicitly encoded by a single "
                    "24-hour seasonal term. These are expected advantages, not a "
                    "guarantee of lower errors; the common test set determines the "
                    "observed result.",
                ),
                (
                    "6.5 Proposed Model Results",
                    f"Quantile boosting obtained MAE {qgb['mae']:.2f} EUR/MWh, RMSE "
                    f"{qgb['rmse']:.2f} EUR/MWh, sMAPE {qgb['smape_percent']:.2f}%, "
                    f"80% interval coverage {qgb['coverage_80']:.1%}, and mean interval "
                    f"width {qgb['mean_interval_width']:.2f} EUR/MWh. The orange "
                    "quantile interval and median are shown in the forecast comparison plot.",
                ),
            ],
        ),
        (
            "7. PERFORMANCE EVALUATION AND COMPARISON",
            [
                (
                    "7.1 Evaluation Measures",
                    "MAE=(1/n)sum|y-yhat| is interpretable in EUR/MWh. "
                    "RMSE=sqrt((1/n)sum(y-yhat)^2) penalizes large errors. MAPE is "
                    "not used because electricity prices may be zero or negative; "
                    "sMAPE=(200/n)sum(|y-yhat|/(|y|+|yhat|)) is reported instead. "
                    "For the nominal 80% interval, coverage is the fraction of actual "
                    "prices between lower and upper bounds, and mean width measures "
                    "interval sharpness. Pinball loss evaluates the 10th and 90th "
                    "quantile forecasts.",
                ),
                (
                    "7.2 Comparative Results",
                    f"Both models are evaluated on the same {meta['test_observations']:,} "
                    f"held-out hourly prices across {meta['test_days']} days. The table "
                    "compares point error, 80% interval coverage and width, and the "
                    "10th- and 90th-quantile pinball losses. SARIMA-GARCH has lower "
                    "MAE and RMSE; quantile boosting has coverage closer to the nominal "
                    "80% and a slightly narrower interval.",
                ),
                (
                    "7.3 Interpretation of Results",
                    f"SARIMA-GARCH has lower MAE ({sarima['mae']:.2f} vs. "
                    f"{qgb['mae']:.2f} EUR/MWh) and RMSE "
                    f"({sarima['rmse']:.2f} vs. {qgb['rmse']:.2f} EUR/MWh) on this "
                    f"{meta['test_days']}-day test. Quantile boosting coverage "
                    f"({qgb['coverage_80']:.1%}) is close to the nominal 80%; "
                    f"SARIMA-GARCH coverage is {sarima['coverage_80']:.1%}. The "
                    "quantile interval is slightly narrower. Coverage alone is not "
                    "sufficient, so width and pinball losses are also reported. "
                    "This single-zone backtest does not establish a universal winner.",
                ),
            ],
        ),
        (
            "8. CONCLUSION AND FUTURE SCOPE",
            [
                (
                    "8.1 Conclusion",
                    "The project addressed next-day DE-LU hourly price prediction using "
                    "a rolling 24-hour evaluation. The seasonal SARIMA-GARCH baseline "
                    "had the lower point errors; quantile boosting produced coverage "
                    "near its nominal 80% target with a slightly narrower interval. "
                    "Forecasts and intervals can support procurement, flexible-demand, "
                    "and storage planning, but are not guarantees of savings. Findings "
                    "are limited to this zone, input series, model settings, and test period. "
                    "The dashboard makes the held-out input-to-output comparison explorable; "
                    "currency and energy-unit selections are display conversions and do not "
                    "change either model's forecasts. An INR display is still DE-LU market data.",
                ),
                (
                    "8.2 Future Scope",
                    "Test across additional zones and seasons; include load, weather, "
                    "renewable generation, fuel, and neighboring-market variables; "
                    "calibrate intervals; handle local-market daylight-saving hours "
                    "explicitly; compare persistence and more forecasting baselines; "
                    "and test value in a defined operational decision.",
                ),
                (
                    "8.3 SDG Addressed",
                    "SDG 7 (Affordable and Clean Energy) is relevant because reliable "
                    "price forecasts can support efficient electricity use, flexible "
                    "demand, and storage scheduling. SDG 13 (Climate Action) is a "
                    "secondary connection through energy-system planning in renewable-rich "
                    "markets. A forecast alone does not ensure either SDG outcome.",
                ),
            ],
        ),
    ]


def _comparison_rows(content: dict[str, Any]) -> list[list[str]]:
    rows = [[
        "Model",
        "MAE\nEUR/MWh",
        "RMSE\nEUR/MWh",
        "sMAPE",
        "80% coverage",
        "Mean width\nEUR/MWh",
        "10% pinball",
        "90% pinball",
    ]]
    for model in ("sarima_garch", "quantile_boosting"):
        scores = content["metrics"][model]
        rows.append(
            [
                content["names"][model],
                f"{scores['mae']:.2f}",
                f"{scores['rmse']:.2f}",
                f"{scores['smape_percent']:.2f}%",
                f"{scores['coverage_80']:.1%}",
                f"{scores['mean_interval_width']:.2f}",
                f"{scores['pinball_10']:.2f}",
                f"{scores['pinball_90']:.2f}",
            ]
        )
    return rows


def _make_pipeline_table(pdf: bool, width: float, styles: dict[str, Any]) -> Any:
    labels = [
        "Public DE-LU\nprices",
        "Hourly UTC\ncleaning",
        "180-day initial\ntraining",
        "Rolling 24-hour\nforecasts",
        "SARIMA-GARCH\nvs. quantile GB",
        "Error and interval\nevaluation",
    ]
    arrow = "->" if pdf else "→"
    cells: list[Any] = []
    for index, label in enumerate(labels):
        cells.append(Paragraph(label.replace("\n", "<br/>"), styles["SmallCenter"]))
        if index != len(labels) - 1:
            cells.append(Paragraph(arrow, styles["SmallCenter"]))
    col_widths = [width / 11] * 11
    table = Table([cells], colWidths=col_widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#edf3f8")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#7691a8")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#aab8c4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _make_pdf(content: dict[str, Any], output: Path, root: Path) -> None:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "CoverTitleAAT",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#183b5b"),
            spaceAfter=15,
        )
    )
    styles.add(
        ParagraphStyle(
            "SectionAAT",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#183b5b"),
            spaceBefore=11,
            spaceAfter=6,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            "SubsectionAAT",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=colors.HexColor("#285a82"),
            spaceBefore=6,
            spaceAfter=3,
            keepWithNext=True,
        )
    )
    styles.add(
        ParagraphStyle(
            "BodyAAT",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=12,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            "SmallAAT",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=6.7,
            leading=8.4,
            spaceAfter=1,
        )
    )
    styles.add(
        ParagraphStyle(
            "SmallCenter",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=6.7,
            leading=8,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            "CodeAAT",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=6.8,
            leading=8.2,
            leftIndent=6,
            rightIndent=6,
            borderColor=colors.HexColor("#d5dfe8"),
            borderWidth=0.5,
            borderPadding=5,
            backColor=colors.HexColor("#f5f7f9"),
            spaceBefore=2,
            spaceAfter=5,
        )
    )
    page_width = letter[0] - 1.0 * inch
    story: list[Any] = [
        Spacer(1, 0.25 * inch),
        Paragraph("B. M. S. COLLEGE OF ENGINEERING", styles["Heading2"]),
        Paragraph("Autonomous Institute, Affiliated to VTU, Belagavi", styles["BodyAAT"]),
        Paragraph("DEPARTMENT OF MACHINE LEARNING", styles["Heading2"]),
        Paragraph(
            "Program: B.E. in Artificial Intelligence and Machine Learning",
            styles["BodyAAT"],
        ),
        Paragraph("Academic Year: 2026-27 | Session: July 2026 - December 2026", styles["BodyAAT"]),
        Spacer(1, 0.18 * inch),
        Paragraph("Time Series Analysis (24AM7PCTSA)", styles["Heading2"]),
        Paragraph("LAB AAT - DOMAIN-BASED TIME SERIES FORECASTING", styles["Heading2"]),
        Spacer(1, 0.2 * inch),
        Paragraph("AAT REPORT", styles["Heading1"]),
        Paragraph(f"Title: {TITLE}", styles["CoverTitleAAT"]),
        Paragraph("Application Domain: Smart City / Energy Systems", styles["BodyAAT"]),
        Paragraph("SDG addressed: SDG 7 - Affordable and Clean Energy; SDG 13 - Climate Action", styles["BodyAAT"]),
        Spacer(1, 0.12 * inch),
        Paragraph("Submitted by", styles["Heading3"]),
        Paragraph("Student Name: [Enter student name]", styles["BodyAAT"]),
        Paragraph("USN: [Enter USN]", styles["BodyAAT"]),
        Paragraph("Semester &amp; Section: [Enter semester and section]", styles["BodyAAT"]),
        Paragraph("Student Signature: ___________________________________", styles["BodyAAT"]),
        Spacer(1, 0.12 * inch),
        Paragraph("Valuation Report (to be filled by faculty)", styles["Heading3"]),
        Paragraph("Score: __________   Faculty In-charge: ______________________________", styles["BodyAAT"]),
        Paragraph("Comments: ______________________________________________________", styles["BodyAAT"]),
        Paragraph("Faculty Signature with date: ____________________________________", styles["BodyAAT"]),
        PageBreak(),
        Paragraph("TABLE OF CONTENTS", styles["SectionAAT"]),
    ]
    story.extend(Paragraph(item, styles["BodyAAT"]) for item in CONTENTS)
    story.extend(
        [
            PageBreak(),
            Paragraph("1. ABSTRACT", styles["SectionAAT"]),
            Paragraph(content["abstract"], styles["BodyAAT"]),
        ]
    )

    section_rows = _section_content(content)
    for title, paragraphs in section_rows:
        story.append(Paragraph(title, styles["SectionAAT"]))
        if title.startswith("3."):
            story.append(Paragraph("3.1 Review of Existing Research", styles["SubsectionAAT"]))
            headers = [
                "Problem / Dataset",
                "Method Used",
                "Evaluation Measures",
                "Key Findings",
                "Limitations",
                "Link of the paper",
            ]
            table_rows = [
                [Paragraph(f"<b>{header}</b>", styles["SmallAAT"]) for header in headers]
            ]
            for paper in PAPERS:
                table_rows.append([Paragraph(value, styles["SmallAAT"]) for value in paper])
            table = LongTable(
                table_rows,
                colWidths=[page_width * fraction for fraction in (0.24, 0.15, 0.16, 0.17, 0.17, 0.11)],
                repeatRows=1,
                hAlign="LEFT",
            )
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce8f1")),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#8da2b3")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(table)
        if title.startswith("3."):
            paragraphs = paragraphs
        for heading, text in paragraphs:
            story.append(Paragraph(heading, styles["SubsectionAAT"]))
            story.append(Paragraph(text, styles["BodyAAT"]))
            if heading.startswith("3.3"):
                story.append(_make_pipeline_table(True, page_width, styles))
            if heading.startswith("4.4"):
                image_path = root / "outputs" / "eda.png"
                if image_path.exists():
                    story.append(Spacer(1, 4))
                    story.append(Image(str(image_path), width=page_width * 0.78, height=page_width * 0.78 * 0.61))
                    story.append(Paragraph("Figure 1. Daily average prices and median price by UTC hour.", styles["SmallAAT"]))
            if heading.startswith("5.3"):
                story.append(Preformatted(SARIMA_CODE, styles["CodeAAT"]))
            if heading.startswith("5.4"):
                story.append(_make_comparison_table(content, page_width, styles))
                image_path = root / "outputs" / "forecast_comparison.png"
                if image_path.exists():
                    story.append(Image(str(image_path), width=page_width, height=page_width * 0.43))
                    story.append(Paragraph("Figure 2. Forecasts and nominal 80% prediction intervals over the final seven test days.", styles["SmallAAT"]))
            if heading.startswith("6.3"):
                story.append(Preformatted(QUANTILE_CODE, styles["CodeAAT"]))
            if heading.startswith("6.5"):
                story.append(_make_comparison_table(content, page_width, styles))
            if heading.startswith("7.2"):
                story.append(_make_comparison_table(content, page_width, styles))
                story.append(_make_pinball_table(content, page_width, styles))

    story.append(Paragraph("9. REFERENCES", styles["SectionAAT"]))
    story.extend(
        Paragraph(f"[{index}] {reference}", styles["SmallAAT"])
        for index, reference in enumerate(REFERENCES, 1)
    )
    story.append(Paragraph("10. TEAM CONTRIBUTION", styles["SectionAAT"]))
    story.append(
        Paragraph(
            "Member 1: [Student name / USN] - dataset preparation and validation. "
            "Member 2: [Student name / USN] - literature review and research gap. "
            "Member 3: [Student name / USN] - SARIMA-GARCH and quantile model implementation. "
            "Member 4: [Student name / USN] - evaluation, visualizations, and report. "
            "Replace the placeholders with the actual team members and actual work; "
            "remove unused rows or add rows as needed.",
            styles["BodyAAT"],
        )
    )

    def page_footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#627384"))
        canvas.drawString(0.5 * inch, 0.33 * inch, "Time Series Analysis (24AM7PCTSA) - Lab AAT")
        canvas.drawRightString(letter[0] - 0.5 * inch, 0.33 * inch, f"Page {document.page}")
        canvas.restoreState()

    SimpleDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=TITLE,
        author="Student submission",
    ).build(story, onFirstPage=page_footer, onLaterPages=page_footer)


def _make_comparison_table(content: dict[str, Any], width: float, styles: dict[str, Any]) -> Table:
    rows = [
        [Paragraph(f"<b>{cell.replace(chr(10), '<br/>')}</b>", styles["SmallAAT"]) for cell in row]
        for row in _comparison_rows(content)
    ]
    table = Table(
        rows,
        colWidths=[width * fraction for fraction in (0.2, 0.105, 0.11, 0.09, 0.12, 0.13, 0.12, 0.125)],
        repeatRows=1,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce8f1")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#8da2b3")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _make_pinball_table(content: dict[str, Any], width: float, styles: dict[str, Any]) -> Table:
    rows = [
        ["Model", "10th-percentile pinball loss", "90th-percentile pinball loss"],
        *[
            [
                content["names"][model],
                f"{content['metrics'][model]['pinball_10']:.2f}",
                f"{content['metrics'][model]['pinball_90']:.2f}",
            ]
            for model in ("sarima_garch", "quantile_boosting")
        ],
    ]
    table = Table(
        [[Paragraph(f"<b>{cell}</b>" if index == 0 else cell, styles["SmallAAT"]) for index, cell in enumerate(row)] for row in rows],
        colWidths=[width * 0.45, width * 0.275, width * 0.275],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce8f1")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#8da2b3")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _shade_cell(cell: Any, fill: str = "DCE8F1") -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shading)


def _add_docx_table(document: Document, headers: list[str], rows: list[list[str]], font_size: float = 7) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True
    for cell, header in zip(table.rows[0].cells, headers):
        cell.text = header
        _shade_cell(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(font_size)
    for values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, values):
            cell.text = value
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                for run in paragraph.runs:
                    run.font.size = Pt(font_size)


def _add_docx_code(document: Document, code: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.left_indent = Inches(0.15)
    paragraph.paragraph_format.right_indent = Inches(0.15)
    paragraph.paragraph_format.space_after = Pt(5)
    run = paragraph.add_run(code)
    run.font.name = "Courier New"
    run.font.size = Pt(7.5)


def _make_docx(content: dict[str, Any], output: Path, root: Path) -> None:
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.62)
    section.bottom_margin = Inches(0.62)
    section.left_margin = Inches(0.68)
    section.right_margin = Inches(0.68)
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(9)
    normal.paragraph_format.space_after = Pt(5)
    for style_name, size, color in (
        ("Heading 1", 15, "183B5B"),
        ("Heading 2", 10.5, "285A82"),
    ):
        style = document.styles[style_name]
        style.font.name = "Arial"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)

    cover = document.add_paragraph()
    cover.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading = cover.add_run(
        "B. M. S. COLLEGE OF ENGINEERING\n"
        "Autonomous Institute, Affiliated to VTU, Belagavi\n"
        "DEPARTMENT OF MACHINE LEARNING\n"
        "Program: B.E. in Artificial Intelligence and Machine Learning\n"
        "Academic Year: 2026-27 | Session: July 2026 - December 2026\n\n"
        "Time Series Analysis (24AM7PCTSA)\n"
        "LAB AAT - DOMAIN-BASED TIME SERIES FORECASTING\n\n"
        "AAT REPORT\n"
    )
    heading.bold = True
    heading.font.size = Pt(14)
    heading.font.color.rgb = RGBColor(24, 59, 91)
    title = cover.add_run(TITLE)
    title.bold = True
    title.font.size = Pt(18)
    for line in [
        "\nApplication Domain: Smart City / Energy Systems",
        "SDG addressed: SDG 7 - Affordable and Clean Energy; SDG 13 - Climate Action",
        "\nSubmitted by",
        "Student Name: [Enter student name]",
        "USN: [Enter USN]",
        "Semester & Section: [Enter semester and section]",
        "Student Signature: ___________________________________",
        "\nValuation Report (to be filled by faculty)",
        "Score: __________   Faculty In-charge: ______________________________",
        "Comments: ______________________________________________________",
        "Faculty Signature with date: ____________________________________",
    ]:
        paragraph = document.add_paragraph(line)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    document.add_page_break()
    document.add_heading("TABLE OF CONTENTS", level=1)
    for item in CONTENTS:
        document.add_paragraph(item)
    document.add_page_break()
    document.add_heading("1. ABSTRACT", level=1)
    document.add_paragraph(content["abstract"])

    for title_text, paragraphs in _section_content(content):
        document.add_heading(title_text, level=1)
        if title_text.startswith("3."):
            document.add_heading("3.1 Review of Existing Research", level=2)
            _add_docx_table(
                document,
                [
                    "Problem / Dataset",
                    "Method Used",
                    "Evaluation Measures",
                    "Key Findings",
                    "Limitations",
                    "Link of the paper",
                ],
                PAPERS,
                font_size=6.5,
            )
        for heading, text in paragraphs:
            document.add_heading(heading, level=2)
            document.add_paragraph(text)
            if heading.startswith("3.3"):
                diagram = document.add_table(rows=1, cols=11)
                diagram.style = "Table Grid"
                labels = [
                    "Public DE-LU\nprices", "->", "Hourly UTC\ncleaning", "->",
                    "180-day initial\ntraining", "->", "Rolling 24-hour\nforecasts", "->",
                    "SARIMA-GARCH\nvs. quantile GB", "->", "Error and interval\nevaluation",
                ]
                for cell, label in zip(diagram.rows[0].cells, labels):
                    cell.text = label
                    for paragraph in cell.paragraphs:
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        for run in paragraph.runs:
                            run.font.size = Pt(7)
            if heading.startswith("4.4"):
                image_path = root / "outputs" / "eda.png"
                if image_path.exists():
                    document.add_picture(str(image_path), width=Inches(6.3))
                    document.add_paragraph(
                        "Figure 1. Daily average prices and median price by UTC hour."
                    )
            if heading.startswith("5.3"):
                _add_docx_code(document, SARIMA_CODE)
            if heading.startswith("5.4"):
                document.add_paragraph("Baseline results and model comparison:")
                _add_docx_table(document, _comparison_rows(content)[0], _comparison_rows(content)[1:], font_size=7)
                image_path = root / "outputs" / "forecast_comparison.png"
                if image_path.exists():
                    document.add_picture(str(image_path), width=Inches(6.4))
                    document.add_paragraph(
                        "Figure 2. Forecasts and nominal 80% prediction intervals over the final seven test days."
                    )
            if heading.startswith("6.3"):
                _add_docx_code(document, QUANTILE_CODE)
            if heading.startswith("6.5") or heading.startswith("7.2"):
                _add_docx_table(document, _comparison_rows(content)[0], _comparison_rows(content)[1:], font_size=7)
                if heading.startswith("7.2"):
                    pinball = [
                        ["Model", "10th-percentile pinball loss", "90th-percentile pinball loss"],
                        *[
                            [
                                content["names"][model],
                                f"{content['metrics'][model]['pinball_10']:.2f}",
                                f"{content['metrics'][model]['pinball_90']:.2f}",
                            ]
                            for model in ("sarima_garch", "quantile_boosting")
                        ],
                    ]
                    _add_docx_table(document, pinball[0], pinball[1:], font_size=7)

    document.add_heading("9. REFERENCES", level=1)
    for index, reference in enumerate(REFERENCES, 1):
        paragraph = document.add_paragraph(f"[{index}] {reference}")
        paragraph.paragraph_format.space_after = Pt(3)
        for run in paragraph.runs:
            run.font.size = Pt(8)
    document.add_heading("10. TEAM CONTRIBUTION", level=1)
    document.add_paragraph(
        "Member 1: [Student name / USN] - dataset preparation and validation. "
        "Member 2: [Student name / USN] - literature review and research gap. "
        "Member 3: [Student name / USN] - SARIMA-GARCH and quantile model implementation. "
        "Member 4: [Student name / USN] - evaluation, visualizations, and report. "
        "Replace the placeholders with the actual team members and actual work; "
        "remove unused rows or add rows as needed."
    )
    document.save(output)


def build_report(
    prices_path: str | Path,
    forecasts_path: str | Path,
    metrics_path: str | Path,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """Generate an editable DOCX and a PDF containing every template section."""
    root = Path(__file__).resolve().parents[1]
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    content = _report_content(Path(prices_path), Path(forecasts_path), Path(metrics_path))
    pdf_path = destination / "TSA_AAT_Report.pdf"
    docx_path = destination / "TSA_AAT_Report.docx"
    _make_pdf(content, pdf_path, root)
    _make_docx(content, docx_path, root)
    return pdf_path, docx_path
