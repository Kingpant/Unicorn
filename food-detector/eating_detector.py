#!/usr/bin/env python3
"""
Eating detector using chest-mounted camera.

Detects WHETHER you eat by tracking wrist trajectory with YOLOv8 Pose:
  - Wrist moves DOWN into plate zone → reaching for food
  - Wrist moves UP and exits frame   → bringing food to mouth = eating event

Identifies WHAT you eat using your YOLOv8 food model.

Usage:
    python eating_detector.py                         # webcam (test on Mac)
    python eating_detector.py --source 0              # explicit webcam index
    python eating_detector.py --source http://192.168.1.x:81/stream  # ESP32-CAM
    python eating_detector.py --model runs/world_food/weights/best.pt
"""

import argparse
import csv
import time
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

import cv2
from ultralytics import YOLO

HERE = Path(__file__).parent  # always food-detector/ regardless of cwd

# ── Zones (normalized 0–1, Y increases downward) ─────────────────────────────
PLATE_ZONE_Y = 0.55   # wrist below this line = in plate zone
EXIT_ZONE_Y  = 0.15   # wrist above this line = exiting toward mouth
COOLDOWN_SEC = 1.5    # min seconds between logged eating events
KP_CONF_MIN  = 0.3    # ignore wrist keypoints below this confidence

# YOLOv8 COCO pose keypoint indices
LEFT_WRIST  = 9
RIGHT_WRIST = 10


def build_food_model(model_path: str) -> YOLO:
    p = Path(model_path)
    if p.exists():
        print(f"Food model: {p}")
        return YOLO(str(p))
    print(f"  {p} not found — using yolov8n.pt (generic, no food labels yet)")
    print("  Train your model first: python train.py ...")
    return YOLO("yolov8n.pt")


class EatingStateMachine:
    """
    Tracks one wrist's trajectory:
      IDLE → REACHING (wrist enters plate zone) → eating event (wrist exits top)
    """
    IDLE     = "idle"
    REACHING = "reaching"

    def __init__(self):
        self.state = self.IDLE
        self.last_event_time = 0.0

    def update(self, wrist_y: float | None) -> bool:
        """Return True when an eating event is detected."""
        if wrist_y is None:
            self.state = self.IDLE
            return False

        if self.state == self.IDLE and wrist_y > PLATE_ZONE_Y:
            self.state = self.REACHING

        elif self.state == self.REACHING:
            if wrist_y < EXIT_ZONE_Y:
                now = time.time()
                if now - self.last_event_time > COOLDOWN_SEC:
                    self.last_event_time = now
                    self.state = self.IDLE
                    return True
            elif wrist_y <= PLATE_ZONE_Y:
                self.state = self.IDLE

        return False


def detect_food(model: YOLO, frame) -> tuple[str | None, list]:
    """Run food detection, return (best_label, list of box dicts for drawing)."""
    results = model(frame, verbose=False, conf=0.20)
    best_label = None
    best_conf  = 0.0
    boxes = []
    for r in results:
        for box in r.boxes:
            conf  = float(box.conf[0])
            label = r.names[int(box.cls[0])]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            boxes.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                          "label": label, "conf": conf})
            if conf > best_conf:
                best_conf  = conf
                best_label = label
    return best_label, boxes


def draw_food_boxes(frame, boxes: list):
    """Redraw the last known food boxes onto the current frame."""
    for b in boxes:
        cv2.rectangle(frame, (b["x1"], b["y1"]), (b["x2"], b["y2"]), (0, 255, 255), 2)
        text = f"{b['label']} {b['conf']:.0%}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (b["x1"], b["y1"] - th - 6),
                      (b["x1"] + tw + 4, b["y1"]), (0, 255, 255), -1)
        cv2.putText(frame, text, (b["x1"] + 2, b["y1"] - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)


def draw_zones(frame):
    h, w = frame.shape[:2]
    cv2.line(frame, (0, int(PLATE_ZONE_Y * h)), (w, int(PLATE_ZONE_Y * h)),
             (0, 165, 255), 1)
    cv2.putText(frame, "plate zone", (8, int(PLATE_ZONE_Y * h) - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)
    cv2.line(frame, (0, int(EXIT_ZONE_Y * h)), (w, int(EXIT_ZONE_Y * h)),
             (0, 200, 0), 1)
    cv2.putText(frame, "mouth zone", (8, int(EXIT_ZONE_Y * h) - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 0), 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="0",
                        help="Camera: 0=webcam, or ESP32-CAM stream URL")
    parser.add_argument("--model", default=str(HERE / "runs/world_food/weights/best.pt"),
                        help="YOLOv8 food model weights")
    parser.add_argument("--log", default=str(HERE / "eating_log.csv"),
                        help="CSV file to log eating events")
    args = parser.parse_args()

    food_model = build_food_model(args.model)
    # downloads yolov8n-pose.pt automatically on first run (~6 MB)
    pose_model = YOLO("yolov8n-pose.pt")

    source = int(args.source) if args.source.isdigit() else args.source
    cap    = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"ERROR: cannot open source: {args.source}")
        return

    # one state machine per wrist (index 0=left, 1=right)
    machines     = [EatingStateMachine(), EatingStateMachine()]
    food_votes   = deque(maxlen=5)  # last 5 detections — pick most common
    last_food    = None
    last_boxes   = []               # redrawn every frame so boxes stay visible
    food_refresh = 0.0
    flash_frames = 0

    log_path     = Path(args.log)
    write_header = not log_path.exists()
    log_file     = open(log_path, "a", newline="")
    writer       = csv.writer(log_file)
    if write_header:
        writer.writerow(["timestamp", "food", "confidence_note"])

    print("\nEating detector running — press Q to quit\n")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            h, w = frame.shape[:2]

            # refresh food label every 1.5 s to save CPU
            now = time.time()
            if now - food_refresh > 1.5:
                detected, boxes = detect_food(food_model, frame)
                if detected:
                    food_votes.append(detected)
                    last_boxes = boxes
                if food_votes:
                    last_food = Counter(food_votes).most_common(1)[0][0]
                food_refresh = now

            draw_food_boxes(frame, last_boxes)

            # ── Pose: detect wrists ───────────────────────────────────────────
            pose_results   = pose_model(frame, verbose=False, conf=0.4)
            wrist_detected = [False, False]
            ate_this_frame = False

            for r in pose_results:
                if r.keypoints is None or r.keypoints.xy is None:
                    continue
                kps  = r.keypoints.xy    # (num_persons, 17, 2) pixel coords
                conf = r.keypoints.conf  # (num_persons, 17)

                for person in range(len(kps)):
                    for wrist_kp, machine_idx in [(LEFT_WRIST, 0), (RIGHT_WRIST, 1)]:
                        kp_conf = float(conf[person][wrist_kp])
                        if kp_conf < KP_CONF_MIN:
                            continue

                        px = float(kps[person][wrist_kp][0])
                        py = float(kps[person][wrist_kp][1])
                        wrist_y_norm = py / h

                        wrist_detected[machine_idx] = True
                        cv2.circle(frame, (int(px), int(py)), 8, (255, 255, 0), -1)

                        if machines[machine_idx].update(wrist_y_norm):
                            ate_this_frame = True

            # reset state machines for wrists not seen this frame
            for i, seen in enumerate(wrist_detected):
                if not seen:
                    machines[i].update(None)

            # ── Log eating event ──────────────────────────────────────────────
            if ate_this_frame:
                flash_frames = 15
                ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                food = last_food or "unknown"
                print(f"[{ts}]  EATING DETECTED — {food}")
                writer.writerow([ts, food, ""])
                log_file.flush()

            # ── Overlay ───────────────────────────────────────────────────────
            draw_zones(frame)

            if flash_frames > 0:
                overlay = frame.copy()
                cv2.rectangle(overlay, (0, 0), (w, h), (0, 255, 0), -1)
                cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)
                flash_frames -= 1

            status = f"Food: {last_food}" if last_food else "Food: scanning..."
            cv2.putText(frame, status, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, "Q to quit", (10, h - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

            cv2.imshow("Eating Detector", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        log_file.close()
        print(f"\nLog saved to: {log_path.resolve()}")


if __name__ == "__main__":
    main()
