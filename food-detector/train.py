#!/usr/bin/env python3
"""
Train YOLOv8 world food detection model.

Uses Apple MPS (Metal GPU) on M3 Pro for training.
After training, run export_coreml.py to enable ANE inference.

Usage:
    python train.py                                                    # default
    python train.py --imgsz 320 --batch 32 --cache ram                # fast (recommended)
    python train.py --imgsz 320 --batch 32 --cache ram --device cpu   # if MPS is slow
"""

import argparse
from pathlib import Path

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="yolov8n.pt",
                        help="Base weights: yolov8n/s/m/l/x.pt (default: yolov8n.pt — fastest)")
    parser.add_argument("--data", default="merged_dataset/data.yaml",
                        help="Path to merged data.yaml")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16,
                        help="Batch size (reduce to 8 if OOM)")
    parser.add_argument("--patience", type=int, default=20,
                        help="Early stopping patience")
    parser.add_argument("--cache", default="ram",
                        help="Cache images: ram (fastest), disk, or none (default: ram)")
    parser.add_argument("--device", default="mps",
                        help="Training device: mps, cpu, 0 (default: mps)")
    parser.add_argument("--workers", type=int, default=0,
                        help="Dataloader workers — 0 works best with MPS (default: 0)")
    args = parser.parse_args()

    if not Path(args.data).exists():
        print(f"ERROR: {args.data} not found — run prepare_dataset.py first")
        return

    model = YOLO(args.model)

    cache = False if args.cache == "none" else args.cache
    print(f"Training {args.model} on {args.data}")
    print(f"Device: {args.device}  |  Epochs: {args.epochs}  |  Batch: {args.batch}  |  imgsz: {args.imgsz}  |  Cache: {cache}")
    print("After training, run: python export_coreml.py\n")

    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        cache=cache,
        project="runs",
        name="world_food",
        patience=args.patience,
        save=True,
        plots=True,
        exist_ok=True,
    )

    best = Path("runs/world_food/weights/best.pt")
    if best.exists():
        print(f"\nDone! Best model saved to: {best}")
        print("Next step: python export_coreml.py")
    else:
        print("\nTraining complete. Check runs/world_food/weights/")


if __name__ == "__main__":
    main()
