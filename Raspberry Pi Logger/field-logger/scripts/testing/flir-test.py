#!/usr/bin/env python3

import os
import sys
import json
import math
from datetime import datetime
from zoneinfo import ZoneInfo

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

LOCAL_TIMEZONE = ZoneInfo("America/Lima")

BASE_DIR = "/mnt/ssd/testing/flir-test"

FLIR_DIR = os.path.join(BASE_DIR, "flir")
ENVIRONMENTAL_DIR = os.path.join(BASE_DIR, "environmental")

# Add parent directory to Python path to import existing modules
SCRIPT_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, SCRIPT_DIR)


# ------------------------------------------------------------
# Verify SSD
# ------------------------------------------------------------

def verify_storage():

    if not os.path.ismount("/mnt/ssd"):
        raise RuntimeError(
            "SSD is not mounted at /mnt/ssd. Aborting."
        )

    print("SSD mount verified.")

    os.makedirs(FLIR_DIR, exist_ok=True)
    os.makedirs(ENVIRONMENTAL_DIR, exist_ok=True)


# ------------------------------------------------------------
# Get reference temperature
# ------------------------------------------------------------

def get_bath_reference_temperature():

    while True:

        value = input(
            "\nEnter water bath reference temperature (°C): "
        ).strip()

        try:
            temperature = float(value)

            if not math.isfinite(temperature):
                raise ValueError

            return temperature

        except ValueError:

            print(
                "Invalid temperature. Please enter a numeric value "
                "(e.g., 25, 35.5, or 40)."
            )


# ------------------------------------------------------------
# Main acquisition
# ------------------------------------------------------------

def acquire():

    # Verify storage before initializing sensors
    verify_storage()

    # Get water bath reference temperature
    bath_temperature = get_bath_reference_temperature()

    # Import existing acquisition modules
    import sht31
    import phytos31
    import flir

    # Generate observation timestamp
    now = datetime.now(LOCAL_TIMEZONE)

    observation_id = now.strftime("%Y%m%d_%H%M%S")
    timestamp_iso = now.isoformat()

    print()
    print("=" * 55)
    print("FLIR AND ENVIRONMENTAL SENSOR TEST")
    print("=" * 55)
    print(f"Observation: {observation_id}")
    print()

    # Initialize environmental record
    record = {
        "observation_id": observation_id,
        "timestamp": timestamp_iso,
        "test_mode": True,

        # Water bath reference
        "bath_reference_temperature_c": bath_temperature,
    }

    # --------------------------------------------------------
    # SHT31
    # --------------------------------------------------------

    print("Reading SHT31...")

    try:

        sht_data = sht31.read_sht31()

        record.update(sht_data)

        if all(v is not None for v in sht_data.values()):
            record["sht31_status"] = "success"
            print("  SHT31: SUCCESS")
        else:
            record["sht31_status"] = "partial_or_failed"
            print("  SHT31: PARTIAL / FAILED")

    except Exception as e:

        record["sht31_status"] = "error"
        record["sht31_error"] = str(e)

        print(f"  SHT31 ERROR: {e}")

    # --------------------------------------------------------
    # PHYTOS31
    # --------------------------------------------------------

    print()
    print("Reading PHYTOS31...")

    try:

        phytos_data = phytos31.read_phytos31()

        record.update(phytos_data)

        if phytos_data.get("phytos31_voltage_mv") is not None:
            record["phytos31_status"] = "success"
            print(
                f"  PHYTOS31: SUCCESS "
                f"({phytos_data['phytos31_voltage_mv']:.2f} mV)"
            )
        else:
            record["phytos31_status"] = "failed"
            print("  PHYTOS31: FAILED")

    except Exception as e:

        record["phytos31_status"] = "error"
        record["phytos31_error"] = str(e)

        print(f"  PHYTOS31 ERROR: {e}")

    # --------------------------------------------------------
    # FLIR
    # --------------------------------------------------------

    print()
    print("Capturing FLIR...")

    try:

        flir_data = flir.capture_flir(FLIR_DIR)

        record.update(flir_data)

        record["flir_status"] = "success"

        print("  FLIR: SUCCESS")
        print(f"  Image: {flir_data['flir_filename']}")
        print(f"  Metadata: {flir_data['flir_metadata_filename']}")

    except Exception as e:

        record["flir_status"] = "error"
        record["flir_error"] = str(e)

        print(f"  FLIR ERROR: {e}")

    # --------------------------------------------------------
    # Save environmental record
    # --------------------------------------------------------

    environmental_filename = (
        f"environmental_{observation_id}.json"
    )

    environmental_path = os.path.join(
        ENVIRONMENTAL_DIR,
        environmental_filename
    )

    # Write temporary file, then atomically rename
    temporary_path = environmental_path + ".tmp"

    try:

        with open(temporary_path, "w") as f:
            json.dump(record, f, indent=4)

        os.replace(temporary_path, environmental_path)

        print()
        print("Environmental record saved:")
        print(environmental_path)

    except Exception as e:

        print(f"ERROR SAVING ENVIRONMENTAL JSON: {e}")

        if os.path.exists(temporary_path):
            os.remove(temporary_path)

        raise

    # --------------------------------------------------------
    # Acquisition summary
    # --------------------------------------------------------

    print()
    print("=" * 55)
    print("ACQUISITION SUMMARY")
    print(f"Bath reference: {record['bath_reference_temperature_c']:.2f} °C")    
    print("=" * 55)

    print(f"SHT31:      {record.get('sht31_status')}")
    print(f"PHYTOS31:   {record.get('phytos31_status')}")
    print(f"FLIR:       {record.get('flir_status')}")

    print()
    print("Test acquisition complete.")
    print("=" * 55)


# ------------------------------------------------------------
# Entry point
# ------------------------------------------------------------

if __name__ == "__main__":

    try:
        acquire()

    except Exception as e:

        print()
        print(f"TEST SCRIPT FAILED: {e}")
        sys.exit(1)
