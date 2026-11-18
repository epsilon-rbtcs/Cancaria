import csv
from pathlib import Path
from collections import defaultdict, Counter

ROOT = Path(__file__).resolve().parent.parent

MANIFEST = ROOT / "reports" / "clean_manifest.csv"

groups = defaultdict(list)

with open(MANIFEST, newline="", encoding="utf-8") as file:
    reader = csv.DictReader(file)

    records = list(reader)

for row in records:
    if row["sha256"]:
        groups[row["sha256"]].append(row)


retained = [
    r for r in records
    if r["include"].lower() == "true"
]

print("\n========== RETENTION SUMMARY ==========")

for label in sorted({r["label"] for r in records}):

    total = sum(r["label"] == label for r in records)

    kept = sum(
        r["label"] == label and
        r["include"].lower() == "true"
        for r in records
    )

    print(f"{label}: {kept}/{total} retained")


print("\n========== EXCLUSION REASONS ==========")

reasons = Counter(
    r["reason"] for r in records
    if r["include"].lower() != "true"
)

for reason, count in reasons.items():
    print(f"{reason}: {count}")


print("\n========== DUPLICATE IMPACT BY CLASS ==========")

impact = Counter()

for group in groups.values():

    if len(group) <= 1:
        continue

    labels = {r["label"] for r in group}

    if len(labels) == 1:
        label = next(iter(labels))
        impact[label] += len(group) - 1


for label, count in impact.items():
    print(f"{label}: {count} duplicate copies removed")


print("\n========== CONFLICTING LABEL GROUPS ==========")

conflicts = 0

for digest, group in groups.items():

    labels = {r["label"] for r in group}

    if len(labels) > 1:

        conflicts += 1

        print(f"\nSHA256: {digest}")

        for row in group:
            print(
                f"Class: {row['label']} | "
                f"Split: {row['split']} | "
                f"Path: {row['path']}"
            )

if conflicts == 0:
    print("No conflicting groups found.")

print("\nTotal conflicting groups:", conflicts)


print("\n========== NORMAL DUPLICATE GROUPS ==========")

for digest, group in groups.items():

    labels = {r["label"] for r in group}

    if labels == {"normal"} and len(group) > 1:

        print(f"\nCopies: {len(group)}")

        for row in group:
            print(f"  [{row['split']}] {row['path']}")


print("\n========== AUDIT COMPLETE ==========")