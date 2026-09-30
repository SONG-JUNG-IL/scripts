"""복귀 반영 — 새 PC 에서 바뀐 것만 원 PC 로 옮긴다. 기본은 미리 보기, --apply 일 때만 쓴다.

쓰임::

    python return_apply.py --baseline <manifest_기준_….tsv> --final <manifest_새PC최종_….tsv> --src <새 PC 21차 사본 폴더>
    python return_apply.py … --apply

차례(PC이전_연계방안 §6-3)::

    ① 원 PC 가 기준 목록 그대로인가(volatile 자리는 알림만) — 다르면 멈춘다(--force 로 넘길 수 있음)
    ② 새 PC 사본(--src)에 옮길 파일이 모두 있고 크기가 최종 목록과 같은가
    ③ 차분 = 기준 ↔ 최종 → 이동 · 변경 · 추가 · 삭제
    ④ (--apply) 덮이거나 지워질 원 PC 파일은 _업무 연계_/복귀전백업_시각/ 에 같은 상대경로로 남긴다
       이동 1단계(임시 자리로 뺌) → 삭제(백업 폴더로 옮김) → 이동 2단계(제자리) → 변경 → 추가 → 빈 폴더 정리
       삭제를 추가·이동보다 먼저 하는 까닭: Windows 는 대소문자를 가리지 않아 'a.md' 삭제 + 'A.md' 추가가
       같은 파일을 가리킨다. 추가 뒤에 삭제하면 방금 넣은 새 파일을 지워 버린다.
    ⑤ 최종 목록의 모든 파일을 원 PC 에서 다시 재어 sha1 이 같은지 · 삭제·이동 전 자리가 비었는지(대소문자 구분)
    ⑥ 새 PC 의 _업무 연계_(인계 문서 등)는 목록 밖이라 반영하지 않고, 원 PC _업무 연계_/새PC반납_시각/ 에 따로 둔다

기준 목록에 없던 자리(복사하지 않은 output · _보관_ 등)는 삭제 대상이 될 수 없다. /MIR 을 쓰지 않는다.
종료 코드: 0 = 성공(또는 미리 보기) · 1 = 멈춤/불일치 · 2 = 쓰임 오류.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import _common as C
import manifest as M


def rm_empty_parents(root: Path, rel: str) -> None:
    p = (root / rel).parent
    while p != root and root in p.parents:
        try:
            p.rmdir()          # 비어 있을 때만 지워진다
        except OSError:
            return
        p = p.parent


def backup(root: Path, bdir: Path, rel: str, move: bool) -> None:
    src = root / rel
    if not src.exists():
        return
    dst = bdir / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if move:
        shutil.move(str(src), str(dst))
    else:
        shutil.copy2(src, dst)


def put(src_root: Path, root: Path, rel: str, want: C.Entry) -> None:
    dst = root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_root / rel, dst)
    got = C.sha1_of(dst)
    if got != want.sha1:
        raise OSError(f"복사 뒤 sha1 불일치: {rel}")


def main() -> int:
    C.force_utf8_stdout()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--baseline", required=True, help="복사 직전 원 PC 기준 목록")
    p.add_argument("--final", required=True, help="복귀 직전 새 PC 최종 목록(make --all)")
    p.add_argument("--src", required=True, help="새 PC 21차 폴더 사본(외장 드라이브 등)")
    p.add_argument("--root", default=str(C.DEFAULT_ROOT), help="원 PC 21차 폴더(반영 대상)")
    p.add_argument("--config")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--force", action="store_true", help="① 원 PC 가 기준과 달라도 진행(달라진 파일도 백업한 뒤 덮는다)")
    p.add_argument("--quick", action="store_true", help="① 대조를 크기·수정시각으로(빠름)")
    a = p.parse_args()

    root, src = Path(a.root).resolve(), Path(a.src).resolve()
    if root == src:
        print("🔴 --root 와 --src 가 같습니다", file=sys.stderr)
        return 2
    cfg = C.load_config(Path(a.config) if a.config else None)
    log = C.setup_log("return_apply", root)
    _, base = C.read_manifest(Path(a.baseline))
    fh, final = C.read_manifest(Path(a.final))
    log.info(f"복귀 반영 {'(적용)' if a.apply else '(미리 보기)'} — 원 PC {root} ← 새 PC 사본 {src}")
    log.info(f"기준 {len(base):,}개 · 최종 {len(final):,}개(최종 목록 방식 {fh.get('mode')} · {fh.get('host')} {fh.get('made')})")

    # ① 원 PC 그대로인가
    try:
        drift = M.verify(root, cfg, Path(a.baseline), a.quick, log)
    except C.MeasureError as e:
        log.error(f"🔴 ① 원 PC 를 잴 수 없음 — {e}")
        return 1
    drift_items = [(k, it[0] if k == "moved" else it) for k in ("changed", "added", "deleted", "moved") for it in drift[k]]
    hard = [(k, r) for k, r in drift_items if not C.in_volatile(r, cfg)]
    for k, r in drift_items:
        log.warning(f"  원 PC 가 기준과 다름: {k} {r}{' (저절로 바뀌는 자리)' if C.in_volatile(r, cfg) else ''}")
    if hard and not a.force:
        log.error(f"🔴 원 PC 가 기준 목록과 {len(hard)}건 다릅니다 — 정전 동안 누가 고쳤는지 보고 정한 뒤 --force")
        return 1
    log.info(f"① 원 PC 대조 — 다름 {len(drift_items)}(멈출 것 {len(hard)})")

    # ③ 차분
    d = C.diff(base, final)
    log.info("③ 차분 — " + C.summarize(d))
    for k in ("moved", "changed", "added", "deleted"):
        for it in d[k][:40]:
            log.info(f"   {k:8s} {it}")
        if len(d[k]) > 40:
            log.info(f"   {k:8s} … 외 {len(d[k]) - 40}")

    # ② 새 PC 사본에 필요한 파일
    need = d["changed"] + d["added"] + [t for _, t in d["moved"]]
    lack = [r for r in need if not (src / r).is_file() or (src / r).stat().st_size != final[r].size]
    if lack:
        for r in lack[:30]:
            log.error(f"  새 PC 사본에 없거나 크기 다름: {r}")
        log.error(f"🔴 ② 새 PC 사본이 최종 목록과 다릅니다({len(lack)}건)")
        return 1
    log.info(f"② 새 PC 사본 — 옮길 파일 {len(need):,}개 · {C.fmt_bytes(sum(final[r].size for r in need))} 있음")

    if not a.apply:
        log.info("미리 보기 끝 — 실제 반영은 --apply")
        return 0

    # ②' 쓰기 전에 옮길 파일 sha1 을 모두 확인한다 — 반영 도중 불일치로 멈춰 반쪽 상태가 되는 것을 막는다
    try:
        got = C.measure(src, need, log)
    except C.MeasureError as e:
        log.error(f"🔴 ②' 새 PC 사본을 잴 수 없음 — {e}")
        return 1
    bad_src = [r for r in need if got[r].sha1 != final[r].sha1]
    if bad_src:
        for r in bad_src[:30]:
            log.error(f"  새 PC 사본 sha1 이 최종 목록과 다름: {r}")
        log.error(f"🔴 ②' 새 PC 사본이 최종 목록 뒤에 바뀌었습니다({len(bad_src)}건) — 새 PC 에서 최종 목록을 다시 만드십시오")
        return 1
    log.info(f"②' 새 PC 사본 sha1 확인 {len(need):,}개 — 모두 같음")

    # ④ 적용
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bdir = root / "_업무 연계_" / f"복귀전백업_{ts}"
    stage = bdir / "_이동중"
    log.info(f"④ 적용 — 백업 {bdir}")
    done = {"moved": 0, "moved_as_copy": 0, "changed": 0, "added": 0, "deleted": 0}
    # 이동: 원 PC 파일이 기준과 같으면 옮기고, 아니면 새 PC 사본에서 복사
    staged: list[tuple[str, str]] = []
    for f, t in d["moved"]:
        pf = root / f
        if pf.is_file() and pf.stat().st_size == base[f].size and C.sha1_of(pf) == base[f].sha1:
            backup(root, bdir, f, move=False)
            (stage / t).parent.mkdir(parents=True, exist_ok=True)
            os.replace(pf, stage / t)
            staged.append((f, t))
        else:   # 원 PC 쪽 옛 자리가 기준과 다르거나 없다 → 새 PC 사본에서 가져온다
            backup(root, bdir, f, move=True)
            backup(root, bdir, t, move=True)
            put(src, root, t, final[t])
            done["moved_as_copy"] += 1
        rm_empty_parents(root, f)
    for r in d["deleted"]:
        backup(root, bdir, r, move=True)
        rm_empty_parents(root, r)
        done["deleted"] += 1
    for f, t in staged:
        backup(root, bdir, t, move=True)
        (root / t).parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage / t, root / t)
        done["moved"] += 1
    for r in d["changed"]:
        backup(root, bdir, r, move=False)
        put(src, root, r, final[r])
        done["changed"] += 1
    for r in d["added"]:
        backup(root, bdir, r, move=True)    # 기준 밖에 같은 이름이 있었다면 남긴다
        put(src, root, r, final[r])
        done["added"] += 1
    shutil.rmtree(stage, ignore_errors=True)
    log.info(f"   {done}")

    # ⑤ 검증
    miss = [r for r in final if not (root / r).is_file() or not C.exists_exact(root, r)]
    if miss:
        log.error(f"🔴 ⑤ 최종 목록 파일이 원 PC 에 없음(대소문자 포함) {len(miss)}: {miss[:20]} — 백업 {bdir}")
        return 1
    try:
        now = C.measure(root, sorted(final), log)
    except C.MeasureError as e:
        log.error(f"🔴 ⑤ 원 PC 를 다시 잴 수 없음 — {e}")
        return 1
    bad = [r for r in final if now[r].sha1 != final[r].sha1]
    left = [r for r in d["deleted"] + [f for f, _ in d["moved"]] if C.exists_exact(root, r)]
    rep = {"when": ts, "plan": d, "done": done, "sha1_mismatch": bad, "left_behind": left,
           "backup": str(bdir), "origin_drift": drift_items}
    # ⑥ 새 PC 의 _업무 연계_ 는 따로 보관(원 PC 의 _업무 연계_ 를 덮지 않는다)
    hsrc = src / "_업무 연계_"
    if hsrc.is_dir():
        hdst = root / "_업무 연계_" / f"새PC반납_{ts}"
        shutil.copytree(hsrc, hdst, ignore=shutil.ignore_patterns("세션보관_*", "복귀전백업_*", "새PC반납_*", "__pycache__"))
        log.info(f"⑥ 새 PC _업무 연계_ → {hdst}")
    (bdir / "_복귀기록.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    if bad or left:
        log.error(f"🔴 ⑤ sha1 다름 {len(bad)} · 지워져야 할 자리에 남음 {len(left)} — {bdir / '_복귀기록.json'}")
        return 1
    log.info(f"✅ ⑤ 최종 목록 {len(final):,}개 모두 같음 · 백업 {bdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
