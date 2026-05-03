#!/usr/bin/env python3
"""
Export trained YOLOv8 model to CoreML for Apple Neural Engine (ANE) inference.

The exported .mlpackage runs on the ANE of M3 Pro, which is faster and more
power-efficient than CPU or GPU for inference.

Usage:
    python export_coreml.py
    python export_coreml.py --model runs/world_food/weights/best.pt
    python export_coreml.py --int8   # smaller model, slight accuracy trade-off
"""

import argparse
from pathlib import Path

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="runs/world_food/weights/best.pt",
                        help="Path to trained .pt model")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--int8", action="store_true",
                        help="Quantize to INT8 (smaller file, ~2% accuracy drop)")
    args = parser.parse_args()

    pt_path = Path(args.model)
    if not pt_path.exists():
        print(f"ERROR: {pt_path} not found — run train.py first")
        return

    model = YOLO(str(pt_path))

    print(f"Exporting {pt_path} → CoreML (.mlpackage)")
    print(f"INT8 quantization: {'ON' if args.int8 else 'OFF'}")
    print("The model will use Apple Neural Engine (ANE) on M3 Pro for inference.\n")

    model.export(
        format="coreml",
        imgsz=args.imgsz,
        nms=True,
        int8=args.int8,
    )

    mlpackage = pt_path.with_suffix(".mlpackage")
    if mlpackage.exists():
        size_mb = sum(f.stat().st_size for f in mlpackage.rglob("*") if f.is_file()) / 1e6
        print(f"\nCoreML model: {mlpackage}  ({size_mb:.1f} MB)")
        print("Next step: python detect.py --model", mlpackage)
    else:
        print("\nExport complete. Check the same directory as the .pt file.")


if __name__ == "__main__":
    main()
