# ESP32-CAM GC2145 HTTP Stream

WiFi camera stream using the AI-Thinker ESP32-CAM board with **GC2145 sensor** and ESP-IDF.  
Exposes an MJPEG stream and JPEG snapshot over HTTP for image processing on a host PC.

## Hardware

| Item | Details |
|------|---------|
| Board | AI-Thinker ESP32-CAM |
| Sensor | GC2145 (no hardware JPEG — software conversion via `frame2jpg()`) |
| Flasher | USB-TTL adapter (CH340 / CP2102) |

## Endpoints

| URL | Description |
|-----|-------------|
| `http://<IP>/stream` | MJPEG continuous stream |
| `http://<IP>/capture` | Single JPEG snapshot |

## Performance

| Setting | Value |
|---------|-------|
| Resolution | QVGA (320×240) |
| Frame rate | ~8 fps |
| JPEG quality | 20 (software) |
| Frame pacing | 120 ms between frames |

> The GC2145 outputs raw RGB565 — the ESP32 CPU encodes every frame to JPEG in software.
> This caps throughput at ~8 fps. For 30 fps VGA, swap to an **OV2640** module (same connector).

## Requirements

- [ESP-IDF v5.0+](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/)
- macOS with Homebrew (or Linux)
- USB-TTL adapter for flashing

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
cd esp32cam-gc2145
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

Watch the serial monitor for the assigned IP address:

```
I (xxxx) wifi: connected
I (xxxx) esp_netif: sta ip: 192.168.x.x
I (xxxx) http_server: HTTP server started on :80
```

To stop the monitor: press **Ctrl + ]**

### 8. Open the stream

```
http://<IP>/stream
```

Or open a snapshot:

```
http://<IP>/capture
```

## Finding Your USB Port

Run the companion port server and open `device-finder.html` in Chrome:

```bash
make ports
```

Then open `../device-finder.html` directly in Chrome (not via Live Server — it causes unwanted reloads).

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make setup` | Pull `esp32-camera` component (run once) |
| `make config` | Open menuconfig for WiFi credentials |
| `make build` | Compile firmware |
| `make flash` | Flash to board |
| `make monitor` | Open serial monitor |
| `make flash-monitor` | Flash then open monitor |
| `make ports` | Start port helper server for device-finder.html |
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
esp32cam-gc2145/
├── Makefile
├── CMakeLists.txt
├── sdkconfig.defaults          # PSRAM + partition config
└── main/
    ├── main.c
    ├── wifi.c / wifi.h
    ├── camera.c / camera.h     # GC2145 init, RGB565, sensor tuning
    ├── http_server.c / http_server.h  # MJPEG stream + JPEG snapshot
    ├── Kconfig.projbuild       # WiFi SSID/password menu entries
    └── idf_component.yml       # espressif/esp32-camera dependency
```

## Sensor Settings (camera.c)

The GC2145 is initialized with automatic image controls for better image quality:

| Setting | Value |
|---------|-------|
| Auto white balance | Enabled |
| Auto gain | Enabled |
| Auto exposure | Enabled |
| Brightness | +1 |
| Contrast | +1 |
| Saturation | 0 |
| Flip / Mirror | Off |

## Upgrading to OV2640

Swap the camera module (same 24-pin FPC connector) and change two lines in `main/camera.c`:

```c
.pixel_format = PIXFORMAT_JPEG,   // hardware JPEG from sensor
.frame_size   = FRAMESIZE_VGA,    // 640×480
```

No other code changes needed — `http_server.c` already handles hardware JPEG frames.
