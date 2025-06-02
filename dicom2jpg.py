import pydicom
from PIL import Image
from pathlib import Path

out_dir = Path("images"); out_dir.mkdir(exist_ok=True)

for dcm in Path(".").rglob("*.dcm"):
    ds = pydicom.dcmread(dcm, stop_before_pixels=False)
    img = Image.fromarray(ds.pixel_array).convert("L")
    img.save(out_dir / f"{dcm.stem}.jpg", quality=92)
