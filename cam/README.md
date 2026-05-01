# ESP32-CAM HTTP Stream

WiFi camera stream using the AI-Thinker ESP32-CAM board and ESP-IDF.  
Exposes an MJPEG stream and JPEG snapshot over HTTP for image processing on a host PC.

## Endpoints

| URL | Description |
|-----|-------------|
| `http://<IP>/stream` | MJPEG continuous stream |
| `http://<IP>/capture` | Single JPEG snapshot |

## Requirements

- [ESP-IDF v5.0+](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/)
- AI-Thinker ESP32-CAM board
- USB-TTL adapter (CH340 / CP2102) for flashing

## Quick Start

### 1. Install prerequisites (once)

```bash
brew install cmake ninja dfu-util python@3.12
```

> ESP-IDF v5 requires Python 3.10+. macOS ships with 3.9 — the above installs 3.12 via Homebrew.

### 2. Clone ESP-IDF (once)

```bash
mkdir -p ~/esp && cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git
```

> Downloads ~1 GB, takes a few minutes.

### 3. Run the ESP-IDF installer (once)

```bash
cd ~/esp/esp-idf
export PATH="/opt/homebrew/opt/python@3.12/bin:$PATH"
./install.sh esp32
```

### 4. Set WiFi credentials

```bash
make config
```

Inside menuconfig:

1. Arrow keys to highlight **ESP32-CAM Configuration** → press **Enter**
2. Highlight **WiFi SSID** → press **Enter**, type your network name, press **Enter**
3. Highlight **WiFi Password** → press **Enter**, type your password, press **Enter**
4. Press **S** to Save
5. Press **Q** to Quit

### 5. Install components (once)

```bash
make setup
```

### 6. Build

```bash
make build
```

### 7. Flash + monitor

Connect the ESP32-CAM via USB-TTL adapter, hold **IO0 to GND** while powering on, then:

```bash
make flash-monitor
# Port is auto-detected. Override if needed:
make flash-monitor PORT=/dev/tty.usbserial-XXXX
```

The serial monitor will print the assigned IP address after boot.

To stop the monitor: press **Ctrl + ]**

### 8. Open the stream

```
http://<IP>/stream
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make setup` | Pull `esp32-camera` component (run once) |
| `make config` | Open menuconfig |
| `make build` | Compile firmware |
| `make flash` | Flash to board |
| `make monitor` | Open serial monitor |
| `make flash-monitor` | Flash then open monitor |
| `make all` | setup + build + flash-monitor |
| `make clean` | Remove build artefacts |

Override IDF path if not installed at `~/esp/esp-idf`:

```bash
make build IDF_PATH=/path/to/esp-idf
```

## Hardware Wiring (AI-Thinker)

| ESP32-CAM pin | USB-TTL pin |
|---------------|-------------|
| 5V | 5V |
| GND | GND |
| U0TXD (GPIO1) | RX |
| U0RXD (GPIO3) | TX |
| IO0 | GND (flash mode only) |

Disconnect IO0 from GND after flashing and press reset to boot normally.

## Project Structure

```
cam/
├── Makefile
├── CMakeLists.txt
├── sdkconfig.defaults      # PSRAM + partition config
└── main/
    ├── main.c
    ├── wifi.c / wifi.h
    ├── camera.c / camera.h
    ├── http_server.c / http_server.h
    ├── Kconfig.projbuild   # WiFi SSID/password menu entries
    └── idf_component.yml   # espressif/esp32-camera dependency
```
