# Jetson Edge AI Pipeline

## Project Overview

A real-time edge AI sensor fusion system running on NVIDIA Jetson Orin Nano with Docker/ROS2 Humble. The system simultaneously collects data from a UNI-T UTi721M thermal camera and Intel RealSense D435 depth camera to perform thermal anomaly detection and distance estimation. System performance and decision-making latency are benchmarked across different power modes (7W, 15W, 25W).

---

## Hardware Requirements

- NVIDIA Jetson Orin Nano (JetPack 5.x)
- Intel RealSense D435 (USB 3.0)
- UNI-T UTi721M Thermal Camera (USB)

## Software Requirements

- Docker + Docker Compose
- ROS2 Humble
- NVIDIA L4T ML Container (`nvcr.io/nvidia/l4t-ml:r36.2.0-py3`)

---

## Architecture

```
UTi721M (thermal)                    RealSense D435 (depth)
      │                                       │
thermal_camera_driver_node           realsense2_camera_node
      │ /thermal/image_raw16                  │ /camera/camera/depth/image_rect_raw
      └──────────────┬────────────────────────┘
                     │
             sensor_fusion_node
          (ApproximateTimeSynchronizer, slop=0.04s)
                     │ /fused/output_v2
                     │
              decision_node
     (thermal bitmap + region analysis + distance)
                     │
     ┌───────────────┼───────────────┐
     │               │               │
/decision/alert  /decision/       /decision/latency
(String)         thermal_bitmap   (Float32)
                 (Image)               │
                                power_benchmark_node
                                (latency + system metrics)

system_monitor_node  ←── tegrastats (CPU/GPU/RAM/power/temperature)
      │ /system_monitor (DiagnosticArray, 1Hz)
      │
      ├── diagnostics_node ←── subscribes: /thermal/image_raw16
      │   (pipeline health)               /camera/camera/depth/image_rect_raw
      │   → /diagnostics                  /fused/output_v2
      │                                   /decision/alert
      │
      ├── calibration_node
      │   
      │
      └── power_benchmark_node
          (power mode performance + latency comparison)
```

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/gizemezer/jetson-edge-ai-pipeline.git
cd jetson-edge-ai-pipeline
git checkout dev
```

### 2. Local Development (Windows + WSL2 + Docker)

**WSL2 Setup**

```powershell
# Windows PowerShell (Administrator):
wsl --install
# Install Ubuntu 22.04 LTS from Microsoft Store
```

**Docker Setup**

Install Docker Desktop for Windows: https://docs.docker.com/desktop/setup/install/windows-install/

Go to Settings → Resources → WSL Integration → Enable Ubuntu-22.04.

**Start the Container**

```bash
docker compose up -d --build
docker exec -it jetson_pipeline_dev bash
```

**Build ROS2 Package**

```bash
cd /workspace
colcon build --packages-select edge_ai_interfaces edge_ai_fusion
source install/setup.bash
```

### 3. Jetson Orin Nano Setup

**Verify JetPack**

```bash
cat /etc/nv_tegra_release
# or
jetson_release
```

**Jetson Docker Container**

```bash
# docker-compose.yml uses Dockerfile.jetson
docker compose up -d --build
docker exec -it jetson_pipeline_dev bash
```

**Verify Camera Connections**

```bash
# List USB devices
lsusb

# List video devices
ls /dev/video*
v4l2-ctl --list-devices

# Check thermal camera format
v4l2-ctl --device=/dev/video6 --list-formats-ext
```

Expected output:
```
Intel(R) RealSense(TM) Depth Ca → /dev/video0 - /dev/video5
USB Camera (UTi721M)            → /dev/video6, /dev/video7
```

**Build ROS2 Package (Jetson)**

```bash
cd /workspace
colcon build --packages-select edge_ai_interfaces edge_ai_fusion
source install/setup.bash
```

---

## Running Nodes Individually

For each terminal, first enter the container:
```bash
docker exec -it jetson_pipeline_dev bash
source install/setup.bash
```

**Terminal 1 — System Monitor:**
```bash
ros2 run edge_ai_fusion system_monitor_node
```

**Terminal 2 — Thermal Camera:**
```bash
ros2 run thermal_camera_driver thermal_camera_driver_node --ros-args -p device:=/dev/video6
```

**Terminal 3 — RealSense Depth Camera:**
```bash
ros2 launch realsense2_camera rs_launch.py
```

**Terminal 4 — Sensor Fusion:**
```bash
ros2 run edge_ai_fusion sensor_fusion_node
```

**Terminal 5 — Decision:**
```bash
ros2 run edge_ai_fusion decision_node
```

**Terminal 6 — Diagnostics (optional):**
```bash
ros2 run edge_ai_fusion diagnostics_node
```

---

## Single Command Launch

```bash
ros2 launch edge_ai_fusion pipeline_hardware.launch.py

# For a different thermal camera port
ros2 launch edge_ai_fusion pipeline_hardware.launch.py device:=/dev/video6
```

---

## Benchmarking

### Power Modes (Jetson Orin Nano)

| ID | Mode | Description |
|---|---|---|
| 3 | 7W | Low power |
| 0 | 15W | Default |
| 1 | 25W | Maximum performance |
| 2 | MAXN_SUPER | Unlimited |

```bash
sudo nvpmodel -m 3   # Switch to 7W
sudo nvpmodel -q     # Query current mode
```

### Calibration

Run separately for each power mode while `system_monitor_node` is active:

```bash
# 7W
ros2 run edge_ai_fusion calibration_node --ros-args -p power_mode:=7W

# Reboot → 15W
sudo nvpmodel -m 0 && sudo reboot
ros2 run edge_ai_fusion calibration_node --ros-args -p power_mode:=15W

# Reboot → 25W
sudo nvpmodel -m 1 && sudo reboot
ros2 run edge_ai_fusion calibration_node --ros-args -p power_mode:=25W

# After all 3 modes are complete
ros2 run edge_ai_fusion merge_calibration_reports
```

### Power Mode Benchmark

Run with the full pipeline active (system_monitor + all nodes):

```bash
ros2 run edge_ai_fusion power_benchmark_node --ros-args -p power_mode:=7W
# Reboot → 15W
ros2 run edge_ai_fusion power_benchmark_node --ros-args -p power_mode:=15W
# Reboot → 25W
ros2 run edge_ai_fusion power_benchmark_node --ros-args -p power_mode:=25W

ros2 run edge_ai_fusion merge_power_reports
```

### Resolution Benchmark

```bash
ros2 run edge_ai_fusion resolution_node
```

---

## Topics

| Topic | Publisher | Subscriber | Message Type | Hz |
|---|---|---|---|---|
| /thermal/image_raw16 | thermal_camera_driver_node | sensor_fusion_node, diagnostics_node | sensor_msgs/Image | 25 |
| /camera/camera/depth/image_rect_raw | realsense2_camera_node | sensor_fusion_node, diagnostics_node | sensor_msgs/Image | 30 |
| /fused/output_v2 | sensor_fusion_node | decision_node, resolution_node, diagnostics_node | FusedData | ~25 |
| /decision/alert | decision_node | diagnostics_node | std_msgs/String | ~25 |
| /decision/thermal_bitmap | decision_node | — | sensor_msgs/Image | ~25 |
| /decision/latency | decision_node | power_benchmark_node | std_msgs/Float32 | ~25 |
| /system_monitor | system_monitor_node | calibration_node, power_benchmark_node, diagnostics_node | diagnostic_msgs/DiagnosticArray | 1 |
| /diagnostics | diagnostics_node | — | diagnostic_msgs/DiagnosticArray | 1 |

---

## Parameters

| Parameter | Default | Description |
|---|---|---|
| device | /dev/video6 | Thermal camera USB port |
| power_mode | 7W | Calibration/benchmark power mode |
| THERMAL_HOT | 45.0°C | Hot region threshold |
| THERMAL_DANGEROUS | 60.0°C | Dangerous region threshold |
| DEPTH_TOO_CLOSE | 50mm | Minimum valid distance |
| DEPTH_MAX_VALID | 300mm | Maximum valid distance |
| slop | 0.04s | Sensor synchronization tolerance (Nyquist: 1/2×25Hz) |
| CALIB_SEC | 600s | Calibration duration |
| STEADY_START | 300s | Steady-state start time |
| MEASURE_SEC | 60s | Benchmark measurement duration |
| N_RUNS | 5 | Number of benchmark runs |
| COOLDOWN_SEC | 180s | Cool-down duration between modes |

---

## Output Files

All outputs are stored in `/workspace/logs/`.

### Report PNG Files

| File | Generated By |
|---|---|
| calibration_report_final.png | merge_calibration_reports |
| power_benchmark_final.png | merge_power_reports |
| resolution_benchmark.png | resolution_node |
| bitmap_HHMMSS.png | decision_node (every 20 seconds) |

---

## Sample Outputs

### Thermal Node (terminal)

<img width="1600" height="846" alt="1" src="https://github.com/user-attachments/assets/7f675b6c-5142-4020-8244-5472278e4bcd" />

### RealSense Node (terminal)

<img width="1600" height="846" alt="3" src="https://github.com/user-attachments/assets/d55b2aec-583e-4ebd-a024-2602673bc052" />

### Sensor Fusion Node (terminal)

<img width="1600" height="852" alt="7" src="https://github.com/user-attachments/assets/0f93dbfb-2d24-4420-b4e4-48fc7d056a9f" />

### Decision Node (terminal)

<img width="1907" height="835" alt="image" src="https://github.com/user-attachments/assets/4dbd0c45-8337-4a97-8b3b-a18288524699" />

### Calibration Node (terminal)

<img width="1856" height="708" alt="image" src="https://github.com/user-attachments/assets/271fb45c-7207-46b3-b507-de1e4560bb14" />

<img width="1907" height="670" alt="image" src="https://github.com/user-attachments/assets/d6716e71-a8ed-42e1-b2a7-d6ed9de04bd2" />

<img width="1889" height="614" alt="image" src="https://github.com/user-attachments/assets/42e0567c-2a74-4263-8b02-8b93d91a7131" />

### Power Benchmark Node (terminal)

<img width="1877" height="772" alt="image" src="https://github.com/user-attachments/assets/29977ba1-5f52-4ecf-a786-05a7c6d426a7" />

<img width="1888" height="838" alt="image" src="https://github.com/user-attachments/assets/85b3a747-9c6a-4394-9add-f400669d3c90" />

<img width="1883" height="704" alt="image" src="https://github.com/user-attachments/assets/7597630a-2318-477a-810c-cf1895664461" />

### System Monitor (terminal)

<img width="1369" height="672" alt="image" src="https://github.com/user-attachments/assets/b0b745be-db9a-4c17-83ad-44134d37e8ab" />

<img width="1600" height="838" alt="14" src="https://github.com/user-attachments/assets/aefc801e-6738-4f08-b226-8deb0bb84584" />

### Diagnostics (terminal)

<img width="716" height="434" alt="image" src="https://github.com/user-attachments/assets/1c532756-7a7d-4b77-9d3d-66b6fc099f28" />

### Launch (terminal)

<img width="1033" height="546" alt="image" src="https://github.com/user-attachments/assets/00b21bc4-8015-454d-8f35-af6af1acc80c" />

---

## Repository Structure

```
jetson-edge-ai-pipeline/
├── src/
│   ├── edge_ai_fusion/
│   │   ├── edge_ai_fusion/
│   │   │   ├── sensor_fusion_node.py
│   │   │   ├── decision_node.py
│   │   │   ├── system_monitor_node.py
│   │   │   ├── diagnostics_node.py
│   │   │   ├── calibration_node.py
│   │   │   ├── power_benchmark_node.py
│   │   │   ├── resolution_node.py
│   │   │   ├── merge_calibration_reports.py
│   │   │   └── merge_power_reports.py
│   │   └── launch/
│   │       └── pipeline_hardware.launch.py
│   ├── edge_ai_interfaces/
│   │   └── msg/
│   │       └── FusedData.msg
│   └── thermal-camera-ros2-driver/
├── docker-compose.yml
├── Dockerfile.jetson
└── README.md
```

---

## License

MIT License
