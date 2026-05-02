# Roboflow Dataset Downloader

Downloads image datasets from [Roboflow Universe](https://universe.roboflow.com) by search query, for training a custom object detection model.

## Requirements

- Python 3.10+
- Free Roboflow account (for API key)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> Next time you open a new terminal, run `source venv/bin/activate` before using the script.

## Get an API Key

1. Sign up at [app.roboflow.com](https://app.roboflow.com) (free, no credit card)
2. Click your profile icon → **Settings** → **Workspaces** → **API Keys**
3. Copy your **Private API Key**

## Usage

### Default (food + thai food, pages 1–5)
```bash
python download.py --key YOUR_KEY
```

### Custom search queries
```bash
python download.py --key YOUR_KEY --query "thai food" "japanese food" "korean food"
```

### Specific page range
```bash
python download.py --key YOUR_KEY --query food --start 3 --end 8
```

### All pages
```bash
python download.py --key YOUR_KEY --query food --all
```

### COCO format instead of YOLOv8
```bash
python download.py --key YOUR_KEY --query food --format coco
```

## Arguments

| Argument | Default | Description |
|---|---|---|
| `--key` | required | Your Roboflow API key |
| `--query` | `food` `thai food` | One or more search queries |
| `--format` | `yolov8` | Export format: `yolov8` \| `coco` \| `voc` |
| `--start` | `1` | First page to fetch |
| `--end` | `5` | Last page to fetch (~50 projects per page) |
| `--all` | off | Fetch ALL pages (ignores `--start` / `--end`) |

## Output Structure

```
datasets/
└── <workspace>/
    └── <project>/
        ├── train/
        │   ├── images/
        │   └── labels/
        ├── valid/
        │   ├── images/
        │   └── labels/
        └── data.yaml
```

## Train with YOLOv8

After downloading, train directly with:

```bash
pip install ultralytics
yolo train data=datasets/<workspace>/<project>/data.yaml model=yolov8n.pt epochs=100
```

## Export Formats

| Format | Use with | Notes |
|---|---|---|
| `yolov8` | Ultralytics YOLOv8 | **Recommended** — includes `data.yaml`, ready to train |
| `coco` | Detectron2, MMDetection | Single JSON annotation file |
| `voc` | Legacy pipelines | XML per image |
