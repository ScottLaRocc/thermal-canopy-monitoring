import board
import busio
import logging
import csv
import time
from datetime import datetime
from pathlib import Path

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

INTERVAL_SECONDS = 1

OUTPUT_DIR = Path("/mnt/ssd/testing/phytos31-test")
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / (
    f"phytos31_test_{datetime.now():%Y%m%d_%H%M%S}.csv"
)


# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Initialize I2C and ADS1115
# ------------------------------------------------------------------

try:
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c)
    phytos31 = AnalogIn(ads, 0)

    print("PHYTOS 31 initialized successfully.")

except Exception as e:
    logger.error("PHYTOS 31 initialization failed: %s", e)
    raise SystemExit(1)


# ------------------------------------------------------------------
# Read sensor
# ------------------------------------------------------------------

def read_phytos31():

    try:
        voltage_mv = phytos31.voltage * 1000

        return voltage_mv

    except Exception as e:
        logger.warning("PHYTOS 31 read failed: %s", e)
        return None


# ------------------------------------------------------------------
# Main logging loop
# ------------------------------------------------------------------

def main():

    print("\nStarting PHYTOS 31 test logger")
    print(f"Logging interval: {INTERVAL_SECONDS} seconds")
    print(f"Output file: {OUTPUT_FILE}")
    print("Press Ctrl+C to stop.\n")

    with open(OUTPUT_FILE, "w", newline="") as csvfile:

        writer = csv.writer(csvfile)

        # CSV header
        writer.writerow([
            "timestamp",
            "phytos31_voltage_mv"
        ])

        try:

            while True:

                timestamp = datetime.now().isoformat(
                    sep=" ",
                    timespec="seconds"
                )

                voltage_mv = read_phytos31()

                # Print to CLI
                if voltage_mv is not None:
                    print(
                        f"{timestamp} | "
                        f"PHYTOS 31: {voltage_mv:.2f} mV"
                    )
                else:
                    print(
                        f"{timestamp} | "
                        "PHYTOS 31: unavailable"
                    )

                # Write to CSV
                writer.writerow([
                    timestamp,
                    voltage_mv
                ])

                # Ensure data is written immediately
                csvfile.flush()

                # Wait until next measurement
                time.sleep(INTERVAL_SECONDS)

        except KeyboardInterrupt:

            print("\n\nPHYTOS 31 test interrupted.")
            print(f"Data saved to: {OUTPUT_FILE}")
            print("Logger stopped successfully.")


# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------

if __name__ == "__main__":
    main()
