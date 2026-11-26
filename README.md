# Project Overview
This repository documents the design and implementation of a thermal imagery data acquisition system for forest canopy research, deployed at the Tambopata National Reserve AndesFlux PE-TNR tower. 

The system utilizes a Raspberry Pi to coordinate data collection, storage, and cloud syncing across sensors including a FLIR A615 thermal camera, Phytos 31 leaf wetness sensor, SHT31 temperature and humidty sensors, and a thermistor-based temperature reference panel. 

This repository provides documentation of the system's hardware and software architecture, testing protocols, and data processing protocols. It is intended to support the reproducibility, maintenance, and adaptation of the system for environmental monitoring and ecological research.

## 2. Hardware Configuration
The following table summarizes the hardware components connected to the Raspberry Pi and their respective functions.

| Component | Model | Interface | Purpose |
|---|---|---|---|
| Single-board computer | Raspberry Pi 5 | — | Data acquisition controller |
| Storage | NVMe SSD | PCIe | Local data storage |
| Thermal camera | FLIR A615 | Ethernet | Thermal imagery acquisition |
| Temperature/humidity sensors | 2 SHT31 | I2C | Temperature and humidity measurements (ambient / camera housing)|
| Leaf wetness sensor | PHYTOS 31 | Analog via ADS1115 | Leaf wetness monitoring |
| Analog-to-digital converter (ADC) | ADS1115 | I2C | Analog voltage acquisition |
| Thermistor reference panel | 4 Amphenol EC95G104VN thermistors | Campbell CR310 data logger | temperature reference measurements

### 2a. Wiring Diagram 
```
               12V DC from Tower       
                       |      
              +--------+--------+--------------+     
              |                 |              |      
        12V-5V converter    FLIR A615     Campbell CR310     
           (USB-C)                             | 
              |                                |    
          Raspberry Pi 5                  +----+---------+     
              |                           |              |        
       +------+------+                Thermistors (4)   (Other tower sensors)       
       |             |      
      I2C         Ethernet     
       |             |     
   +---+---+      FLIR A615    
   |       |     
   SHT31   ADS1115      
           | 
           PHYTOS31        
```

## 3. Software Architecture 
```
Raspberry Pi 5    
│    
├── /home/scott/    
│   ├── field-logger/    
│   │   └── scripts/     
│   │       ├── main.py             # main data collection script    
│   │       ├── flir.py             # operates flir thermal captures    
│   │       ├── phytos31.py         # operates phytos31 leaf wetness captures    
│   │       ├── sht31.py            # operates SHT31 temp/humidity sensors  
│   │       ├── storage_manager.py  # manages storage location (prefer ssd, sd backup)  
│   │       ├── sync-nextcloud.sh   # synchronizes ssd with Nextcloud using rclone     
│   │       └── monitor.py          # tracks hardware temp., ssd/sd status, last data coll. 
│   │                               # & emails alerts   
│   │                               
│   ├── field-logger-backup/        # backup SD storage location in case of SSD loss
│   │ 
│   ├── .pyenv/                     # virtual environment 
│   │    └── versions/    
│   │        └── deployment_env/    
│   │
│   └── requirements.txt
│     
├── /mnt/    
│   └── ssd/                     # mounted SSD location 
│       └── field-logger/    
│           ├── environmental/       
│           │     └── .json      # phytos and sht31 data     
│           └── flir/     
│                ├── .tiff       # thermal images     
│                └── .json       # constants and variables for calculating deg C     
│    
├── /etc/    
│   └── systemd/    
│       └── system/    
│           ├── data-logger.service      # runs main.py data acquisition script automatically 
│           ├── nextcloud-sync.service   # automates Nextcloud sync    
│           ├── nextcloud-sync.timer     # automatically schedules sync (every 30 min)
│           ├── station-monitor.service  # automatically monitors cpu & FLIR temperature
│           └── station-monitor.timer    # schedules station-monitor.service (every 10 min)
│     
└── Data Synchronization    
    └── rclone → Nextcloud    

Campbell CR310    
└── thermistor_reference_panel.CR300     # campbell control script 
```

## 4. Normal Operation: 

The data logger operates autonomously once the Raspberry Pi boots. Systemd manages the startup and scheduling of the acquisition, monitoring, and synchronization processes. Automated processes are controlled by `.service` and `.timer` scripts, which initialize automatically on boot. 

### 4.1 Data Acquisition (Every 30 Minutes)
Controlled by `data-logger.service`

Triggers `main.py` at each hour (:00) and half-hour (:30) time stamp from pi's onboard clock. 

`main.py` collects:

1. **Temperature and humidity measurements:** calls `sht31.py` to collect temperature and relative humidity from the SHT31 sensors (ambient and FLIR housing). 

2. **Leaf wetness measurements:** calls `phytos31.py` to read the PHYTOS31 sensor voltage.

3. **Thermal imagery:** calls `flir.py` to collect thermal image and metadata from the FLIR A615. 

4. **Storage location:** calls `storage-manager.py` to check for connection and available space in the SSD. If connection to SSD is interrupted, sets the storage location to onboard SD. 

Data from sensors are stored as .json under `/environmental/`, and data from FLIR camera as .tiff and .json metadata under `/flir/`. 

- A modular design allows `main.py` to execute successfully if one sensor or storage location is compromised. 

### 4.2 Cloud Synchronization (Every 30 minutes)
`nextcloud-sync.timer` and `nextcloud-sync.service` execute `sync-nextcloud.sh`. 

- Uses rclone to synchronize the pi's local storage directories (SSD & SD) with cloud storage in Nextcloud. 

### 4.3 System Monitoring (Every 10 Minutes)
`station-monitor.timer` and `station-monitor.service` execute `monitor.py`, which checks:
- Raspberry Pi CPU temperature.
- FLIR housing temperature and humidity.
- Ambient temperature and relative humidity.
- SSD mounting and SD card storage status.
- Time elapsed since the last successful data collection.

Email notifications are sent if predefined warning or critical thresholds are exceeded for each monitoring variable, and when the system returns to normal. 


## 4. Python Environment and Dependencies
===== PYTHON ENVIRONMENT =====    
Environment: /home/scott/.pyenv/versions/3.10.13/envs/deployment_env    
Python executable: /home/scott/.pyenv/shims/python     
Python version: Python 3.10.13    

Use: `pyenv activate deployment_env`

Requirements list: `~/field-logger/requirements.txt`

