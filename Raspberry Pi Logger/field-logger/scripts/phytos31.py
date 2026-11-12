import board
import busio
import logging

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn


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

    logger.info("PHYTOS 31 initialized successfully.")

except Exception as e:
    logger.warning("PHYTOS 31 initialization failed: %s", e)

    phytos31 = None


# ------------------------------------------------------------------
# Read sensor
# ------------------------------------------------------------------

def read_phytos31():
    """Read PHYTOS 31 and return a flat dictionary."""

    if phytos31 is None:
        logger.warning(
            "PHYTOS 31 unavailable: ADC initialization failed."
        )

        return {
            "phytos31_voltage_mv": None,
        }

    try:
        voltage_mv = phytos31.voltage * 1000

        return {
            "phytos31_voltage_mv": voltage_mv,
        }

    except Exception as e:
        logger.warning(
            "PHYTOS 31 read failed: %s", e
        )

        return {
            "phytos31_voltage_mv": None,
        }


# ------------------------------------------------------------------
# Test
# ------------------------------------------------------------------

if __name__ == "__main__":
    data = read_phytos31()

    for name, value in data.items():
        if value is None:
            print(f"{name}: unavailable")
        else:
            print(f"{name}: {value:.2f}")
