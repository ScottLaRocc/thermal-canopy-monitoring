#!/bin/bash

DEST="nextcloud:Andesflux/Photos/FLIR-IR-Tambopata"

# Synchronize SSD if mounted
if mountpoint -q /mnt/ssd; then
    rclone copy /mnt/ssd/field-logger "$DEST" --log-level INFO
else
    echo "SSD not mounted. Skipping SSD synchronization."
fi

# Synchronize SD fallback
rclone copy /home/scott/field-logger-backup "$DEST" --log-level INFO
