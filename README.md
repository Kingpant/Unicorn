# Unicorn

A personal eating tracker gadget — a small chest-mounted camera that watches what you eat and whether you actually ate it.

The idea is simple: wear a tiny camera on your chest, and it quietly logs every meal — the food type and the moment you bring it to your mouth — without you having to do anything.

## What it does

- Identifies the food on your plate (Thai, Japanese, Italian, and more)
- Detects whether you actually ate, by watching your hand move from plate to mouth
- Logs every eating event with a timestamp and food name

## How it's built

| Folder | What it does |
|--------|-------------|
| `esp32cam-gc2145/` | Firmware for the ESP32-CAM — streams live video over WiFi |
| `dataset-downloader/` | Downloads global food datasets from Roboflow by cuisine query |
| `food-detector/` | Trains the food model, exports to CoreML for Apple Neural Engine, and runs the eating detector |
| `face-detection/` | Face detection service that reads the ESP32-CAM stream |
| `macbook-face-detection/` | Face detection running on MacBook camera |

## The gadget

```
[Chest camera]  →  WiFi  →  [Mac: food detector + eating detector]  →  eating_log.csv
```

The chest camera streams JPEG frames over WiFi to the Mac.
The Mac identifies what food is on the plate and detects each time a hand goes from plate to mouth.
Every eating event is saved with a timestamp and food name.

## Quick start

- [`food-detector/README.md`](food-detector/README.md) — train the model and run the eating detector
- [`dataset-downloader/README.md`](dataset-downloader/README.md) — download more food datasets
- [`esp32cam-gc2145/README.md`](esp32cam-gc2145/README.md) — flash the camera firmware
