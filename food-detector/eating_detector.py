#!/usr/bin/env python3
"""
Eating detector using chest-mounted camera.

Detects WHETHER you eat by tracking wrist trajectory with MediaPipe Hands:
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
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
from ultralytics import YOLO

# ── Zones (normalized 0–1, Y increases downward) ─────────────────────────────
PLATE_ZONE_Y = 0.55   # wrist below this line = in plate zone
EXIT_ZONE_Y  = 0.15   # wrist above this line = exiting toward mouth
COOLDOWN_SEC = 3.0    # min seconds between logged eating events


def build_model(model_path: str) -> YOLO:
    p = Path(model_path)
    if p.exists():
        print(f"Food model: {p}")
        return YOLO(str(p))
    print(f"  {p} not found — using yolov8n.pt (generic, no food labels yet)")
    print("  Train your model first: python train.py ...")
    return YOLO("yolov8n.pt")


class EatingStateMachine:
    """
    Tracks one hand's wrist trajectory:
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
                # returned to rest without reaching mouth
                self.state = self.IDLE

        return False


def detect_food(model: YOLO, frame) -> str | None:
    """Run food detection, return highest-confidence label or None."""
    results = model(frame, verbose=False, conf=0.35)
    best_label = None
    best_conf  = 0.0
    for r in results:
        for box in r.boxes:
            conf = float(box.conf[0])
            if conf > best_conf:
                best_conf  = conf
                best_label = r.names[int(box.cls[0])]
    return best_label


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
    parser.add_argument("--model", default="runs/world_food/weights/best.pt",
                        help="YOLOv8 food model weights")
    parser.add_argument("--log", default="eating_log.csv",
                        help="CSV file to log eating events")
    args = parser.parse_args()

    food_model = build_model(args.model)

    mp_hands = mp.solutions.hands
    mp_draw  = mp.solutions.drawing_utils
    hands    = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.5,
    )

    source = int(args.source) if args.source.isdigit() else args.source
    cap    = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"ERROR: cannot open source: {args.source}")
        return

    # one state machine per hand (index 0=left, 1=right)
    machines     = [EatingStateMachine(), EatingStateMachine()]
    last_food    = None
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
            rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # refresh food label every 1.5 s
            now = time.time()
            if now - food_refresh > 1.5:
                last_food    = detect_food(food_model, frame)
                food_refresh = now

            result = hands.process(rgb)
            ate_this_frame = False

            if result.multi_hand_landmarks:
                for hand_lm, hand_info in zip(result.multi_hand_landmarks,
                                               result.multi_handedness):
                    label    = hand_info.classification[0].label  # "Left"/"Right"
                    hand_idx = 0 if label == "Left" else 1

                    mp_draw.draw_landmarks(frame, hand_lm,
                                           mp_hands.HAND_CONNECTIONS)

                    wrist_y = hand_lm.landmark[mp_hands.HandLandmark.WRIST].y
                    wx = int(hand_lm.landmark[mp_hands.HandLandmark.WRIST].x * w)
                    wy = int(wrist_y * h)
                    cv2.circle(frame, (wx, wy), 8, (255, 255, 0), -1)

                    if machines[hand_idx].update(wrist_y):
                        ate_this_frame = True
            else:
                for m in machines:
                    m.state = EatingStateMachine.IDLE

            if ate_this_frame:
                flash_frames = 15
                ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                food = last_food or "unknown"
                print(f"[{ts}]  EATING DETECTED — {food}")
                writer.writerow([ts, food, ""])
                log_file.flush()

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
        hands.close()
        log_file.close()
        print(f"\nLog saved to: {log_path.resolve()}")


if __name__ == "__main__":
    main()
