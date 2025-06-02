import json, argparse, pathlib, PIL.Image as Image

p = argparse.ArgumentParser()
p.add_argument("--images_dir","--images", required=True)
p.add_argument("--output",     required=True)
p.add_argument("--base_url",   required=True)
args = p.parse_args()

canvases = []
for idx, img_path in enumerate(sorted(pathlib.Path(args.images_dir).glob("*.jpg")), 1):
    w, h = Image.open(img_path).size
    canvases.append({
      "id": f"{args.base_url}/canvas/{idx}",
      "type": "Canvas",
      "width": w, "height": h,
      "items": [{
        "type": "AnnotationPage",
        "items": [{
          "type": "Annotation",
          "motivation": "painting",
          "body": {
            "id": f"{args.base_url}/{img_path}",
            "type": "Image", "format": "image/jpeg"
          },
          "target": f"{args.base_url}/canvas/{idx}"
        }]
      }]
    })

manifest = {
  "id": f"{args.base_url}/manifest.json",
  "type": "Manifest",
  "label": { "ko": ["데모 CT"], "en": ["Demo CT"] },
  "items": canvases
}

with open(args.output, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
