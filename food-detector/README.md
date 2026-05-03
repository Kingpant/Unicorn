# food-detector

Detect food from around the world using YOLOv8 trained on merged global food datasets,
with inference running on the **Apple Neural Engine (ANE)** of the MacBook M3 Pro.

## Architecture

```
Training  → YOLOv8  (CPU)    ← stable on M3 Pro; avoids PyTorch MPS validation bug
Inference → CoreML  (ANE)    ← low-power, fast inference on M3 Pro NPU
```

## Setup

```bash
cd food-detector
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 1 — Download more global food datasets

Add world cuisines to your existing dataset by running the downloader with broader queries:

```bash
cd ../dataset-downloader
source venv/bin/activate

python download.py --key YOUR_API_KEY --query \
  "japanese food" "sushi" "ramen" \
  "indian food" "curry" "biryani" \
  "italian food" "pizza" "pasta" \
  "chinese food" "dim sum" "dumplings" \
  "mexican food" "taco" "burrito" \
  "korean food" "bibimbap" "tteokbokki" \
  "french food" "american food" "bbq"
```

## Step 2 — Merge all datasets

Scans every downloaded dataset, normalizes class names, converts segmentation → bounding boxes,
and writes a unified `merged_dataset/` ready for training.

```bash
cd ../food-detector
python prepare_dataset.py
```

## Step 3 — Train (CPU recommended on Apple Silicon)

```bash
# recommended — fast and stable on M3 Pro
python train.py --imgsz 320 --batch 32 --cache ram --device cpu --epochs 50

# higher accuracy (slower, needs more RAM)
python train.py --imgsz 640 --batch 16 --cache ram --device cpu --epochs 100
```

### Training parameters explained

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `--imgsz` | `640` | Resize images to this square size before training. `320` is 4× faster than `640` with minimal accuracy loss — good for a first run |
| `--batch` | `16` | Images processed per step. Larger = fewer steps per epoch and more stable learning, but uses more RAM. `32` works well on M3 Pro (18 GB) |
| `--cache` | `ram` | Load all images into RAM on epoch 1, then skip disk for all future epochs. Biggest speed win on large datasets |
| `--device` | `mps` | Hardware to train on. Use `cpu` on Apple Silicon — avoids a PyTorch MPS bug that crashes validation. `cpu` on M3 Pro is fast enough |
| `--epochs` | `100` | Full passes through the dataset. `50` gives a usable model; more epochs improve accuracy up to a point then plateau |
| `--model` | `yolov8n.pt` | Base model size. `n`=nano (fastest), `s`=small, `m`=medium (best practical accuracy) |
| `--patience` | `20` | Stop early if validation does not improve for this many epochs. Saves time if the model converges before `--epochs` |

### Model size trade-offs

| Model | Train speed | Accuracy | Use when |
|-------|-------------|----------|----------|
| yolov8n | fastest | good | quick experiments, edge devices |
| yolov8s | fast | better | balanced — good starting point |
| yolov8m | medium | best practical | final model for production |

Best weights saved to `runs/world_food/weights/best.pt`.

### Reading training output

Each epoch prints two lines — one while training, one after validation:

**Training line:**
```
Epoch 9/50 | box_loss 1.098 | cls_loss 1.737 | dfl_loss 1.285
```

| Number | What it means | Want |
|--------|--------------|------|
| `9/50` | Finished epoch 9 out of 50 | Higher |
| `box_loss` | How wrong the box position is — is the rectangle drawn in the right place? | Lower |
| `cls_loss` | How wrong the food name is — saying "sushi" when it's "pad thai"? | Lower |
| `dfl_loss` | How sloppy the box edges are — tight around food or loose? | Lower |

All 3 losses dropping each epoch = model is learning normally.

**Validation line:**
```
all | 1886 images | 3551 instances | P 0.576 | R 0.465 | mAP50 0.468 | mAP50-95 0.359
```

| Number | What it means | Want |
|--------|--------------|------|
| `P` (Precision) | When it says "this is food", how often it's correct | Higher |
| `R` (Recall) | Out of all food in the photo, how much it found | Higher |
| `mAP50` | **Main accuracy score** — 0 = useless, 1.0 = perfect | Higher |
| `mAP50-95` | Stricter version — box must be very tight to count | Higher |

**mAP50 progress guide:**

| mAP50 | Meaning |
|-------|---------|
| 0.0 – 0.3 | Model is struggling |
| 0.3 – 0.5 | Learning, getting useful |
| 0.5 – 0.7 | Good, practical for real use |
| 0.7+ | Excellent |

A first run with many food classes typically reaches 0.55–0.65 by epoch 50.

### If training crashes — resume

```bash
python train.py --resume
```

Picks up from `runs/world_food/weights/last.pt` (saved after every epoch). No need to repeat any flags.

## Step 4 — Export to CoreML (ANE)

```bash
python export_coreml.py
# with INT8 quantization (smaller file, ~2% accuracy trade-off):
# python export_coreml.py --int8
```

Outputs `runs/world_food/weights/best.mlpackage` — CoreML routes this to the ANE automatically.

## Step 5 — Detect

```bash
# webcam live detection
python detect.py --source 0

# single image
python detect.py --source photo.jpg

# folder of images (save results)
python detect.py --source images/ --save

# video file
python detect.py --source video.mp4 --save

# lower threshold to catch more food
python detect.py --source photo.jpg --conf 0.3
```

## Step 6 — Eating Detector (did I actually eat?)

Detects **whether** you eat using wrist trajectory from a chest-mounted camera.
No mouth detection needed — tracks the hand going down to the plate then up toward the mouth.

```bash
pip install -r requirements.txt   # installs mediapipe

# test on Mac webcam first
python eating_detector.py

# after training your food model
python eating_detector.py --model runs/world_food/weights/best.pt

# with ESP32-CAM chest camera stream
python eating_detector.py --source http://192.168.1.x:81/stream --model runs/world_food/weights/best.pt
```

### How it works

```
Chest camera frame
        ↓
MediaPipe Hands  →  wrist moves DOWN into plate zone
                 →  wrist moves UP and exits frame  =  eating event logged
        +
YOLOv8 food model  →  identifies food type on plate
        ↓
eating_log.csv: [timestamp, food, confidence_note]
```

### Zone calibration

Edit these constants in `eating_detector.py` to match your camera mount height:

| Constant | Default | Meaning |
|----------|---------|---------|
| `PLATE_ZONE_Y` | `0.55` | Wrist below this = in plate zone |
| `EXIT_ZONE_Y` | `0.15` | Wrist above this = going to mouth |
| `COOLDOWN_SEC` | `3.0` | Min seconds between eating events |

### Hardware — Phase 2 (buy after webcam test passes)

| Part | Purpose | Price |
|------|---------|-------|
| XIAO ESP32S3 Sense | Tiny camera + WiFi, wears on chest | ~$15 |
| LiPo 500 mAh | All-day power | ~$8 |
| Chest clip / lanyard | Mount at sternum level | ~$2 |

ESP32S3 streams JPEG over WiFi → Mac runs `eating_detector.py` → logs result.

## M3 Pro chip roles

| Stage     | Hardware | Why |
|-----------|----------|-----|
| Training  | CPU | M3 Pro CPU is fast; MPS has a PyTorch validation bug (tensor size mismatch) |
| Export    | CPU       | One-time conversion, speed irrelevant |
| Inference | ANE (NPU) | Fixed-graph neural ops — 3–5× faster, far less power than GPU |
