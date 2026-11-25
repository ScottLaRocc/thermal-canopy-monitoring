import os
import shutil
import subprocess
import tempfile

from datetime import datetime


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

# Primary SSD storage
SSD_MOUNT = "/mnt/ssd"

SSD_UUID = "9de653ff-dcc1-45b3-b56b-a693568a73a4"

SSD_DATA_DIR = "/mnt/ssd/field-logger"

# Secondary SD card storage
SD_DATA_DIR = "/home/scott/field-logger-backup"

# Storage limits
SSD_MIN_FREE_GB = 2

SD_MAX_USAGE_GB = 10

SD_MIN_FREE_GB = 5

# Directory names
ENVIRONMENTAL_DIR = "environmental"
FLIR_DIR = "flir"


# ------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------

def get_free_space(path):
    """
    Return available disk space in GB.
    """

    usage = shutil.disk_usage(path)

    return usage.free / (1024 ** 3)


def get_directory_size(path):
    """
    Calculate the total size of files in a directory.

    Returns size in GB.
    """

    total_size = 0

    if not os.path.exists(path):
        return 0

    for root, dirs, files in os.walk(path):

        for filename in files:

            filepath = os.path.join(root, filename)

            try:
                total_size += os.path.getsize(filepath)

            except OSError:
                continue

    return total_size / (1024 ** 3)


# ------------------------------------------------------------------
# SSD health checks
# ------------------------------------------------------------------

def check_ssd_mount():
    """
    Verify that the expected SSD partition is mounted
    at the expected mountpoint.

    Returns
    -------
    tuple
        (mounted, reason)
    """

    try:

        result = subprocess.run(
            [
                "findmnt",
                "-rn",
                "-M", SSD_MOUNT,
                "-o", "UUID"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:

            return False, "SSD is not mounted"

        mounted_uuid = result.stdout.strip()

        if mounted_uuid != SSD_UUID:

            return False, (
                f"Unexpected filesystem mounted at {SSD_MOUNT}: "
                f"{mounted_uuid}"
            )

        return True, "SSD mounted correctly"

    except Exception as e:

        return False, f"Mount check failed: {e}"


def check_ssd_writable():
    """
    Test whether the SSD filesystem is writable.

    Creates and deletes a temporary file.
    """

    try:

        with tempfile.NamedTemporaryFile(
            dir=SSD_MOUNT,
            prefix=".storage_test_",
            delete=True
        ) as test_file:

            test_file.write(b"storage_test")

            test_file.flush()

            os.fsync(test_file.fileno())

        return True, "SSD is writable"

    except Exception as e:

        return False, f"SSD write test failed: {e}"


def check_ssd():
    """
    Perform complete SSD health check.

    Returns
    -------
    dict
        SSD health information.
    """

    mounted, mount_message = check_ssd_mount()

    result = {
        "mounted": mounted,
        "healthy": False,
        "available_gb": None,
        "message": mount_message
    }

    if not mounted:
        return result

    # Check available capacity
    try:

        free_space = get_free_space(SSD_MOUNT)

        result["available_gb"] = round(free_space, 2)

        if free_space < SSD_MIN_FREE_GB:

            result["message"] = (
                f"SSD storage critically low: "
                f"{free_space:.2f} GB available"
            )

            return result

    except Exception as e:

        result["message"] = f"SSD capacity check failed: {e}"

        return result

    # Check filesystem writability
    writable, write_message = check_ssd_writable()

    if not writable:

        result["message"] = write_message

        return result

    result["healthy"] = True

    result["message"] = "SSD operating normally"

    return result


# ------------------------------------------------------------------
# SD card fallback checks
# ------------------------------------------------------------------

def check_sd_storage():
    """
    Verify that sufficient SD card storage is available.

    Returns
    -------
    dict
        SD storage information.
    """

    os.makedirs(SD_DATA_DIR, exist_ok=True)

    free_space = get_free_space("/")

    used_space = get_directory_size(SD_DATA_DIR)

    result = {
        "available_gb": round(free_space, 2),
        "used_gb": round(used_space, 3),
        "healthy": False,
        "message": ""
    }

    if free_space < SD_MIN_FREE_GB:

        result["message"] = (
            f"SD card has insufficient free space: "
            f"{free_space:.2f} GB"
        )

        return result

    if used_space >= SD_MAX_USAGE_GB:

        result["message"] = (
            f"SD fallback storage limit reached: "
            f"{used_space:.2f} GB"
        )

        return result

    result["healthy"] = True

    result["message"] = "SD fallback storage available"

    return result


# ------------------------------------------------------------------
# Storage selection
# ------------------------------------------------------------------

def get_active_storage():
    """
    Select the appropriate storage device.

    Prioritizes the SSD.

    Falls back to the SD card if the SSD is unavailable
    or unhealthy.

    Returns
    -------
    dict
        Active storage configuration.
    """

    timestamp = datetime.now().isoformat()

    ssd = check_ssd()

    sd = check_sd_storage()

    # --------------------------------------------------------------
    # Primary storage: SSD
    # --------------------------------------------------------------

    if ssd["healthy"]:

        base_dir = SSD_DATA_DIR

        active_device = "SSD"

        fallback_active = False

    # --------------------------------------------------------------
    # Secondary storage: SD card
    # --------------------------------------------------------------

    elif sd["healthy"]:

        base_dir = SD_DATA_DIR

        active_device = "SD"

        fallback_active = True

        print()
        print("=" * 60)
        print("WARNING: SSD UNAVAILABLE")
        print(f"Reason: {ssd['message']}")
        print("Switching to SD card storage.")
        print("=" * 60)

    # --------------------------------------------------------------
    # No available storage
    # --------------------------------------------------------------

    else:

        raise RuntimeError(
            "NO AVAILABLE STORAGE!\n"
            f"SSD: {ssd['message']}\n"
            f"SD: {sd['message']}"
        )

    # --------------------------------------------------------------
    # Create directories
    # --------------------------------------------------------------

    environmental_dir = os.path.join(
        base_dir,
        ENVIRONMENTAL_DIR
    )

    flir_dir = os.path.join(
        base_dir,
        FLIR_DIR
    )

    os.makedirs(environmental_dir, exist_ok=True)

    os.makedirs(flir_dir, exist_ok=True)

    # --------------------------------------------------------------
    # Return storage configuration
    # --------------------------------------------------------------

    return {

        "base_dir": base_dir,

        "environmental": environmental_dir,

        "flir": flir_dir,

        "active_device": active_device,

        "fallback_active": fallback_active,

        "ssd_mounted": ssd["mounted"],

        "ssd_healthy": ssd["healthy"],

        "ssd_available_gb": ssd["available_gb"],

        "sd_available_gb": sd["available_gb"],

        "sd_used_gb": sd["used_gb"],

        "timestamp": timestamp,

        "ssd_message": ssd["message"],

        "sd_message": sd["message"]
    }


# ------------------------------------------------------------------
# Standalone test
# ------------------------------------------------------------------

if __name__ == "__main__":

    print()
    print("=" * 60)
    print("STORAGE MANAGER TEST")
    print("=" * 60)

    storage = get_active_storage()

    print()

    for key, value in storage.items():

        print(f"{key}: {value}")

    print()
    print(f"Active storage: {storage['active_device']}")

    print(f"Environmental directory: {storage['environmental']}")

    print(f"FLIR directory: {storage['flir']}")

    print()
    print("Storage manager test complete.")
