#!/usr/bin/env python3
"""
FLIR radiometric (IRFormat = Radiometric, Mono16) raw counts -> temperature (degC)
for CALIBRATION: emissivity = 1, distance = 0.

With emissivity = 1 there is no reflected term, and with distance = 0 the
atmospheric transmission is 1, so air temperature, RH and reflected temperature
have no effect. What remains:

    S_meas = t_w * S(T) + (1 - t_w) * S(T_win)       (window optional)
    S      = (raw - J0) / J1
    S(T)   = R / (exp(B / T) - F),   T(S) = B / ln(R / S + F)    T in kelvin

Without a window (default, --window-transmission 1) this is the plain
blackbody / apparent temperature from the camera's own calibration constants.

If the camera views the reference through its enclosure window, pass
--window-transmission and --t-window. The window is assumed to have zero
reflectance and emissivity 1 - t_w.

Optional --roi x y w h (pixels, repeatable) reports mean / std / min / max
temperature in each region and writes a CSV summary across all images, for
comparison with your reference (blackbody, thermocouple, etc.).
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import tifffile

KELVIN = 273.15
REQUIRED_CAL = ["R", "B", "F", "J0", "J1"]


# ------------------------------------------------------------------
# Physics (same functions the full script will use)
# ------------------------------------------------------------------

def planck_signal(temp_k, R, B, F):
    """Normalised signal produced by a blackbody at temp_k (kelvin)."""
    return R / (np.exp(B / temp_k) - F)


def planck_temperature(signal, R, B, F):
    """Inverse of planck_signal. Returns kelvin; NaN where signal <= 0."""
    signal = np.asarray(signal, dtype=np.float64)
    out = np.full(signal.shape, np.nan)
    ok = signal > 0
    out[ok] = B / np.log(R / signal[ok] + F)
    return out


def raw_to_temperature_calibration(raw, cal, window_transmission=1.0, t_window_k=None):
    """
    Raw counts -> temperature in degC, assuming emissivity = 1 and distance = 0.
    Invalid pixels (raw == 0, or signal <= 0 after window correction) are NaN.
    """
    R, B, F = cal["R"], cal["B"], cal["F"]
    J0, J1 = cal["J0"], cal["J1"]

    s_meas = (raw.astype(np.float64) - J0) / J1

    if window_transmission < 1.0:
        s_win = planck_signal(t_window_k, R, B, F)
        s_obj = (s_meas - (1.0 - window_transmission) * s_win) / window_transmission
    else:
        s_obj = s_meas

    temp_k = planck_temperature(s_obj, R, B, F)
    temp_k[raw == 0] = np.nan
    return (temp_k - KELVIN).astype(np.float32)


# ------------------------------------------------------------------
# ROI statistics
# ------------------------------------------------------------------

def roi_stats(temp_c, raw, roi):
    x, y, w, h = roi
    t = temp_c[y:y + h, x:x + w]
    r = raw[y:y + h, x:x + w]
    valid = ~np.isnan(t)
    n = int(valid.sum())
    if n == 0:
        return {"roi": roi, "n_valid": 0}
    return {
        "roi": roi,
        "n_valid": n,
        "mean_c": float(np.nanmean(t)),
        "std_c": float(np.nanstd(t)),
        "min_c": float(np.nanmin(t)),
        "max_c": float(np.nanmax(t)),
        "raw_mean": float(r[valid].mean()),
    }


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    ap.add_argument(
        "--raw-dir",
        type=Path,
        required=True,
        help="Directory containing raw FLIR TIFFs and corresponding JSON metadata."
    )

    ap.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Directory where processed TIFFs, JSONs, and CSV summary will be saved."
    )

    ap.add_argument(
        "--window-transmission",
        type=float,
        default=1.0,
        help="Enclosure window transmission (0-1). Default 1 = no window."
    )

    ap.add_argument(
        "--t-window",
        type=float,
        help="Window temperature, degC. Required if window transmission < 1."
    )

    ap.add_argument(
        "--roi",
        type=int,
        nargs=4,
        action="append",
        metavar=("X", "Y", "W", "H"),
        help="Region of interest in pixels; may be given several times."
    )

    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)

    t_w = args.window_transmission
    if not 0 < t_w <= 1:
        ap.error("--window-transmission must be in (0, 1].")
    t_window_k = None
    if t_w < 1:
        if args.t_window is None:
            ap.error("--t-window is required when --window-transmission < 1.")
        t_window_k = args.t_window + KELVIN

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rois = [tuple(r) for r in (args.roi or [])]

    tiffs = sorted(list(args.raw_dir.glob("*.tiff")) + list(args.raw_dir.glob("*.tif")))
    if not tiffs:
        print(f"No TIFFs found in {args.raw_dir}")
        return 1

    summary_rows = []

    for tiff_path in tiffs:
        json_path = tiff_path.with_suffix(".json")
        if not json_path.exists():
            print(f"Skipping {tiff_path.name}: no JSON found.")
            continue

        with open(json_path) as f:
            meta = json.load(f)

        missing = [k for k in REQUIRED_CAL if meta.get(k) is None]
        if missing:
            print(f"Skipping {tiff_path.name}: missing calibration {missing}")
            continue

        raw = tifffile.imread(tiff_path)
        if raw.dtype != np.uint16 or raw.ndim != 2:
            print(f"Skipping {tiff_path.name}: expected 2-D uint16, got {raw.dtype} {raw.shape}")
            continue

        bad_roi = [r for r in rois
                   if r[0] < 0 or r[1] < 0 or r[2] <= 0 or r[3] <= 0
                   or r[0] + r[2] > raw.shape[1] or r[1] + r[3] > raw.shape[0]]
        if bad_roi:
            print(f"Error: ROI {bad_roi} outside image {raw.shape[1]}x{raw.shape[0]}.")
            return 1

        temp_c = raw_to_temperature_calibration(raw, meta, t_w, t_window_k)

        stats = [roi_stats(temp_c, raw, r) for r in rois]
        record = {
            "source_tiff": tiff_path.name,
            "source_timestamp": meta.get("timestamp"),
            "units": "degC",
            "mode": "calibration",
            "parameters": {
                "emissivity": 1.0,
                "distance_m": 0.0,
                "window_transmission": t_w,
                "t_window_k": t_window_k,
            },
            "calibration_constants": {k: meta[k] for k in REQUIRED_CAL},
            "invalid_pixels": int(np.isnan(temp_c).sum()),
            "frame_median_c": float(np.nanmedian(temp_c)),
            "roi_stats": stats,
        }

        out_path = args.out_dir / tiff_path.name
        tifffile.imwrite(out_path, temp_c, metadata=None, description=json.dumps(record))
        with open(out_path.with_suffix(".json"), "w") as f:
            json.dump(record, f, indent=4)

        line = f"{tiff_path.name}: frame median {record['frame_median_c']:.2f} C"
        for i, s in enumerate(stats):
            if s["n_valid"]:
                line += f" | ROI{i} {s['mean_c']:.2f} ± {s['std_c']:.2f} C"
            else:
                line += f" | ROI{i} no valid pixels"
            summary_rows.append({
                "image": tiff_path.name,
                "timestamp": meta.get("timestamp"),
                "roi_index": i,
                "x": s["roi"][0], "y": s["roi"][1], "w": s["roi"][2], "h": s["roi"][3],
                "n_valid": s["n_valid"],
                "mean_c": s.get("mean_c"), "std_c": s.get("std_c"),
                "min_c": s.get("min_c"), "max_c": s.get("max_c"),
                "raw_mean": s.get("raw_mean"),
            })
        print(line)

    if summary_rows:
        csv_path = args.out_dir / "calibration_summary.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)
        print(f"ROI summary: {csv_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
