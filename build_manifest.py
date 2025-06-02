import json, argparse, pathlib, PIL.Image as Image

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--images_dir', required=True)
    ap.add_argument('--output',     required=True)
    ap.add_argument('--base_url',   required=True)
    args = ap.parse_args()

    imgs = sorted(pathlib.Path(args.images_dir).glob('*.jpg'))
    canvases = []
    for idx, img_path in enumerate(imgs, 1):
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
                  "type": "Image",
                  "format": "image/jpeg"
                },
                "target": f"{args.base_url}/canvas/{idx}"
              }]
            }]
        })

    manifest = {
      "id": f"{args.base_url}/manifest.json",
      "type": "Manifest",
      "label": { "ko": ["데모 CT 슬라이스"], "en": ["Demo CT Slice"] },
      "items": canvases
    }
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
