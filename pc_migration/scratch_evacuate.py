"""세션 임시 폴더(scratchpad)에서 남길 것만 21차 안(_업무 연계_/세션보관_날짜/)으로 옮겨 적는다(복사 · 원본은 그대로).

쓰임::

    python scratch_evacuate.py                    # 미리 보기 — 넣을 것 · 뺄 것 · 미분류 폴더와 크기
    python scratch_evacuate.py --apply            # 복사 + 세션보관/_목록.md
    python scratch_evacuate.py --apply --with-unclassified   # 미분류 폴더도 넣는다

넣고 뺄 폴더는 이전설정.json 의 scratch.sessions 에서 고친다. 낱개 파일(폴더 밖)은 loose_files=true 면 모두 넣는다.
session 에 '*' 를 쓰면 그 프로젝트의 모든 세션을 세션 ID 별 하위 폴더로 대피한다(새 PC 는 세션 ID 를 몰라도 된다).
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

import _common as C


def dir_size(p: Path) -> tuple[int, int]:
    n = b = 0
    for f in p.rglob("*"):
        if f.is_file():
            n += 1
            b += f.stat().st_size
    return n, b


def find_scratch(cfg: dict, s: dict) -> list[tuple[str, Path]]:
    """(세션 ID, scratchpad 경로) 목록. session 이 정확한 ID 면 하나, '*' 같은 무늬면 맞는 것 모두."""
    base = Path(C.expand(cfg["scratch"]["temp_base"]))
    found: list[tuple[str, Path]] = []
    for proj in sorted(base.glob(s["project_like"])):
        for sd in sorted(proj.glob(s["session"])):
            if (sd / "scratchpad").is_dir():
                found.append((sd.name, sd / "scratchpad"))
    if not any(ch in s["session"] for ch in "*?["):
        found = found[:1]
    return found


def main() -> int:
    C.force_utf8_stdout()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=str(C.DEFAULT_ROOT))
    p.add_argument("--config")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--with-unclassified", action="store_true")
    p.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    a = p.parse_args()
    root = Path(a.root).resolve()
    cfg = C.load_config(Path(a.config) if a.config else None)
    log = C.setup_log("scratch_evacuate", root)
    dest_root = root / cfg["scratch"]["dest"].format(date=a.date)
    index: list[str] = [f"# 세션보관 — {datetime.now():%Y-%m-%d %H:%M:%S}", ""]
    total_b = 0
    jobs: list[tuple[dict, str, Path]] = []
    for s in cfg["scratch"]["sessions"]:
        hits = find_scratch(cfg, s)
        if not hits:
            log.warning(f"{s['name']}: 임시 폴더를 찾지 못함 ({s['project_like']}/{s['session']})")
        wild = any(ch in s["session"] for ch in "*?[")
        jobs += [(s, f"{s['name']}/{sid}" if wild else s["name"], sp) for sid, sp in hits]
    for s, oname, sp in jobs:
        log.info(f"── {oname} — {sp}")
        inc, exc = set(s.get("include_dirs", [])), set(s.get("exclude_dirs", []))
        take_dirs: list[Path] = []
        for d in sorted(x for x in sp.iterdir() if x.is_dir()):
            n, b = dir_size(d)
            if d.name in inc:
                kind = "넣음"
                take_dirs.append(d)
            elif d.name in exc:
                kind = "뺌"
            else:
                kind = "미분류→넣음" if a.with_unclassified else "미분류(뺌)"
                if a.with_unclassified:
                    take_dirs.append(d)
            if kind != "뺌" or b > 50 * 2**20:
                log.info(f"  [{kind:9s}] {d.name:40s} {n:6,}개 {C.fmt_bytes(b):>10s}")
        for missing in sorted(inc - {d.name for d in sp.iterdir() if d.is_dir()}):
            log.warning(f"  설정의 include_dirs 에 있는데 없음: {missing}")
        loose = sorted(f for f in sp.iterdir() if f.is_file()) if s.get("loose_files") else []
        lb = sum(f.stat().st_size for f in loose)
        db = sum(dir_size(d)[1] for d in take_dirs)
        total_b += lb + db
        log.info(f"  낱개 파일 {len(loose):,}개 {C.fmt_bytes(lb)} · 넣을 폴더 {len(take_dirs)}개 {C.fmt_bytes(db)}")
        index += [f"## {oname}", f"- 원래 자리: `{sp}`", f"- 낱개 파일 {len(loose)}개 · 폴더: "
                  + ", ".join(d.name for d in take_dirs), ""]
        if a.apply:
            out = dest_root / oname
            out.mkdir(parents=True, exist_ok=True)
            for f in loose:
                shutil.copy2(f, out / f.name)
            for d in take_dirs:
                shutil.copytree(d, out / d.name, dirs_exist_ok=True)
    log.info(f"합계 {C.fmt_bytes(total_b)} → {dest_root}")
    if a.apply:
        (dest_root / "_목록.md").write_text("\n".join(index) + "\n", encoding="utf-8")
        log.info("✅ 복사 끝(원본 임시 폴더는 그대로)")
    else:
        log.info("미리 보기 끝 — 실제 복사는 --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
