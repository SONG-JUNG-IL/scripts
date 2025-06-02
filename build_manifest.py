import json, argparse, pathlib
from biiif import Builder            # 간단한 빌더

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--images_dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--base_url", required=True)
    args = p.parse_args()

    imgs = sorted(pathlib.Path(args.images_dir).glob("*.jpg"))
    b = Builder(label="Demo CT Slice",
                id=f"{args.base_url}/manifest.json")

    for idx, img in enumerate(imgs, 1):
        b.add_canvas(
            # 자동 width/height 계산
            identifier=f"{args.base_url}/canvas/{idx}",
            img=img,
            label=f"slice {idx}"
        )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(b.build(), f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
