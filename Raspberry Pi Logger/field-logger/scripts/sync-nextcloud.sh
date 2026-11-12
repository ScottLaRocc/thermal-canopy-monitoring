#!/bin/bash

SOURCE="/mnt/ssd/field-logger"
DEST="nextcloud:Shared/Andesflux/Photos/FLIR-IR-Tambopata"

rclone copy "$SOURCE" "$DEST" \
    --log-level INFO
