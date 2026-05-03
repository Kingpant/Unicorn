#!/usr/bin/env python3
"""
Merge all downloaded food datasets into a single YOLOv8 detection dataset.

- Skips datasets with numeric-only class labels
- Normalizes class names (lowercase, consistent)
- Converts segmentation labels → bounding boxes
- Outputs merged_dataset/ ready for train.py

Usage:
    python prepare_dataset.py                                        # all folders
    python prepare_dataset.py --query thai_food japanese_food        # specific cuisines
    python prepare_dataset.py --query thai_food --out thai_merged    # custom output dir
"""

import argparse
import re
import shutil
import yaml
from pathlib import Path

SKIP_CLASSES = {"-", "normal", "bowl", "thai food"}

# Non-food classes that slip through food dataset searches
NON_FOOD_CLASSES = {
    "hand", "text", "object", "stick", "cup", "lid", "ne", "scc",
    "lymphocytes", "japanese characters", "japanese honeysuckle",
    "japanese knotweed", "japanese knotweedrotation", "japanese kamon",
    "jasmineleaves", "milkpot", "teapot", "tea caddy spoon",
    "dish a", "dish b", "dish c", "dish d",
    # Japanese feudal lord names (from kamon/family-crest datasets)
    "oda", "tokugawa", "toyotomi",
}

# Keywords that indicate a class name is README/documentation text, not a food label
_GARBAGE_KEYWORDS = (
    "http", "directory", "please", "download", ".txt", ".jpg", ".zip",
    "bounding box", "dataset", "copyright", "university", "student",
    "professor", "prof.", "android", "smartphone", "release", "revised",
    "redundant", "contact", "address", "research group", "informatics",
    "correspondences", "food list", "food id", "food photo", "zip file",
    "e mail", "master student", "electro", "tokyo", "bb info",
    # URL patterns
    ".ac.jp", ".mobi", ".com", ".org", "food group", "ids and food",
    "people than", "other countries", "most of the",
)


def is_numeric(name: str) -> bool:
    return re.fullmatch(r"\d+", name.strip()) is not None


def is_garbage(name: str) -> bool:
    """True if the class name is README/documentation text rather than a food label."""
    stripped = name.strip()
    if not stripped:          # empty string
        return True
    if len(stripped) < 2:    # single character
        return True
    if len(stripped) > 60:
        return True
    lower = stripped.lower()
    return any(kw in lower for kw in _GARBAGE_KEYWORDS)


def normalize(name: str) -> str:
    return name.strip().lower().replace("_", " ").replace("-", " ")


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def seg_to_bbox(points: list[float]) -> tuple[float, float, float, float]:
    """Convert polygon point list [x1,y1,x2,y2,...] to cx,cy,w,h, clamped to [0,1]."""
    xs = points[0::2]
    ys = points[1::2]
    x0, x1 = _clamp01(min(xs)), _clamp01(max(xs))
    y0, y1 = _clamp01(min(ys)), _clamp01(max(ys))
    return (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0


def find_split_dir(root: Path, config: dict, split: str) -> Path | None:
    key = "val" if split == "valid" else split

    # Roboflow data.yaml uses ../train/images (one level up) but the actual
    # images sit at root/train/images — check yaml path first, then fall back.
    candidates = []
    raw = config.get(key) or config.get(split)
    if raw:
        p = Path(raw)
        resolved = p if p.is_absolute() else (root / raw).resolve()
        candidates.append(resolved if resolved.name == "images" else resolved / "images")

    # Direct fallback: images are a sibling of data.yaml
    candidates.append(root / split / "images")
    candidates.append(root / key / "images")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_valid_datasets(datasets_dir: Path, queries: list[str] | None = None) -> list[dict]:
    if queries:
        # Only scan the requested nationality subfolders
        search_roots = [datasets_dir / q for q in queries if (datasets_dir / q).is_dir()]
        unknown = [q for q in queries if not (datasets_dir / q).is_dir()]
        for q in unknown:
            print(f"  WARN folder not found: {datasets_dir / q}")
        yaml_paths = sorted(p for root in search_roots for p in root.rglob("data.yaml"))
    else:
        yaml_paths = sorted(datasets_dir.rglob("data.yaml"))

    result = []
    for yaml_path in yaml_paths:
        with open(yaml_path) as f:
            config = yaml.safe_load(f)

        names = config.get("names") or []
        if not names:
            continue

        # Skip if every label is numeric
        if all(is_numeric(n) for n in names):
            print(f"  SKIP numeric labels  : {yaml_path.parent.name}")
            continue

        # Skip if majority of class names are README/documentation garbage
        garbage_count = sum(1 for n in names if is_garbage(n))
        if garbage_count > len(names) * 0.3:
            print(f"  SKIP garbage labels  : {yaml_path.parent.name} ({garbage_count}/{len(names)} bad)")
            continue

        valid = [
            n for n in names
            if not is_numeric(n)
            and not is_garbage(n)
            and normalize(n) not in SKIP_CLASSES
            and normalize(n) not in NON_FOOD_CLASSES
        ]
        if not valid:
            print(f"  SKIP no food classes : {yaml_path.parent.name}")
            continue

        print(f"  OK  {yaml_path.parent.name} ({len(valid)} classes)")
        result.append({"root": yaml_path.parent, "names": names, "valid": valid, "config": config})

    return result


def build_master_classes(datasets: list[dict]) -> list[str]:
    seen = set()
    for ds in datasets:
        for n in ds["valid"]:
            seen.add(normalize(n))
    return sorted(seen)


def copy_split(ds: dict, split: str, master: list[str], out: Path) -> int:
    images_dir = find_split_dir(ds["root"], ds["config"], split)
    if not images_dir:
        return 0

    labels_dir = images_dir.parent / "labels"
    orig_names = ds["names"]

    # Map original class id → master class id (-1 = skip)
    class_map: dict[int, int] = {}
    for i, name in enumerate(orig_names):
        if is_numeric(name):
            class_map[i] = -1
            continue
        norm = normalize(name)
        class_map[i] = master.index(norm) if norm in master else -1

    out_img = out / split / "images"
    out_lbl = out / split / "labels"
    out_img.mkdir(parents=True, exist_ok=True)
    out_lbl.mkdir(parents=True, exist_ok=True)

    count = 0
    for img in images_dir.iterdir():
        if img.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        label = labels_dir / (img.stem + ".txt")
        if not label.exists():
            continue

        lines = []
        for raw in label.read_text().splitlines():
            parts = raw.strip().split()
            if not parts:
                continue
            try:
                orig_cls = int(parts[0])
            except ValueError:
                continue

            new_cls = class_map.get(orig_cls, -1)
            if new_cls == -1:
                continue

            vals = list(map(float, parts[1:]))
            if len(vals) > 4:
                cx, cy, w, h = seg_to_bbox(vals)
            elif len(vals) == 4:
                cx, cy, w, h = (_clamp01(v) for v in vals)
            else:
                continue

            # Skip degenerate boxes (zero area causes NMS explosion)
            if w <= 0 or h <= 0:
                continue

            lines.append(f"{new_cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

        if not lines:
            continue

        shutil.copy2(img, out_img / img.name)
        (out_lbl / (img.stem + ".txt")).write_text("\n".join(lines) + "\n")
        count += 1

    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", default="../dataset-downloader/datasets",
                        help="Path to downloaded datasets (default: ../dataset-downloader/datasets)")
    parser.add_argument("--out", default="merged_dataset",
                        help="Output directory (default: merged_dataset)")
    parser.add_argument("--query", nargs="*", metavar="FOLDER",
                        help="Nationality folders to include, e.g. thai_food japanese_food "
                             "(default: all folders)")
    parser.add_argument("--clean", action="store_true",
                        help="Delete and recreate the output directory before merging")
    args = parser.parse_args()

    datasets_dir = Path(args.datasets)
    out_dir = Path(args.out)

    if args.clean and out_dir.exists():
        shutil.rmtree(out_dir)
        print(f"Cleaned: {out_dir}")

    if args.query:
        print(f"Scanning queries: {', '.join(args.query)}")
    else:
        print("Scanning datasets (all queries)...")
    datasets = load_valid_datasets(datasets_dir, args.query)
    print(f"\nUsable datasets: {len(datasets)}\n")

    master = build_master_classes(datasets)
    print(f"Total unique food classes: {len(master)}\n")

    out_dir.mkdir(parents=True, exist_ok=True)

    totals: dict[str, int] = {}
    for split in ("train", "valid", "test"):
        n = sum(copy_split(ds, split, master, out_dir) for ds in datasets)
        totals[split] = n

    data_yaml = {
        "path": str(out_dir.resolve()),
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "nc": len(master),
        "names": master,
    }
    (out_dir / "data.yaml").write_text(yaml.dump(data_yaml, allow_unicode=True))

    print("\nMerged dataset summary:")
    for split, n in totals.items():
        print(f"  {split:6s}: {n:,} images")
    print(f"\nClasses ({len(master)}):")
    for i, name in enumerate(master):
        print(f"  {i:3d}: {name}")
    print(f"\nReady → {out_dir}/data.yaml")


if __name__ == "__main__":
    main()
