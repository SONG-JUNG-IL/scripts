import pydicom, numpy as np
from PIL import Image
from pathlib import Path

OUT_DIR = Path("images")
OUT_DIR.mkdir(exist_ok=True)

for dcm in Path(".").rglob("*.dcm"):
    ds = pydicom.dcmread(dcm, stop_before_pixels=False)
    arr = ds.pixel_array
    img = Image.fromarray(arr).convert("L")  # 8-bit 그레이
    out_path = OUT_DIR / f"{dcm.stem}.jpg"
    img.save(out_path, quality=92)
    print(f"✔ {dcm.name} → {out_path}")
