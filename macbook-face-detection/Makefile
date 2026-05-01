BINARY  := face-detection
CASCADE := /opt/homebrew/share/opencv4/haarcascades/haarcascade_frontalface_default.xml
DEVICE  := 0

# Clear stale GOROOT that asdf may have set from a previous Go version
unexport GOROOT

.PHONY: deps tidy build run clean

deps:
	brew install opencv

tidy:
	go mod tidy

build: tidy
	go build -o $(BINARY) .

run: build
	./$(BINARY) --cascade $(CASCADE) --device $(DEVICE)

clean:
	rm -f $(BINARY)
