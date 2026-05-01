# Face-detection service — Go + GoCV (OpenCV)
# Usage:
#   make deps      — install OpenCV via Homebrew (once)
#   make tidy      — fetch Go module dependencies
#   make build     — compile binary → ./face-detection
#   make run       — run (set CAM=http://<IP>/stream)
#   make clean     — remove compiled binary
#
# Example:
#   make run CAM=http://192.168.1.42/stream

BINARY  := face-detection
CASCADE := /opt/homebrew/share/opencv4/haarcascades/haarcascade_frontalface_default.xml
ADDR    := :8080
CAM     ?=

.PHONY: deps tidy build run clean

deps:
	brew install opencv

tidy:
	go mod tidy

build: tidy
	go build -o $(BINARY) .

run:
	@if [ -z "$(CAM)" ]; then \
		echo ""; \
		echo "ERROR: CAM is required."; \
		echo "       Usage: make run CAM=http://192.168.x.x/stream"; \
		echo ""; \
		exit 1; \
	fi
	go run . --cam $(CAM) --addr $(ADDR) --cascade $(CASCADE)

clean:
	rm -f $(BINARY)
