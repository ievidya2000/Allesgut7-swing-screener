import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict

from screener_v2.performance.journal import init_db, get_trade_results, get_all_predictions


def parse_probability(prob_str):
    if prob_str is None:
        return None
    if isinstance(prob_str, (int, float)):
        return float(prob_str)
    try:
        return float(str(prob_str).replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def calibration_analysis(n_bins=10):
    init_db()
    trades = get_trade_results()
    predictions = get_all_predictions(filters={"status": "CLOSED"})

    pred_map = {p["id"]: p for p in predictions}

    bins_data = defaultdict(lambda: {"predicted": [], "actual": []})

    for trade in trades:
        pred_id = trade.get("prediction_id")
        if pred_id not in pred_map:
            continue

        pred = pred_map[pred_id]
        prob_tp1 = parse_probability(pred.get("prob_tp1"))
        if prob_tp1 is None:
            continue

        actual_hit = 1 if trade.get("hit_tp1") else 0
        bin_idx = min(int(prob_tp1 / (100 / n_bins)), n_bins - 1)
        bin_label = f"{bin_idx * 100 // n_bins}-{(bin_idx + 1) * 100 // n_bins}%"

        bins_data[bin_label]["predicted"].append(prob_tp1)
        bins_data[bin_label]["actual"].append(actual_hit)

    results = {}
    for bin_label in sorted(bins_data.keys()):
        data = bins_data[bin_label]
        avg_predicted = np.mean(data["predicted"]) if data["predicted"] else 0
        actual_rate = np.mean(data["actual"]) if data["actual"] else 0
        count = len(data["actual"])

        results[bin_label] = {
            "avg_predicted": round(avg_predicted, 2),
            "actual_hit_rate": round(actual_rate * 100, 2),
            "count": count,
            "gap": round(abs(avg_predicted - actual_rate * 100), 2),
        }

    return results


def brier_score(trades, predictions):
    pred_map = {p["id"]: p for p in predictions}
    scores = []

    for trade in trades:
        pred_id = trade.get("prediction_id")
        if pred_id not in pred_map:
            continue

        pred = pred_map[pred_id]
        prob_tp1 = parse_probability(pred.get("prob_tp1"))
        if prob_tp1 is None:
            continue

        actual = 1 if trade.get("hit_tp1") else 0
        predicted = prob_tp1 / 100

        scores.append((predicted - actual) ** 2)

    return np.mean(scores) if scores else None


def expected_calibration_error(calibration_bins, n_bins=10):
    total_count = sum(b["count"] for b in calibration_bins.values())
    if total_count == 0:
        return None

    ece = 0
    for bin_label, data in calibration_bins.items():
        weight = data["count"] / total_count
        gap = abs(data["avg_predicted"] - data["actual_hit_rate"])
        ece += weight * gap

    return round(ece, 4)


def maximum_calibration_error(calibration_bins):
    if not calibration_bins:
        return None
    return max(b["gap"] for b in calibration_bins.values())


def plot_reliability_diagram(save_path=None):
    bins_data = calibration_analysis(n_bins=10)

    if not bins_data:
        print("  No data available for calibration plot")
        return

    predicted = [v["avg_predicted"] for v in bins_data.values()]
    actual = [v["actual_hit_rate"] for v in bins_data.values()]
    counts = [v["count"] for v in bins_data.values()]
    bin_labels = list(bins_data.keys())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    ax1.plot([0, 100], [0, 100], "k--", alpha=0.5, label="Perfect calibration")
    scatter = ax1.scatter(predicted, actual, c=counts, cmap="viridis", s=100, edgecolors="black")
    ax1.set_xlabel("Predicted Probability (%)")
    ax1.set_ylabel("Actual Hit Rate (%)")
    ax1.set_title("Reliability Diagram")
    ax1.legend()
    plt.colorbar(scatter, ax=ax1, label="Sample Count")

    ax2.bar(range(len(bin_labels)), counts, color="steelblue", edgecolor="black")
    ax2.set_xticks(range(len(bin_labels)))
    ax2.set_xticklabels(bin_labels, rotation=45, ha="right")
    ax2.set_xlabel("Probability Bin")
    ax2.set_ylabel("Count")
    ax2.set_title("Prediction Distribution")

    plt.tight_layout()

    if save_path is None:
        save_path = Path(__file__).parent.parent / "calibration_plot.png"

    plt.savefig(str(save_path), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Calibration plot saved: {save_path}")
    return str(save_path)


def print_calibration_report():
    init_db()
    trades = get_trade_results()
    predictions = get_all_predictions(filters={"status": "CLOSED"})

    if not trades:
        print("  No closed trades available for calibration analysis")
        return

    print(f"\n{'='*60}")
    print("  MONTE CARLO CALIBRATION REPORT")
    print(f"{'='*60}\n")

    bins = calibration_analysis()

    print(f"  {'Bin':<12s} {'Predicted':>10s} {'Actual':>10s} {'Gap':>8s} {'Count':>6s}")
    print("  " + "-" * 50)
    for bin_label, data in bins.items():
        print(
            f"  {bin_label:<12s} {data['avg_predicted']:>9.1f}% "
            f"{data['actual_hit_rate']:>9.1f}% {data['gap']:>7.1f}% {data['count']:>6d}"
        )
    print("  " + "-" * 50)

    bs = brier_score(trades, predictions)
    ece = expected_calibration_error(bins)
    mce = maximum_calibration_error(bins)

    print(f"\n  Brier Score           : {bs:.4f}" if bs else "  Brier Score           : N/A")
    print(f"  Expected Calib. Error : {ece:.4f}%" if ece else "  Expected Calib. Error : N/A")
    print(f"  Max Calib. Error      : {mce:.1f}%" if mce else "  Max Calib. Error      : N/A")

    if bs is not None:
        if bs < 0.1:
            rating = "EXCELLENT"
        elif bs < 0.2:
            rating = "GOOD"
        elif bs < 0.3:
            rating = "FAIR"
        else:
            rating = "POOR"
        print(f"  Calibration Rating    : {rating}")

    print(f"\n{'='*60}")
