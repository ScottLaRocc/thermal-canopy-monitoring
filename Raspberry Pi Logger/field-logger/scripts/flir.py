import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import PySpin


# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

LOCAL_TIMEZONE = ZoneInfo("America/Lima")


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------

def get_node_value(nodemap, name):
    """Safely read a GenICam node."""

    node = nodemap.GetNode(name)

    if node is None or not PySpin.IsAvailable(node):
        return None

    try:
        interface = node.GetPrincipalInterfaceType()

        if interface == PySpin.intfIFloat:
            return PySpin.CFloatPtr(node).GetValue()

        elif interface == PySpin.intfIInteger:
            return PySpin.CIntegerPtr(node).GetValue()

        elif interface == PySpin.intfIEnumeration:
            enum = PySpin.CEnumerationPtr(node)
            entry = enum.GetCurrentEntry()
            return entry.GetSymbolic()

        elif interface == PySpin.intfIString:
            return PySpin.CStringPtr(node).GetValue()

        elif interface == PySpin.intfIBoolean:
            return PySpin.CBooleanPtr(node).GetValue()

    except PySpin.SpinnakerException:
        return None

    return None


# ------------------------------------------------------------------
# Capture FLIR image
# ------------------------------------------------------------------

def capture_flir(save_dir):
    """
    Capture one radiometric FLIR image.

    Returns
    -------
    dict
        FLIR filenames and timestamp for inclusion in the
        main observation record.
    """

    os.makedirs(save_dir, exist_ok=True)

    # Generate timestamp when this acquisition occurs
    now = datetime.now(LOCAL_TIMEZONE)

    timestamp = now.strftime("%Y%m%d_%H%M%S")
    timestamp_iso = now.isoformat()

    tiff_filename = f"thermal_{timestamp}.tiff"
    json_filename = f"thermal_{timestamp}.json"

    tiff_path = os.path.join(save_dir, tiff_filename)
    json_path = os.path.join(save_dir, json_filename)

    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()

    cam = None

    try:

        if cam_list.GetSize() == 0:
            raise RuntimeError("No FLIR cameras detected.")

        cam = cam_list.GetByIndex(0)
        cam.Init()

        nodemap = cam.GetNodeMap()

        # --------------------------------------------------------------
        # Stream buffer handling
        # --------------------------------------------------------------

        stream_nodemap = cam.GetTLStreamNodeMap()

        buffer_mode = PySpin.CEnumerationPtr(
            stream_nodemap.GetNode("StreamBufferHandlingMode")
        )

        buffer_mode.SetIntValue(
            buffer_mode.GetEntryByName("NewestOnly").GetValue()
        )

        # --------------------------------------------------------------
        # Force desired settings
        # --------------------------------------------------------------

        pixel_format = PySpin.CEnumerationPtr(
            nodemap.GetNode("PixelFormat")
        )

        pixel_format.SetIntValue(
            pixel_format.GetEntryByName("Mono16").GetValue()
        )

        ir_format = PySpin.CEnumerationPtr(
            nodemap.GetNode("IRFormat")
        )

        ir_format.SetIntValue(
            ir_format.GetEntryByName("Radiometric").GetValue()
        )

        acq_mode = PySpin.CEnumerationPtr(
            nodemap.GetNode("AcquisitionMode")
        )

        acq_mode.SetIntValue(
            acq_mode.GetEntryByName("Continuous").GetValue()
        )

        # --------------------------------------------------------------
        # Acquire image
        # --------------------------------------------------------------

        cam.BeginAcquisition()

        try:

            image = cam.GetNextImage(5000)

            try:

                if image.IsIncomplete():
                    raise RuntimeError("FLIR image incomplete.")

                image.Save(tiff_path)

            finally:
                image.Release()

        finally:
            cam.EndAcquisition()

        # --------------------------------------------------------------
        # Collect metadata
        # --------------------------------------------------------------

        metadata = {
            "timestamp": timestamp_iso,

            "camera_model": get_node_value(
                nodemap,
                "DeviceModelName"
            ),

            "camera_serial": get_node_value(
                nodemap,
                "DeviceSerialNumber"
            ),

            "IRFormat": get_node_value(
                nodemap,
                "IRFormat"
            ),

            "PixelFormat": get_node_value(
                nodemap,
                "PixelFormat"
            ),

            "IRFrameRate": get_node_value(
                nodemap,
                "IRFrameRate"
            ),

            # Calibration constants
            "R": get_node_value(nodemap, "R"),
            "B": get_node_value(nodemap, "B"),
            "F": get_node_value(nodemap, "F"),
            "J0": get_node_value(nodemap, "J0"),
            "J1": get_node_value(nodemap, "J1"),
            "X": get_node_value(nodemap, "X"),

            "alpha1": get_node_value(
                nodemap,
                "alpha1"
            ),

            "alpha2": get_node_value(
                nodemap,
                "alpha2"
            ),

            "beta1": get_node_value(
                nodemap,
                "beta1"
            ),

            "beta2": get_node_value(
                nodemap,
                "beta2"
            ),

            # Radiometric parameters
            "ObjectEmissivity": get_node_value(
                nodemap,
                "ObjectEmissivity"
            ),

            "AtmosphericTemperature": get_node_value(
                nodemap,
                "AtmosphericTemperature"
            ),

            "ReflectedTemperature": get_node_value(
                nodemap,
                "ReflectedTemperature"
            ),

            "ExtOpticsTemperature": get_node_value(
                nodemap,
                "ExtOpticsTemperature"
            ),

            # Image dimensions
            "Width": get_node_value(
                nodemap,
                "Width"
            ),

            "Height": get_node_value(
                nodemap,
                "Height"
            ),
        }

        # --------------------------------------------------------------
        # Validate calibration constants
        # --------------------------------------------------------------

        required_constants = [
            "R",
            "B",
            "F",
            "J0",
            "J1",
        ]

        missing = [
            key
            for key in required_constants
            if metadata[key] is None
        ]

        if missing:
            raise RuntimeError(
                "Missing required FLIR calibration constants: "
                + ", ".join(missing)
            )

        # --------------------------------------------------------------
        # Warn about missing environmental parameters
        # --------------------------------------------------------------

        optional_parameters = [
            "ObjectEmissivity",
            "AtmosphericTemperature",
            "ReflectedTemperature",
            "ExtOpticsTemperature",
        ]

        for key in optional_parameters:
            if metadata[key] is None:
                print(f"Warning: {key} unavailable.")

        # --------------------------------------------------------------
        # Save metadata
        # --------------------------------------------------------------

        with open(json_path, "w") as f:
            json.dump(metadata, f, indent=4)

        # --------------------------------------------------------------
        # Return information to main.py
        # --------------------------------------------------------------

        return {
            "flir_timestamp": timestamp_iso,
            "flir_filename": tiff_filename,
            "flir_metadata_filename": json_filename,
        }

    finally:

        if cam is not None:
            cam.DeInit()
            del cam

        cam_list.Clear()
        system.ReleaseInstance()


# ------------------------------------------------------------------
# Standalone test
# ------------------------------------------------------------------

if __name__ == "__main__":

    data = capture_flir("/mnt/ssd/field-logger/flir")

    print(f"Saved image: {data['flir_filename']}")
    print(f"Saved metadata: {data['flir_metadata_filename']}")
