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
              | (USB-C)                        |    
          Raspberry Pi 5                  +----+---------+     
              |                           |              |        
       +------+------+                Thermistors (4)   (Other tower sensors)       
       |             |      
      I2C          Ethernet     
       |             |     
   +---+---+      FLIR A615    
   |       |     
   SHT31   ADS1115      
           | (15 m cable, trs 3.5mm jack w breakout)        
        PHYTOS31        
```

## 3. Software Architecture 
```
Raspberry Pi 5    
│    
├── /home/scott/    
│   ├── field-logger/    
│   │   └── scripts/     
│   │       ├── main.py           # main data collection script    
│   │       ├── flir.py           # operates flir thermal captures    
│   │       ├── phytos31.py       # operates phytos31 leaf wetness captures    
│   │       └── sht31.py          # operates SHT31 temp/humidity sensors    
│   │    
│   └── .pyenv/    
│       └── versions/    
│           └── deployment_env/    
│     
├── /mnt/    
│   └── ssd/    
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
│           ├── data-logger.service      # runs main.py data acquisition script automatically on boot     
│           ├── nextcloud-sync.service   # synchronizes ssd with Nextcloud using rclone      
│           └── nextcloud-sync.timer     # automatically schedules and triggers Nextcloud synch service at configured intervals    
│    
└── Data Synchronization    
    └── rclone → Nextcloud    

Campbell CR310    
└── thermistor_reference_panel.CR300     # campbell control script 
```

## 4. Python Environment and Dependencies
===== PYTHON ENVIRONMENT =====    
Environment: /home/scott/.pyenv/versions/3.10.13/envs/deployment_env    
Python executable: /home/scott/.pyenv/shims/python     
Python version: Python 3.10.13    

===== PYENV =====    
deployment_env (set by PYENV_VERSION environment variable)

===== INSTALLED PACKAGES =====    
Adafruit-Blinka==8.64.0    
adafruit-circuitpython-ads1x15==3.0.5    
adafruit-circuitpython-busdevice==5.2.17    
adafruit-circuitpython-connectionmanager==3.1.8    
adafruit-circuitpython-requests==4.1.17    
adafruit-circuitpython-sht31d==2.3.31    
adafruit-circuitpython-typing==1.12.3    
Adafruit-PlatformDetect==3.89.1    
Adafruit-PureIO==1.1.11    
binho-host-adapter==0.1.6    
lgpio==0.2.2.0    
numpy==1.26.4    
pyftdi==0.57.2    
pyserial==3.5    
pyusb==1.3.1    
rpi-ws281x==5.0.0    
RPi.GPIO==0.7.1    
spinnaker-python @ file:///home/scott/Downloads/spinnaker_python-4.3.0.189-cp310-cp310-linux_aarch64.whl     
sysv_ipc==1.2.0      
toml==0.10.2     
typing_extensions==4.16.0    

