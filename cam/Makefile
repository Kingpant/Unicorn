# ESP32-CAM build/flash helper  (GNU Make 3.81+ compatible)
# Usage:
#   make setup         — install components (run once after clone)
#   make config        — open menuconfig to set WiFi SSID/password
#   make build         — compile the firmware
#   make flash         — flash to board (auto-detects USB port)
#   make monitor       — open serial monitor
#   make flash-monitor — flash then open monitor
#   make all           — setup + build + flash-monitor
#   make clean         — remove build artefacts
#   make ports         — start port helper server for device-finder.html
#
# Override port:     make flash PORT=/dev/tty.usbserial-XXXX
# Override IDF path: make build IDF_PATH=/path/to/esp-idf

SHELL := /bin/bash

IDF_PATH    ?= $(HOME)/esp/esp-idf
IDF_EXPORT  := $(IDF_PATH)/export.sh

# Auto-detect first available USB-serial port (macOS + Linux)
PORT ?= $(shell ls /dev/tty.usbserial-* /dev/tty.SLAB_USBtoUART* /dev/ttyUSB* 2>/dev/null | head -1)

.PHONY: all setup config build flash monitor flash-monitor clean port-check ports

all: setup build flash-monitor

setup:
	@if [ ! -f "$(IDF_EXPORT)" ]; then \
		echo ""; \
		echo "ERROR: ESP-IDF not found at $(IDF_PATH)"; \
		echo "       Install: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/"; \
		echo "       Or set:  make setup IDF_PATH=/path/to/esp-idf"; \
		echo ""; \
		exit 1; \
	fi; \
	source $(IDF_EXPORT) && \
	idf.py reconfigure

config:
	@if [ ! -f "$(IDF_EXPORT)" ]; then \
		echo "ERROR: ESP-IDF not found at $(IDF_PATH)"; exit 1; \
	fi; \
	source $(IDF_EXPORT) && \
	idf.py menuconfig

build:
	@if [ ! -f "$(IDF_EXPORT)" ]; then \
		echo ""; \
		echo "ERROR: ESP-IDF not found at $(IDF_PATH)"; \
		echo "       Install: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/"; \
		echo "       Or set:  make build IDF_PATH=/path/to/esp-idf"; \
		echo ""; \
		exit 1; \
	fi; \
	source $(IDF_EXPORT) && \
	idf.py build

flash: port-check
	@if [ ! -f "$(IDF_EXPORT)" ]; then \
		echo "ERROR: ESP-IDF not found at $(IDF_PATH)"; exit 1; \
	fi; \
	source $(IDF_EXPORT) && \
	idf.py -p $(PORT) flash

monitor: port-check
	@if [ ! -f "$(IDF_EXPORT)" ]; then \
		echo "ERROR: ESP-IDF not found at $(IDF_PATH)"; exit 1; \
	fi; \
	source $(IDF_EXPORT) && \
	idf.py -p $(PORT) monitor

flash-monitor: port-check
	@if [ ! -f "$(IDF_EXPORT)" ]; then \
		echo "ERROR: ESP-IDF not found at $(IDF_PATH)"; exit 1; \
	fi; \
	source $(IDF_EXPORT) && \
	idf.py -p $(PORT) flash monitor

clean:
	rm -rf build/

ports:
	python3 ../list-ports.py

port-check:
	@if [ -z "$(PORT)" ]; then \
		echo ""; \
		echo "ERROR: No USB serial port detected."; \
		echo "       Connect the board, then check:  ls /dev/tty.usb*"; \
		echo "       Or specify:  make flash PORT=/dev/tty.usbserial-XXXX"; \
		echo ""; \
		exit 1; \
	fi
	@echo "Using port: $(PORT)"
