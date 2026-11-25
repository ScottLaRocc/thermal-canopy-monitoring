#!/usr/bin/env python3

import json
import glob
import os
import csv
import math
import ssl
import smtplib
import argparse
import subprocess
import shutil

from datetime import datetime
from email.message import EmailMessage


# ==================================================
# CONFIGURATION
# ==================================================

ENV_DIRS = [
    "/mnt/ssd/field-logger/environmental",
    "/home/scott/field-logger-backup/environmental"]

LOG_DIR = "/home/scott/pi-monitor/logs"

STATE_FILE = os.path.join(LOG_DIR, "alert_state.json")
CSV_FILE = os.path.join(LOG_DIR, "temperature.csv")

WARNING = {
    "cpu": 70,
    "housing": 40,
    "ambient": 35,
    "humidity": 80
}

CRITICAL = {
    "cpu": 80,
    "housing": 45,
    "ambient": 40,
    "humidity": 90
}

MAX_LOG_AGE_MINUTES = 45
CRITICAL_LOG_AGE_MINUTES = 90

# Storage configuration

SSD_MOUNT = "/mnt/ssd"

SSD_UUID = "9de653ff-dcc1-45b3-b56b-a693568a73a4"

SD_MIN_FREE_GB = 5
SD_MAX_USAGE_GB = 10
SSD_MIN_FREE_GB = 2

os.makedirs(LOG_DIR, exist_ok=True)


# ==================================================
# EMAIL CONFIGURATION
# ==================================================

def send_email(subject, body):

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", 587))
    username = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"].replace(" ", "")

    sender = os.environ["ALERT_FROM"]
    recipient = os.environ["ALERT_TO"]

    message = EmailMessage()

    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient

    message.set_content(body)

    context = ssl.create_default_context()

    with smtplib.SMTP(host, port, timeout=20) as server:

        server.ehlo()
        server.starttls(context=context)
        server.ehlo()

        server.login(username, password)

        server.send_message(message)

    print(f"EMAIL SENT: {subject}")


# ==================================================
# ALERT STATE MANAGEMENT
# ==================================================

def load_state():

    if not os.path.exists(STATE_FILE):

        return {
            "statuses": {},
            "pending_emails": []
        }

    try:

        with open(STATE_FILE, "r") as f:
            return json.load(f)

    except Exception as e:

        print(f"WARNING: Could not load alert state: {e}")

        return {
            "statuses": {},
            "pending_emails": []
        }


def save_state(state):

    temp_file = STATE_FILE + ".tmp"

    with open(temp_file, "w") as f:

        json.dump(state, f, indent=4)

    os.replace(temp_file, STATE_FILE)


def queue_email(state, subject, body):

    state["pending_emails"].append({
        "subject": subject,
        "body": body,
        "created": datetime.now().astimezone().isoformat()
    })


def process_pending_emails(state):

    while state["pending_emails"]:

        email = state["pending_emails"][0]

        try:

            send_email(
                email["subject"],
                email["body"]
            )

            state["pending_emails"].pop(0)

            save_state(state)

        except Exception as e:

            print(f"EMAIL FAILED: {e}")
            print("Email retained for next monitoring cycle.")

            break


# ==================================================
# CPU TEMPERATURE
# ==================================================

def get_cpu_temperature():

    try:

        result = subprocess.check_output(
            ["vcgencmd", "measure_temp"],
            text=True
        )

        return float(
            result.split("=")[1].replace("'C", "")
        )

    except Exception as e:

        print(f"WARNING: Could not read CPU temperature: {e}")

        return None


# ==================================================
# ENVIRONMENTAL DATA
# ==================================================

def get_environmental_data():

    files = []

    for directory in ENV_DIRS:

        files.extend(
            glob.glob(
                os.path.join(directory, "environmental_*.json")
            )
        )

    if not files:

        print("WARNING: No environmental JSON files found.")

        return None

    latest = max(files, key=os.path.getmtime)

    try:

        with open(latest, "r") as f:
            data = json.load(f)

        timestamp = datetime.fromisoformat(
            data["timestamp"]
        )

        age = (
            datetime.now(timestamp.tzinfo) - timestamp
        ).total_seconds() / 60

        data["data_age_minutes"] = max(0, age)

        data["source_file"] = latest

        return data

    except Exception as e:

        print(f"WARNING: Could not read environmental data: {e}")

        return None

# ==================================================
# STORAGE MONITORING
# ==================================================

def get_storage_status(environmental):

    storage = {}

    # Check SSD mount identity

    try:

        result = subprocess.run(
            ["findmnt", "-rn", "-M", SSD_MOUNT, "-o", "UUID"],
            capture_output=True,
            text=True
        )

        mounted_uuid = result.stdout.strip()

        storage["ssd_mounted"] = (
            mounted_uuid == SSD_UUID
        )

    except Exception:

        storage["ssd_mounted"] = False

    # Check SSD available space

    storage["ssd_available_gb"] = None

    if storage["ssd_mounted"]:

        try:

            usage = shutil.disk_usage(SSD_MOUNT)

            storage["ssd_available_gb"] = (
                usage.free / (1024 ** 3)
            )

        except Exception:
            pass

    # Read storage metadata from latest observation

    metadata = {}

    if environmental is not None:

        # Support either nested storage metadata or top-level storage fields.
        metadata = environmental.get("storage") or environmental

    else:

        metadata = {}

    storage["active_device"] = metadata.get("active_device")

    storage["sd_available_gb"] = metadata.get("sd_available_gb")
    storage["sd_used_gb"] = metadata.get("sd_used_gb")

    # Determine storage health

    ssd_healthy = (
        storage["ssd_mounted"]
        and storage["ssd_available_gb"] is not None
        and storage["ssd_available_gb"] >= SSD_MIN_FREE_GB
    )

    sd_healthy = (
        storage["sd_available_gb"] is not None
        and storage["sd_used_gb"] is not None
        and storage["sd_available_gb"] >= SD_MIN_FREE_GB
        and storage["sd_used_gb"] < SD_MAX_USAGE_GB
    )

    storage["ssd_healthy"] = ssd_healthy
    storage["sd_healthy"] = sd_healthy

    # Base the alert on the destination used by the latest acquisition.
    # This avoids reporting fallback until an acquisition confirms SD use.

    if storage["active_device"] == "SD":

        storage["status"] = "WARNING" if sd_healthy else "CRITICAL"

    elif storage["active_device"] == "SSD" and ssd_healthy:

        storage["status"] = "NORMAL"

    else:

        # Missing/uncertain metadata, or SSD disappeared after the latest
        # SSD acquisition: wait for the next acquisition to confirm fallback.
        storage["status"] = "UNKNOWN"

    return storage

# ==================================================
# THRESHOLD EVALUATION
# ==================================================

def evaluate(name, value, warning, critical):

    if value is None:
        return "UNKNOWN"

    if not math.isfinite(float(value)):
        return "UNKNOWN"

    value = float(value)

    if value >= critical:

        print(f"CRITICAL: {name} = {value:.1f}")

        return "CRITICAL"

    elif value >= warning:

        print(f"WARNING: {name} = {value:.1f}")

        return "WARNING"

    return "NORMAL"


# ==================================================
# ALERT GENERATION
# ==================================================

def check_alert(
    state,
    name,
    value,
    status,
    unit,
    alert_message=None,
    recovery_message=None
):

    # Do not overwrite a known alert state when a reading is unavailable.
    if status == "UNKNOWN":
        return

    previous = state["statuses"].get(name, "NORMAL")

    if status == previous:
        return

    state["statuses"][name] = status

    now = datetime.now().astimezone().strftime(
        "%Y-%m-%d %H:%M:%S %Z"
    )

    if status in ("WARNING", "CRITICAL"):

        subject = f"[{status}] Tambopata Field Station: {name}"

        if alert_message is not None:
            details = alert_message
        else:
            details = f"Current measurement: {value:.1f} {unit}"

        body = f"""
TAMBOPATA FIELD STATION

{status}: {name}

{details}

Previous status: {previous}
Current status: {status}

Time: {now}

Device: tmb-pi

Please investigate the field station.
"""

        queue_email(state, subject, body)

    elif status == "NORMAL" and previous in (
        "WARNING",
        "CRITICAL"
    ):

        subject = f"[RECOVERED] Tambopata Field Station: {name}"

        if recovery_message is not None:
            details = recovery_message
        else:
            details = (
                f"{name} has returned to normal.\\n"
                f"Current measurement: {value:.1f} {unit}"
            )

        body = f"""
TAMBOPATA FIELD STATION

RECOVERY NOTIFICATION

{details}

Previous status: {previous}
Current status: NORMAL

Time: {now}

Device: tmb-pi

Monitoring continues.
"""

        queue_email(state, subject, body)


# ==================================================
# MAIN MONITORING
# ==================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--test-email",
        action="store_true",
        help="Send a test email"
    )

    args = parser.parse_args()

    # Test email without running monitoring

    if args.test_email:

        send_email(
            "[TEST] Tambopata Field Station",
            """
This is a test email from the Tambopata Raspberry Pi.

Email notifications are configured successfully.

Device: tmb-pi
"""
        )

        return

    now = datetime.now().astimezone().isoformat()

    state = load_state()

    # Read sensors

    cpu = get_cpu_temperature()

    environmental = get_environmental_data()

    storage = get_storage_status(environmental)

    housing = None
    ambient = None
    humidity = None
    ambient_humidity = None

    age = None

    if environmental is not None:

        housing = environmental.get(
            "sht31_flirhousing_temperature_c"
        )

        ambient = environmental.get(
            "sht31_ambient_temperature_c"
        )

        humidity = environmental.get(
            "sht31_flirhousing_relative_humidity_pct"
        )

        ambient_humidity = environmental.get(
            "sht31_ambient_relative_humidity_pct"
        )

        age = environmental["data_age_minutes"]

    # Display measurements

    print("\n--- TAMBOPATA FIELD STATION ---")

    print(f"Time: {now}")

    print(f"CPU temperature: {cpu} °C")

    print(f"FLIR housing temperature: {housing} °C")

    print(f"Ambient temperature: {ambient} °C")

    print(f"FLIR housing humidity: {humidity} %")

    print(f"Ambient humidity: {ambient_humidity} %")

    print(f"Environmental data age: {age} minutes")

    print(f"Active storage: {storage['active_device']}")

    print(f"SSD mounted: {storage['ssd_mounted']}")

    print(f"SSD available: {storage['ssd_available_gb']} GB")

    print(f"SD available: {storage['sd_available_gb']} GB")

    print(f"SD used: {storage['sd_used_gb']} GB")

    print(f"Storage status: {storage['status']}")

    # Evaluate temperatures

    statuses = {

        "cpu": evaluate(
            "CPU",
            cpu,
            WARNING["cpu"],
            CRITICAL["cpu"]
        ),

        "housing": evaluate(
            "FLIR housing",
            housing,
            WARNING["housing"],
            CRITICAL["housing"]
        ),

        "ambient": evaluate(
            "Ambient temperature",
            ambient,
            WARNING["ambient"],
            CRITICAL["ambient"]
        ),

        "humidity": evaluate(
            "FLIR housing humidity",
            humidity,
            WARNING["humidity"],
            CRITICAL["humidity"]
        ),

        "storage": storage["status"]
    }

    # Environmental data freshness

    if age is None:

        data_status = "CRITICAL"

    elif age >= CRITICAL_LOG_AGE_MINUTES:

        data_status = "CRITICAL"

    elif age >= MAX_LOG_AGE_MINUTES:

        data_status = "WARNING"

    else:

        data_status = "NORMAL"

    if data_status != "NORMAL":

        print(f"WARNING: Environmental data status: {data_status}")

    statuses["environmental_data"] = data_status

    # Record CSV

    write_header = not os.path.exists(CSV_FILE)

    with open(CSV_FILE, "a", newline="") as f:

        writer = csv.writer(f)

        if write_header:

            writer.writerow([
                "timestamp",
                "cpu_temp_c",
                "housing_temp_c",
                "ambient_temp_c",
                "housing_humidity_pct",
                "ambient_humidity_pct",
                "data_age_minutes",
                "cpu_status",
                "housing_status",
                "ambient_status",
                "humidity_status",
                "environmental_data_status",
                "active_storage",
                "ssd_mounted",
                "ssd_available_gb",
                "sd_available_gb",
                "sd_used_gb",
                "storage_status"
            ])

        writer.writerow([
            now,
            cpu,
            housing,
            ambient,
            humidity,
            ambient_humidity,
            age,
            statuses["cpu"],
            statuses["housing"],
            statuses["ambient"],
            statuses["humidity"],
            statuses["environmental_data"],
            storage["active_device"],
            storage["ssd_mounted"],
            storage["ssd_available_gb"],
            storage["sd_available_gb"],
            storage["sd_used_gb"],
            storage["status"]
        ])

    # Generate alerts

    check_alert(
        state,
        "CPU temperature",
        cpu,
        statuses["cpu"],
        "°C"
    )

    check_alert(
        state,
        "FLIR housing temperature",
        housing,
        statuses["housing"],
        "°C"
    )

    check_alert(
        state,
        "Ambient temperature",
        ambient,
        statuses["ambient"],
        "°C"
    )

    check_alert(
        state,
        "FLIR housing humidity",
        humidity,
        statuses["humidity"],
        "%"
    )

    # Environmental data alerts

    if age is None:

        data_alert_message = (
            "No environmental JSON file could be read from either the SSD "
            "or SD fallback directory. The logger may not be saving data."
        )

    else:

        data_alert_message = (
            f"The latest environmental record is {age:.1f} minutes old. "
            f"Warning threshold: {MAX_LOG_AGE_MINUTES} minutes; "
            f"critical threshold: {CRITICAL_LOG_AGE_MINUTES} minutes."
        )

    check_alert(
        state,
        "Environmental data freshness",
        age,
        data_status,
        "minutes old",
        alert_message=data_alert_message
    )

    # Storage alerts
    if statuses["storage"] == "WARNING":

        storage_alert_message = (
            "The SSD is not being used. The latest acquisition reports "
            "that the logger has switched to SD fallback storage. "
            f"SD free space: {storage['sd_available_gb']} GB; "
            f"SD used: {storage['sd_used_gb']} GB. "
            "Data acquisition is continuing on the SD card."
        )

    elif statuses["storage"] == "CRITICAL":

        storage_alert_message = (
            "The logger reports that SD fallback storage is active, "
            "but the SD card does not meet the configured storage limits. "
            f"SD free space: {storage['sd_available_gb']} GB "
            f"(minimum: {SD_MIN_FREE_GB} GB); "
            f"SD used: {storage['sd_used_gb']} GB "
            f"(maximum: {SD_MAX_USAGE_GB} GB). "
            "Data acquisition may be at risk."
        )

    else:

        storage_alert_message = None

    check_alert(
        state,
        "Storage",
        None,
        statuses["storage"],
        "",
        alert_message=storage_alert_message,
        recovery_message=(
            "The latest acquisition confirms that the logger is using "
            "the SSD again. Storage has returned to normal operation."
        )
    )

    # Save state before attempting email

    save_state(state)

    # Send pending notifications

    process_pending_emails(state)

    print("\nMonitoring cycle complete.")


if __name__ == "__main__":

    main()
