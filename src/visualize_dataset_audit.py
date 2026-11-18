import csv
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "reports" / "clean_manifest.csv"
OUTPUT = ROOT / "reports"

with open(MANIFEST, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))


def create_contact_sheet(records, filename, columns=4):

    cell_w = 220
    cell_h = 220

    total = len(records)
    row_count = (total + columns - 1) // columns

    sheet = Image.new(
        "RGB",
        (columns * cell_w, row_count * cell_h),
        "white"
    )

    draw = ImageDraw.Draw(sheet)

    for index, record in enumerate(records):

        x = (index % columns) * cell_w
        y = (index // columns) * cell_h

        path = ROOT / record["path"]

        try:
            with Image.open(path) as image:
                image = ImageOps.contain(
                    image.convert("RGB"),
                    (cell_w - 20, 165)
                )

            sheet.paste(image, (x + 10, y + 5))

            label = (
                f'{record["split"]} | {record["label"]}\n'
                f'{Path(record["path"]).name}'
            )

            draw.text(
                (x + 5, y + 175),
                label,
                fill="black"
            )

        except Exception as e:
            print(f"Could not load {path}: {e}")

    output_path = OUTPUT / filename
    sheet.save(output_path)

    print(f"Saved: {output_path}")


# Unique Normal images retained by our manifest
normal_images = [
    r for r in rows
    if r["label"] == "normal"
    and r["include"].lower() == "true"
]

normal_images.sort(
    key=lambda r: (
        r["split"],
        r["path"]
    )
)

create_contact_sheet(
    normal_images,
    "normal_unique_images.jpg",
    columns=4
)


# Images sharing identical hashes but having conflicting labels
conflicting_images = [
    r for r in rows
    if r["reason"] == "conflicting_duplicate_labels"
]

create_contact_sheet(
    conflicting_images,
    "conflicting_labels.jpg",
    columns=2
)

print("\nVisual audit completed.")