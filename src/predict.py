import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT = ROOT / "models" / "cancaria_resnet18_final.pth"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

checkpoint = torch.load(CHECKPOINT, map_location=DEVICE, weights_only=True)

CLASSES = checkpoint["classes"]
DISPLAY_NAMES = checkpoint["display_names"]

# Read-only metadata used by the report layer. Added so the API does not have
# to load the checkpoint a second time just to describe the model.
MODEL_INFO = {
    "architecture": checkpoint.get("architecture", "resnet18"),
    "checkpoint": CHECKPOINT.name,
    "image_size": checkpoint["image_size"],
    "classes": CLASSES,
    "display_names": DISPLAY_NAMES,
    "mean": checkpoint["mean"],
    "std": checkpoint["std"],
    "validation_macro_f1": checkpoint.get("best_validation_macro_f1"),
    "validation_loss": checkpoint.get("best_validation_loss"),
    "device": str(DEVICE),
}

model = models.resnet18(weights=None)
model.fc = nn.Sequential(
    nn.Dropout(0.35),
    nn.Linear(model.fc.in_features, len(CLASSES))
)

model.load_state_dict(checkpoint["model_state_dict"])
model.to(DEVICE)
model.eval()

transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(checkpoint["image_size"]),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=checkpoint["mean"],
        std=checkpoint["std"]
    )
])

def predict(image):
    if isinstance(image, (str, Path)):
        image = Image.open(image)

    image = image.convert("RGB")
    tensor = transform(image).unsqueeze(0).to(DEVICE)

    with torch.inference_mode():
        probabilities = torch.softmax(model(tensor), dim=1)[0]

    index = probabilities.argmax().item()

    return {
        "prediction": DISPLAY_NAMES[index],
        "class": CLASSES[index],
        "confidence": round(probabilities[index].item() * 100, 2),
        "scores": {
            DISPLAY_NAMES[i]: round(probabilities[i].item() * 100, 2)
            for i in range(len(CLASSES))
        }
    }