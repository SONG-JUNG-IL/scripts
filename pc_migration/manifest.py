"""목록(manifest) 만들기 · 대조 · 차분 — PC 이전·복귀의 판정 기준.

쓰임::

    python manifest.py make   --label 기준                 # 복사 직전(원 PC) — scope 범위
    python manifest.py make   --label 새PC최종 --all         # 복귀 직전(새 PC) — 21차 폴더 전체(exclude 제외)
    python manifest.py verify --manifest <목록.tsv> [--root <폴더>] [--quick] [--ignore-volatile]
    python manifest.py diff   <옛목록.tsv> <새목록.tsv> [--out 차분.json]
    python manifest.py magic  <폴더>                          # hwpx·xlsx·pdf 등 머리 확인(DRM 암호화 의심 파일 찾기)

verify 는 목록에 있는 파일이 모두 같은지 + (목록과 같은 방식으로 걸었을 때) 목록에 없는 파일이 새로 생겼는지를 본다.
종료 코드: 0 = 같음 · 1 = 다름 · 2 = 쓰임 오류.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import _common as C


def cmd_make(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve()
    cfg = C.load_config(Path(a.config) if a.config else None)
    log = C.setup_log(f"manifest_make_{a.label}", root)
    mode = "all" if a.all else "scope"
    log.info(f"목록 만들기 — 뿌리 {root} · 방식 {mode}")
    if mode == "scope":
        miss = C.scope_missing(root, cfg)
        if miss:
            log.warning(f"설정 scope 에 있는데 없는 자리 {len(miss)}: {miss}")
        rels = C.scope_files(root, cfg)
    else:
        rels = C.all_files(root, cfg)
    log.info(f"파일 {len(rels):,}개 — sha1 재는 중")
    t0 = time.time()
    ents = C.measure(root, rels, log)
    out = Path(a.out) if a.out else root / "_업무 연계_" / f"manifest_{a.label}_{datetime.now():%Y%m%d_%H%M%S}.tsv"
    C.write_manifest(out, ents, mode, root)
    log.info(f"✅ 저장 {out} · {len(ents):,}개 · {C.fmt_bytes(sum(e.size for e in ents.values()))} · {time.time() - t0:.0f}초")
    return 0


def verify(root: Path, cfg: dict, manifest: Path, quick: bool, log) -> dict[str, list]:
    """root 의 지금 상태를 목록과 견준 차분을 돌려준다."""
    head, want = C.read_manifest(manifest)
    mode = head.get("mode", "scope")
    rels = C.all_files(root, cfg) if mode == "all" else C.scope_files(root, cfg)
    log.info(f"대조 — 목록 {len(want):,}개({mode}) · 지금 {len(rels):,}개 · {'빠른(크기·시각)' if quick else '전수 sha1'}")
    now = C.measure(root, rels, log, quick_from=want if quick else None)
    return C.diff(want, now)


def cmd_verify(a: argparse.Namespace) -> int:
    root = Path(a.root).resolve()
    cfg = C.load_config(Path(a.config) if a.config else None)
    log = C.setup_log("manifest_verify", root)
    d = verify(root, cfg, Path(a.manifest), a.quick, log)
    log.info("결과 — " + C.summarize(d))
    bad = 0
    for kind in ("changed", "added", "deleted", "moved"):
        for item in d[kind]:
            rel = item[0] if kind == "moved" else item
            vol = C.in_volatile(rel, cfg)
            if not (vol and a.ignore_volatile):
                bad += 1
            tag = "(저절로 바뀌는 자리)" if vol else ""
            if bad <= 200 or vol:
                log.warning(f"  {kind:8s} {item} {tag}")
    rep = root / "_업무 연계_" / "logs" / f"verify_{datetime.now():%Y%m%d_%H%M%S}.json"
    rep.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    if bad:
        log.error(f"🔴 다름 {bad}건 — 자세한 목록 {rep}")
        return 1
    log.info("✅ 목록과 같다")
    return 0


def cmd_diff(a: argparse.Namespace) -> int:
    _, old = C.read_manifest(Path(a.old))
    _, new = C.read_manifest(Path(a.new))
    d = C.diff(old, new)
    print(C.summarize(d))
    if a.out:
        Path(a.out).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"저장 {a.out}")
    else:
        for k in ("moved", "changed", "added", "deleted"):
            for item in d[k][:50]:
                print(f"  {k:8s} {item}")
    return 0


def cmd_magic(a: argparse.Namespace) -> int:
    """폴더 아래 파일의 머리가 확장자와 맞는지 본다. 종료 코드 0 = 모두 맞음 · 1 = 의심 있음."""
    base = Path(a.folder).resolve()
    n = 0
    odd: list[tuple[str, str]] = []
    for p in sorted(base.rglob("*")):
        if p.is_file() and p.suffix.lower() in C.MAGIC:
            n += 1
            m = C.magic_mismatch(p)
            if m:
                odd.append((str(p.relative_to(base)), m))
    for r, m in odd:
        print(f"  🔴 {r}  [{m}]")
    print(f"{'🔴 의심' if odd else '✅ 모두 맞음'} {len(odd)} / 검사 {n}개 — {base}")
    return 1 if odd else 0


def main() -> int:
    C.force_utf8_stdout()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="설정 JSON(기본 tools/이전설정.json)")
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--label", default="기준")
    m.add_argument("--all", action="store_true", help="21차 폴더 전체(exclude 만 적용) — 새 PC 최종 목록")
    m.add_argument("--root", default=str(C.DEFAULT_ROOT))
    m.add_argument("--out")
    v = sub.add_parser("verify")
    v.add_argument("--manifest", required=True)
    v.add_argument("--root", default=str(C.DEFAULT_ROOT))
    v.add_argument("--quick", action="store_true", help="크기·수정시각이 같으면 sha1 을 다시 읽지 않는다")
    v.add_argument("--ignore-volatile", action="store_true", help="설정 volatile 자리의 차이는 멈추지 않는다")
    d = sub.add_parser("diff")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("--out")
    g = sub.add_parser("magic")
    g.add_argument("folder")
    a = p.parse_args()
    try:
        return {"make": cmd_make, "verify": cmd_verify, "diff": cmd_diff, "magic": cmd_magic}[a.cmd](a)
    except C.MeasureError as e:        # 잠긴 파일 등 — 목록을 반쪽으로 남기지 않는다
        print(f"🔴 {e}", file=sys.stderr)
        return 1
    except (FileNotFoundError, ValueError) as e:
        print(f"🔴 {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
