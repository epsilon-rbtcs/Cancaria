from pathlib import Path
from collections import defaultdict, Counter
from PIL import Image
import hashlib
import csv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "Data"
OUTPUT_DIR = ROOT / "reports"

SPLITS = ["train", "valid", "test"]

CLASSES = [
    "adenocarcinoma",
    "large.cell.carcinoma",
    "normal",
    "squamous.cell.carcinoma",
]

EXTENSIONS = {
    ".jpg", ".jpeg", ".png",
    ".bmp", ".tif", ".tiff", ".webp"
}

# Lower number = higher priority
PRIORITY = {
    "test": 0,
    "valid": 1,
    "train": 2
}


def identify_class(folder_name):

    name = folder_name.lower()

    for class_name in CLASSES:
        if name.startswith(class_name):
            return class_name

    return None


def calculate_hash(path):

    sha = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024), b""
        ):
            sha.update(chunk)

    return sha.hexdigest()


def create_manifest():

    OUTPUT_DIR.mkdir(exist_ok=True)

    records = []
    groups = defaultdict(list)
    unknown_folders = []

    print("\nScanning dataset...")

    for split in SPLITS:

        split_dir = DATA_DIR / split

        for class_dir in sorted(split_dir.iterdir()):

            if not class_dir.is_dir():
                continue

            label = identify_class(class_dir.name)

            if label is None:
                unknown_folders.append(class_dir.name)
                continue

            for path in class_dir.rglob("*"):

                if not path.is_file():
                    continue

                if path.suffix.lower() not in EXTENSIONS:
                    continue

                record = {
                    "split": split,
                    "label": label,
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": "",
                    "include": False,
                    "reason": ""
                }

                try:
                    with Image.open(path) as image:
                        image.verify()

                    digest = calculate_hash(path)

                    record["sha256"] = digest
                    groups[digest].append(record)

                except Exception:
                    record["reason"] = "corrupted_image"

                records.append(record)

    duplicate_groups = 0
    cross_split_groups = 0
    conflict_groups = 0

    for group in groups.values():

        if len(group) > 1:
            duplicate_groups += 1

        labels = {item["label"] for item in group}

        if len(labels) > 1:

            conflict_groups += 1

            for item in group:
                item["reason"] = "conflicting_duplicate_labels"

            continue

        if len({item["split"] for item in group}) > 1:
            cross_split_groups += 1

        group.sort(
            key=lambda item: (
                PRIORITY[item["split"]],
                item["path"].lower()
            )
        )

        # Retain exactly one copy
        group[0]["include"] = True
        group[0]["reason"] = "retained_unique_image"

        for duplicate in group[1:]:

            duplicate["reason"] = (
                f"duplicate_of_{group[0]['split']}"
            )

    # Save complete manifest
    output_file = OUTPUT_DIR / "clean_manifest.csv"

    with open(
        output_file,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "split",
                "label",
                "path",
                "sha256",
                "include",
                "reason"
            ]
        )

        writer.writeheader()
        writer.writerows(records)

    # Print retained image distribution
    retained = [
        item for item in records
        if item["include"]
    ]

    print("\n========== CLEAN DATASET ==========")

    counts = defaultdict(Counter)

    for item in retained:
        counts[item["split"]][item["label"]] += 1

    for split in SPLITS:

        print(f"\n{split.upper()}")

        for label in CLASSES:
            print(f"  {label}: {counts[split][label]}")

        print(f"  TOTAL: {sum(counts[split].values())}")

    print("\n========== DUPLICATE ANALYSIS ==========")

    print(f"Total original images: {len(records)}")
    print(f"Duplicate groups: {duplicate_groups}")
    print(f"Cross-split duplicate groups: {cross_split_groups}")
    print(f"Conflicting-label groups: {conflict_groups}")
    print(f"Retained images: {len(retained)}")
    print(f"Excluded images: {len(records) - len(retained)}")

    print(f"\nManifest saved to: {output_file}")

    if unknown_folders:
        print("\nUnknown folders:", unknown_folders)


if __name__ == "__main__":
    create_manifest()