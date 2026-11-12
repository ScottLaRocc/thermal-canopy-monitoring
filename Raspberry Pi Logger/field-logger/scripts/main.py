import os
import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import sht31
import phytos31
import flir


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

BASE_DIR = "/mnt/ssd/field-logger"

ENVIRONMENTAL_DIR = os.path.join(
    BASE_DIR,
    "environmental"
)

FLIR_DIR = os.path.join(
    BASE_DIR,
    "flir"
)

LOCAL_TIMEZONE = ZoneInfo("America/Lima")


# Create storage directories
os.makedirs(ENVIRONMENTAL_DIR, exist_ok=True)
os.makedirs(FLIR_DIR, exist_ok=True)


# ------------------------------------------------------------------
# Timing
# ------------------------------------------------------------------

def get_next_acquisition_time(now):
    """
    Return the next half-hour acquisition time.
    """

    if now.minute < 30:
        return now.replace(
            minute=30,
            second=0,
            microsecond=0
        )

    return (
        now.replace(
            minute=0,
            second=0,
            microsecond=0
        )
        + timedelta(hours=1)
    )

# ------------------------------------------------------------------
	# Acquisition
# ------------------------------------------------------------------

def acquire():
    """
    Perform one complete acquisition cycle.
    """

    observation_time = datetime.now(LOCAL_TIMEZONE)

    observation_id = observation_time.strftime(
        "%Y%m%d_%H%M%S"
    )

    print()
    print("=" * 60)
    print(
        f"Starting acquisition: "
        f"{observation_time.isoformat()}"
    )
    print("=" * 60)

    # --------------------------------------------------------------
    # Start observation record
    # --------------------------------------------------------------

    record = {
        "observation_id": observation_id,
        "timestamp": observation_time.isoformat(),
    }

    # --------------------------------------------------------------
    # SHT31
    # --------------------------------------------------------------

    try:
        print("Reading SHT31...")

        record.update(
            sht31.read_sht31()
        )

        print("  SHT31 complete.")

    except Exception as e:
        print(f"  SHT31 ERROR: {e}")

        record["sht31_error"] = str(e)

    # --------------------------------------------------------------
    # PHYTOS 31
    # --------------------------------------------------------------

    try:
        print("Reading PHYTOS 31...")

        record.update(
            phytos31.read_phytos31()
        )

        print("  PHYTOS 31 complete.")

    except Exception as e:
        print(f"  PHYTOS 31 ERROR: {e}")

        record["phytos31_error"] = str(e)

    # --------------------------------------------------------------
    # FLIR
    # --------------------------------------------------------------

    try:
        print("Capturing FLIR...")

        flir_data = flir.capture_flir(
            FLIR_DIR
        )

        record.update(flir_data)

        print("  FLIR complete.")

    except Exception as e:
        print(f"  FLIR ERROR: {e}")

        record["flir_error"] = str(e)

    # --------------------------------------------------------------
    # Save environmental data
    # --------------------------------------------------------------

    environmental_filename = (
        f"environmental_{observation_id}.json"
    )

    environmental_path = os.path.join(
        ENVIRONMENTAL_DIR,
        environmental_filename
    )

    with open(environmental_path, "w") as f:
        json.dump(
            record,
            f,
            indent=4
        )

    print()
    print(f"Saved environmental data:")
    print(environmental_path)

    return record


# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------

def main():

    print("Field logger starting...")
    print(f"Base directory: {BASE_DIR}")
    print(f"Environmental data: {ENVIRONMENTAL_DIR}")
    print(f"FLIR data: {FLIR_DIR}")
    print("Acquisition interval: 30 minutes")

    while True:

        now = datetime.now(LOCAL_TIMEZONE)

        next_acquisition = get_next_acquisition_time(
            now
        )

        wait_seconds = (
            next_acquisition - now
        ).total_seconds()

        print()
        print(
            f"Next acquisition: "
            f"{next_acquisition.isoformat()}"
        )

        print(
            f"Waiting {wait_seconds:.0f} seconds..."
        )

        time.sleep(wait_seconds)

        try:
            acquire()

        except Exception as e:
            print(
                f"Unexpected acquisition error: {e}"
            )


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    main()
