#!/usr/bin/env python3
"""
Run world food detection using CoreML model on Apple Neural Engine (ANE).

On M3 Pro, CoreML automatically routes the model to the ANE for fast,
power-efficient inference.

Usage:
    python detect.py --source image.jpg
    python detect.py --source path/to/folder/
    python detect.py --source 0               # webcam
    python detect.py --source video.mp4 --save
    python detect.py --model runs/world_food/weights/best.mlpackage --conf 0.35
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

HERE = Path(__file__).parent  # always food-detector/ regardless of cwd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=str(HERE / "runs/world_food/weights/best.mlpackage"),
                        help="Path to CoreML .mlpackage model")
    parser.add_argument("--source", default="0",
                        help="Image path, folder, video path, or 0 for webcam")
    parser.add_argument("--conf", type=float, default=0.40,
                        help="Confidence threshold (default: 0.40)")
    parser.add_argument("--iou", type=float, default=0.45,
                        help="NMS IoU threshold (default: 0.45)")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--save", action="store_true",
                        help="Save annotated results to runs/detect/")
    parser.add_argument("--no-show", action="store_true",
                        help="Disable live display window")
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        # Fall back to .pt if mlpackage not found yet
        pt_path = model_path.with_suffix(".pt")
        if pt_path.exists():
            print(f"WARNING: {model_path} not found, falling back to {pt_path}")
            print("Run export_coreml.py first to enable ANE inference.\n")
            model_path = pt_path
        else:
            print(f"ERROR: {model_path} not found — run export_coreml.py first")
            return

    print(f"Model : {model_path}")
    print(f"Source: {args.source}")
    print(f"Conf  : {args.conf}  |  IoU: {args.iou}")
    if str(model_path).endswith(".mlpackage"):
        print("Backend: CoreML → Apple Neural Engine (ANE)\n")
    else:
        print("Backend: PyTorch → MPS\n")

    model = YOLO(str(model_path))

    source = int(args.source) if args.source == "0" else args.source
    show = not args.no_show

    results = model.predict(
        source=source,
        conf=args.conf,
        iou=args.iou,
        imgsz=args.imgsz,
        show=show,
        save=args.save,
        stream=True,
        project=str(HERE / "runs" / "detect"),
        name="predict",
        exist_ok=True,
    )

    for result in results:
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            continue
        detections = []
        for box in boxes:
            cls_id = int(box.cls)
            conf = float(box.conf)
            name = result.names[cls_id]
            detections.append(f"{name} ({conf:.0%})")
        if detections:
            print("Detected:", ", ".join(detections))


if __name__ == "__main__":
    main()
