import board
import busio
import adafruit_sht31d
import logging

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Initialize I2C
# ------------------------------------------------------------------

i2c = busio.I2C(board.SCL, board.SDA)

# Initialize each sensor independently.
# If one fails to initialize, the other can still be used.

def initialize_sensor(address, name):
    try:
        sensor = adafruit_sht31d.SHT31D(i2c, address=address)
        logger.info("%s initialized at I2C address 0x%02X", name, address)
        return sensor

    except Exception as e:
        logger.warning(
            "Could not initialize %s at address 0x%02X: %s",
            name, address, e
        )
        return None


sht31_ambient = initialize_sensor(0x44, "Ambient SHT31")
sht31_flirhousing = initialize_sensor(0x45, "FLIR housing SHT31")

# ------------------------------------------------------------------
# Read individual sensors
# ------------------------------------------------------------------

def read_one_sensor(sensor, name, prefix):
    """
    Read one SHT31 independently.

    Returns temperature and humidity, or None for both if
    the sensor is unavailable or a read fails.
    """

    result = {
        f"{prefix}_temperature_c": None,
        f"{prefix}_relative_humidity_pct": None,
    }

    if sensor is None:
        logger.warning("%s is unavailable; skipping read", name)
        return result

    try:
        temperature = sensor.temperature
        humidity = sensor.relative_humidity

        result[f"{prefix}_temperature_c"] = temperature
        result[f"{prefix}_relative_humidity_pct"] = humidity

    except (OSError, RuntimeError, ValueError) as e:
        logger.warning("Failed to read %s: %s", name, e)

    except Exception as e:
        logger.exception("Unexpected error reading %s: %s", name, e)

    return result


# ------------------------------------------------------------------
# Read both sensors
# ------------------------------------------------------------------

def read_sht31():
    """Read both sensors independently and return a flat dictionary."""

    data = {}

    data.update(
        read_one_sensor(
            sht31_ambient,
            "Ambient SHT31",
            "sht31_ambient"
        )
    )

    data.update(
        read_one_sensor(
            sht31_flirhousing,
            "FLIR housing SHT31",
            "sht31_flirhousing"
        )
    )

    return data


# ------------------------------------------------------------------
# Test
# ------------------------------------------------------------------

if __name__ == "__main__":
    data = read_sht31()

    print("\nSHT31 Readings")
    print("-" * 40)

    for name, value in data.items():
        if value is None:
            print(f"{name}: unavailable")
        else:
            print(f"{name}: {value:.2f}")

    print("-" * 40)

