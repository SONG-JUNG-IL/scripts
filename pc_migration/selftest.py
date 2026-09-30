"""가짜 폴더로 이전·복귀 전 과정을 돌려 보는 자기 시험 — 실제 21차 폴더는 읽지도 쓰지도 않는다.

쓰임::

    python selftest.py            # 임시 폴더에서 시험하고 지운다
    python selftest.py --keep     # 시험 폴더를 남긴다(들여다보기용)

시나리오:
    A  기준 목록 → robocopy 복사(--apply --verify) → 대상 대조 ✅
    B  새 PC 에서 변경 · 추가 · 이동 · 맞바꿈 · 삭제 · 제외 자리 · volatile → 최종 목록 → 복귀 미리 보기 → 적용 → 전수 같음 ✅
       + 복사하지 않은 원 PC 자리(output · _보관_ · 옛 산출)가 그대로 남는가
    C  원 PC 가 정전 중 바뀌었으면 멈추는가(종료 1) · volatile 만 바뀌었으면 넘어가는가
    D  새 PC 사본에 파일이 빠졌으면 멈추는가
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _common as C

TOOLS = Path(__file__).resolve().parent
PY = sys.executable
results: list[tuple[bool, str]] = []


def check(ok: bool, what: str) -> None:
    results.append((ok, what))
    print(f"{'✅' if ok else '🔴'} {what}")


def w(root: Path, rel: str, text: str | bytes) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    (p.write_bytes if isinstance(text, bytes) else lambda t: p.write_text(t, encoding="utf-8"))(text)


def run(script: str, *args: str) -> int:
    r = subprocess.run([PY, str(TOOLS / script), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-6:])
    print(f"   $ {script} {' '.join(a if len(a) < 60 else '…' + a[-40:] for a in args)} → rc={r.returncode}\n"
          + "\n".join("     " + t for t in tail.splitlines()))
    return r.returncode


def build_origin(root: Path) -> None:
    w(root, "DICOCH_Tool_정본/DICOCH_Tool/app/a.py", "A = 1\n")
    w(root, "DICOCH_Tool_정본/DICOCH_Tool/app/b.py", "B = 2\n")
    w(root, "DICOCH_Tool_정본/DICOCH_Tool/tools/t.py", "print('t')\n")
    w(root, "DICOCH_Tool_정본/DICOCH_Tool/tools/__pycache__/t.cpython-314.pyc", b"\0pyc")
    w(root, "DICOCH_Tool_정본/DICOCH_Tool/output/원래산출.txt", "원 PC 에만 있는 산출\n")
    w(root, "DICOCH_Tool_정본/DICOCH_Tool/logs/l.log", "log\n")
    w(root, "DICOCH_Tool_정본/DICOCH_Tool/dist/_대장.md", "# 대장 ver241\n")
    w(root, "DICOCH_Tool_정본/코드 시연/캡처/cap54.py", "NEUTRAL = 'X:'\n")
    w(root, "MD/지침서 작업본.md", "# 지침서 μ ρ Σ ± ² ³\n")
    w(root, "MD/빈파일.md", "")
    w(root, "데이터/양식_rev50.xlsx", os.urandom(2048))
    w(root, "데이터/TEST_하회탈/데이터/CT_1/img.bin", os.urandom(3 * 2**20))
    w(root, "데이터/실증산출_옛/y.txt", "복사하지 않는 옛 산출\n")
    w(root, "_보관_구판/z.txt", "복사하지 않는 보관본\n")
    w(root, ".bkit/runtime/r.json", '{"n": 1}\n')
    w(root, "쪽번호.bat", "@echo off\n")


def make_cfg(tmp: Path) -> Path:
    cfg = C.load_config()
    cfg["scope"] = [
        {"path": "DICOCH_Tool_정본"}, {"path": "MD"}, {"path": "데이터", "files_only": True},
        {"path": "데이터/TEST_하회탈"}, {"path": ".bkit"}, {"path": ".", "files_only": True},
        {"path": "_업무 연계_", "manifest": False},
    ]
    p = tmp / "시험설정.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def latest(root: Path, label: str) -> Path:
    return sorted((root / "_업무 연계_").glob(f"manifest_{label}_*.tsv"))[-1]


def main() -> int:
    C.force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    tmp = Path(tempfile.mkdtemp(prefix="DICOCH_이전시험_"))
    orig, newpc, back = tmp / "원PC" / "21차_20260824", tmp / "외장" / "21차_20260824", tmp / "새PC반납" / "21차_20260824"
    print(f"시험 폴더 {tmp}")
    try:
        build_origin(orig)
        cfgp = str(make_cfg(tmp))

        print("\n── A 기준 목록 · 복사 · 대조")
        check(run("manifest.py", "--config", cfgp, "make", "--label", "기준", "--root", str(orig)) == 0, "A1 기준 목록 만들기")
        base = latest(orig, "기준")
        _, be = C.read_manifest(base)
        check("DICOCH_Tool_정본/DICOCH_Tool/output/원래산출.txt" not in be and not any("__pycache__" in r for r in be)
              and "_보관_구판/z.txt" not in be and "데이터/실증산출_옛/y.txt" not in be, "A2 제외 규칙(output · __pycache__ · 범위 밖)")
        check("쪽번호.bat" in be and "데이터/양식_rev50.xlsx" in be and "MD/빈파일.md" in be, "A3 files_only · 빈 파일 포함")
        check(run("copy_out.py", "--config", cfgp, "--root", str(orig), "--dest", str(newpc)) == 0
              and not newpc.exists(), "A4 미리 보기는 아무것도 쓰지 않음")
        check(run("copy_out.py", "--config", cfgp, "--root", str(orig), "--dest", str(newpc), "--apply", "--verify") == 0,
              "A5 복사 + 대상 전수 대조")
        check((newpc / "_업무 연계_").is_dir() and not (newpc / "DICOCH_Tool_정본/DICOCH_Tool/output").exists(),
              "A6 _업무 연계_ 는 가고 output 은 안 감")
        st_o = (orig / "MD/지침서 작업본.md").stat().st_mtime_ns
        st_n = (newpc / "MD/지침서 작업본.md").stat().st_mtime_ns
        check(abs(st_o - st_n) < 20_000_000, "A7 수정시각 보존")

        print("\n── B 새 PC 작업 → 복귀")
        w(newpc, "MD/지침서 작업본.md", "# 지침서 — 새 PC 에서 고침\n")                       # 변경
        w(newpc, "데이터/실증산출_새PC/n.txt", "새 산출\n")                                   # 추가(새 폴더)
        w(newpc, "DICOCH_Tool_정본/DICOCH_Tool/dist/DICOCH_Tool_ver242.zip", os.urandom(4096))  # 추가(dist)
        (newpc / "데이터/_보관_구판").mkdir(parents=True)
        os.replace(newpc / "데이터/양식_rev50.xlsx", newpc / "데이터/_보관_구판/양식_rev50.xlsx")  # 이동
        a_, b_ = newpc / "DICOCH_Tool_정본/DICOCH_Tool/app/a.py", newpc / "DICOCH_Tool_정본/DICOCH_Tool/app/b.py"
        os.replace(a_, a_.with_suffix(".tmp")); os.replace(b_, a_); os.replace(a_.with_suffix(".tmp"), b_)  # 맞바꿈
        os.remove(newpc / "DICOCH_Tool_정본/DICOCH_Tool/tools/t.py")                          # 삭제
        w(newpc, "DICOCH_Tool_정본/DICOCH_Tool/output/새산출.txt", "돌아가면 안 됨\n")            # 제외 자리
        w(newpc, ".bkit/runtime/r.json", '{"n": 2}\n')                                       # volatile
        check(run("manifest.py", "--config", cfgp, "make", "--label", "새PC최종", "--all", "--root", str(newpc)) == 0, "B1 새 PC 최종 목록(--all)")
        final = latest(newpc, "새PC최종")
        _, fe = C.read_manifest(final)
        check("DICOCH_Tool_정본/DICOCH_Tool/output/새산출.txt" not in fe, "B2 최종 목록도 output 제외")
        d = C.diff(be, fe)
        check(len(d["moved"]) == 1 and len(d["deleted"]) == 1 and len(d["added"]) == 2 and len(d["changed"]) == 4,
              f"B3 차분 분류 — {C.summarize(d)} (기대: 이동 1[양식] · 삭제 1 · 추가 2 · 변경 4[md · volatile · 맞바꿈 둘])")
        # 새 PC → 외장 반납 사본(실제 흐름처럼 다른 자리)
        shutil.copytree(newpc, back)
        common = ["--config", cfgp, "--baseline", str(base), "--final", str(final), "--src", str(back), "--root", str(orig)]
        snap = sorted(str(p) for p in orig.rglob("*"))
        check(run("return_apply.py", *common) == 0 and sorted(str(p) for p in orig.rglob("*") if "_업무 연계_" not in str(p))
              == [s for s in snap if "_업무 연계_" not in s], "B4 복귀 미리 보기는 원 PC 를 바꾸지 않음")
        check(run("return_apply.py", *common, "--apply") == 0, "B5 복귀 적용 + 전수 검증")
        same = all(C.sha1_of(orig / r) == fe[r].sha1 for r in fe)
        check(same, "B6 원 PC 가 새 PC 최종 목록과 파일마다 같음")
        check((orig / "DICOCH_Tool_정본/DICOCH_Tool/app/a.py").read_text(encoding="utf-8") == "B = 2\n", "B7 맞바꿈 반영")
        check(not (orig / "DICOCH_Tool_정본/DICOCH_Tool/tools/t.py").exists()
              and any((orig / "_업무 연계_").glob("복귀전백업_*/DICOCH_Tool_정본/DICOCH_Tool/tools/t.py")), "B8 삭제는 백업 폴더로 옮김")
        check((orig / "DICOCH_Tool_정본/DICOCH_Tool/output/원래산출.txt").exists() and (orig / "_보관_구판/z.txt").exists()
              and (orig / "데이터/실증산출_옛/y.txt").exists() and (orig / "DICOCH_Tool_정본/DICOCH_Tool/logs/l.log").exists()
              and not (orig / "DICOCH_Tool_정본/DICOCH_Tool/output/새산출.txt").exists(), "B9 복사 안 한 원 PC 자리 보존 · 새 PC output 안 옴")
        check(any((orig / "_업무 연계_").glob("복귀전백업_*/MD/지침서 작업본.md")), "B10 덮인 파일 백업")

        print("\n── C 원 PC 가 정전 중 바뀐 경우")
        orig2 = tmp / "원PC2" / "21차_20260824"
        build_origin(orig2)
        check(run("manifest.py", "--config", cfgp, "make", "--label", "기준", "--root", str(orig2)) == 0, "C0 기준")
        base2 = latest(orig2, "기준")
        w(orig2, ".bkit/runtime/r.json", '{"n": 9}\n')
        c2 = ["--config", cfgp, "--baseline", str(base2), "--final", str(base2), "--src", str(back), "--root", str(orig2)]
        check(run("return_apply.py", *c2) == 0, "C1 volatile 만 바뀌면 멈추지 않음")
        w(orig2, "MD/지침서 작업본.md", "정전 중 누가 고침\n")
        check(run("return_apply.py", *c2) == 1, "C2 일반 파일이 바뀌면 멈춤(종료 1)")
        check(run("manifest.py", "--config", cfgp, "verify", "--manifest", str(base2), "--root", str(orig2)) == 1, "C3 verify 도 다름으로 봄")

        print("\n── D 새 PC 사본에 파일이 빠진 경우")
        os.remove(back / "데이터/실증산출_새PC/n.txt")
        orig3 = tmp / "원PC3" / "21차_20260824"
        build_origin(orig3)
        run("manifest.py", "--config", cfgp, "make", "--label", "기준", "--root", str(orig3))
        c3 = ["--config", cfgp, "--baseline", str(latest(orig3, "기준")), "--final", str(final), "--src", str(back), "--root", str(orig3)]
        check(run("return_apply.py", *c3, "--apply") == 1 and (orig3 / "MD/지침서 작업본.md").read_text(encoding="utf-8").startswith("# 지침서 μ"),
              "D1 사본이 모자라면 아무것도 바꾸지 않고 멈춤")
    finally:
        if a.keep:
            print(f"\n시험 폴더 남김: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    bad = [w_ for ok, w_ in results if not ok]
    print(f"\n{'✅ 모두 통과' if not bad else '🔴 실패 ' + str(len(bad))} — {len(results) - len(bad)}/{len(results)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
