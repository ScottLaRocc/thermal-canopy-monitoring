#!/usr/bin/env python3

import json
from pathlib import Path

import numpy as np
import tifffile


def raw_to_temperature(raw, metadata):
    """
    Convert FLIR radiometric raw counts to temperature (°C).

    Parameters
    ----------
    raw : ndarray
        Raw Mono16 image.
    metadata : dict
        Metadata loaded from JSON.

    Returns
    -------
    ndarray
        Temperature image in °C (float32).
    """

    R = metadata["R"]
    B = metadata["B"]
    F = metadata["F"]
    J0 = metadata["J0"]
    J1 = metadata["J1"]

    # Convert raw counts to detector signal
    signal = (raw.astype(np.float32) - J0) / J1

    # Prevent divide-by-zero or log issues
    signal = np.maximum(signal, 1e-6)

    # Planck inversion
    temp_k = B / np.log(R / signal + F)

    # Convert to Celsius
    temp_c = temp_k - 273.15

    return temp_c.astype(np.float32)


def main():

    project_dir = Path(__file__).resolve().parent.parent

    raw_dir = project_dir / "images" / "raw"
    processed_dir = project_dir / "images" / "processed"

    processed_dir.mkdir(parents=True, exist_ok=True)

    # Process every TIFF in raw/
    for tiff_path in sorted(raw_dir.glob("*.tiff")):

        json_path = tiff_path.with_suffix(".json")

        if not json_path.exists():
            print(f"Skipping {tiff_path.name}: no JSON found.")
            continue

        print(f"Processing {tiff_path.name}")

        raw = tifffile.imread(tiff_path)

        with open(json_path, "r") as f:
            metadata = json.load(f)

        temp = raw_to_temperature(raw, metadata)

        output_path = processed_dir / tiff_path.name

        tifffile.imwrite(output_path, temp)

        print(f"Saved {output_path.name}")

    print("Done.")


if __name__ == "__main__":
    main()