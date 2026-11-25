#!/usr/bin/env python3

import time
import csv
import os
from datetime import datetime

import board
import adafruit_sht31d


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

INTERVAL = 60  # Seconds between measurements

OUTPUT_DIR = os.path.expanduser("/mnt/ssd/testing/sht31-test")
os.makedirs(OUTPUT_DIR, exist_ok=True)

START_TIME = datetime.now().strftime("%Y%m%d_%H%M%S")

CSV_FILE = os.path.join(
    OUTPUT_DIR,
    f"sht31_test_{START_TIME}.csv"
)

SENSORS = {
    "Ambient": 0x44,
    "FLIR": 0x45
}


# --------------------------------------------------
# INITIALIZE SENSORS
# --------------------------------------------------

print("\nInitializing SHT31 sensors...")

i2c = board.I2C()

initialized_sensors = {}

for name, address in SENSORS.items():

    try:
        sensor = adafruit_sht31d.SHT31D(
            i2c,
            address=address
        )

        initialized_sensors[name] = sensor

        print(f"[OK] {name} initialized at 0x{address:02X}")

    except Exception as e:

        initialized_sensors[name] = None

        print(f"[WARNING] {name} initialization failed: {e}")


# --------------------------------------------------
# CREATE CSV
# --------------------------------------------------

with open(CSV_FILE, "w", newline="") as f:

    writer = csv.writer(f)

    writer.writerow([
        "timestamp",
        "ambient_temp_C",
        "ambient_RH_percent",
        "flir_temp_C",
        "flir_RH_percent",
        "status"
    ])


# --------------------------------------------------
# DATA COLLECTION
# --------------------------------------------------

print("\n----------------------------------------")
print("SHT31 TEST LOGGER")
print("----------------------------------------")
print(f"Sampling interval: {INTERVAL} seconds")
print(f"Output file: {CSV_FILE}")
print("Press CTRL+C to stop.\n")


try:

    while True:

        timestamp = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )

        readings = {
            "Ambient": [None, None],
            "FLIR": [None, None]
        }

        status = []

        for name, sensor in initialized_sensors.items():

            if sensor is None:
                status.append(f"{name}: NOT INITIALIZED")
                continue

            try:

                temperature = sensor.temperature
                humidity = sensor.relative_humidity

                readings[name] = [
                    round(temperature, 2),
                    round(humidity, 2)
                ]

            except Exception as e:

                status.append(f"{name}: ERROR - {e}")

        # Prepare output row

        row = [
            timestamp,
            readings["Ambient"][0],
            readings["Ambient"][1],
            readings["FLIR"][0],
            readings["FLIR"][1],
            "; ".join(status) if status else "OK"
        ]

        # Append to CSV

        with open(CSV_FILE, "a", newline="") as f:

            writer = csv.writer(f)
            writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

        # Print readings

        print(f"\n{timestamp}")

        for name in SENSORS:

            temp, rh = readings[name]

            if temp is not None:

                print(
                    f"{name}: "
                    f"{temp:.2f} °C | "
                    f"{rh:.2f} % RH"
                )

            else:

                print(f"{name}: NO READING")

        if status:
            print("Warnings:", "; ".join(status))

        print(f"Saved: {CSV_FILE}")

        # Wait until next measurement

        time.sleep(INTERVAL)


except KeyboardInterrupt:

    print("\n\nTesting stopped by user.")

finally:

    print("SHT31 test logger terminated.")
    print(f"Data saved to: {CSV_FILE}")
