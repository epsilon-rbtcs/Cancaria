from pathlib import Path
from collections import Counter, defaultdict
from PIL import Image
import hashlib

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "Data"

SPLITS = ["train", "valid", "test"]

CLASSES = [
    "adenocarcinoma",
    "large.cell.carcinoma",
    "normal",
    "squamous.cell.carcinoma",
]

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp",
    ".tif", ".tiff", ".webp"
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
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(chunk)

    return sha.hexdigest()


def inspect_dataset():

    if not DATA_DIR.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_DIR}")

    counts = {
        split: Counter() for split in SPLITS
    }

    corrupted = []
    unknown_folders = []
    dimensions = Counter()
    hashes = defaultdict(list)

    total_images = 0

    print("\n========== DATASET INSPECTION ==========\n")

    for split in SPLITS:

        split_dir = DATA_DIR / split

        if not split_dir.exists():
            print(f"WARNING: Missing split: {split}")
            continue

        print(f"\n--- {split.upper()} ---")

        for class_dir in sorted(split_dir.iterdir()):

            if not class_dir.is_dir():
                continue

            label = identify_class(class_dir.name)

            if label is None:
                unknown_folders.append(class_dir.name)
                continue

            image_paths = [
                p for p in class_dir.rglob("*")
                if p.is_file()
                and p.suffix.lower() in IMAGE_EXTENSIONS
            ]

            valid_count = 0

            for path in image_paths:

                try:
                    with Image.open(path) as image:
                        dimensions[image.size] += 1
                        image.verify()

                    image_hash = calculate_hash(path)

                    hashes[image_hash].append(
                        (split, str(path))
                    )

                    valid_count += 1

                except Exception:
                    corrupted.append(str(path))

            counts[split][label] += valid_count
            total_images += valid_count

            print(f"{class_dir.name}: {valid_count}")

    print("\n========== CLASS DISTRIBUTION ==========")

    for split in SPLITS:

        print(f"\n{split.upper()}:")

        for label in CLASSES:
            print(f"  {label:<30} {counts[split][label]}")

        print(f"  TOTAL: {sum(counts[split].values())}")

    print("\n========== SUMMARY ==========")

    print(f"Total valid images: {total_images}")
    print(f"Unique image dimensions: {len(dimensions)}")

    print("\nMost common dimensions:")

    for size, count in dimensions.most_common(10):
        print(f"  {size}: {count}")

    print(f"\nCorrupted images: {len(corrupted)}")

    for path in corrupted[:10]:
        print(f"  {path}")

    cross_split_duplicates = []

    for files in hashes.values():
        splits_found = {split for split, _ in files}

        if len(splits_found) > 1:
            cross_split_duplicates.append(files)

    print(
        "\nExact duplicate images across splits:",
        len(cross_split_duplicates)
    )

    for group in cross_split_duplicates[:10]:
        for split, path in group:
            print(f"  [{split}] {path}")

    if unknown_folders:
        print("\nUnknown folders:")

        for folder in unknown_folders:
            print(f"  {folder}")

    print("\n========== INSPECTION COMPLETE ==========")


if __name__ == "__main__":
    inspect_dataset()