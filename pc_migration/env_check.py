"""실행 환경 점검 — 원 PC 에서 기준을 뜨고(--save-reference), 새 PC 에서 같은지 본다.

쓰임::

    python env_check.py --save-reference     # 원 PC: _업무 연계_/환경_기준.json + pip_freeze_기준.txt
    python env_check.py                      # 새 PC: 기준과 견준다(기준 파일이 없으면 설정값과 견준다)

종료 코드: 0 = 🔴 없음 · 1 = 🔴 있음.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

import _common as C

OK, WARN, BAD = "✅", "⚠", "🔴"
EXPECTED_ROOT = r"C:\Users\WIN11PRO_512\claude-work3\DICOCH 설계명세서 설명\21차_20260824"


def run(cmd: list[str], timeout: int = 60) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def pip_freeze() -> dict[str, str]:
    rc, out = run([sys.executable, "-m", "pip", "freeze"], 120)
    pk: dict[str, str] = {}
    for line in out.splitlines():
        if "==" in line:
            n, v = line.split("==", 1)
            pk[n.strip().lower()] = v.strip()
    return pk


def claude_enc(path: str) -> str:
    """Claude Code 가 프로젝트 경로로 만드는 폴더 이름(영문·숫자 외는 '-')."""
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def find_bash() -> str | None:
    for c in (shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe",
              r"C:\Program Files\Git\usr\bin\bash.exe"):
        if c and Path(c).is_file() and "System32" not in c:
            return c
    return None


def display_scale() -> int | None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass
    try:
        return round(ctypes.windll.user32.GetDpiForSystem() * 100 / 96)
    except (AttributeError, OSError):
        return None


def hwp_com() -> bool:
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "HWPFrame.HwpObject"))
        return True
    except OSError:
        return False


def long_paths() -> int | None:
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem")
        return int(winreg.QueryValueEx(k, "LongPathsEnabled")[0])
    except OSError:
        return None


def mermaid_ok(spec: str) -> tuple[bool, str]:
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        return False, "npx 없음"
    rc, out = run([npx, "--no-install", spec, "--version"], 120)
    return rc == 0, out.splitlines()[-1] if out else f"rc={rc}"


def collect(root: Path, cfg: dict) -> dict:
    env = cfg["env"]
    home = Path.home() / ".claude"
    dc = shutil.which("dciodvfy")
    ev = os.environ.get("DICOCH_DCIODVFY")
    if not dc and ev:        # 환경변수는 가리키는 파일이 실제로 있어야 인정한다
        dc = ev if Path(ev).is_file() else None
    if not dc and (Path(env["dicom3tools_dir"]) / "dciodvfy.exe").is_file():
        dc = str(Path(env["dicom3tools_dir"]) / "dciodvfy.exe") + " (PATH 밖)"
    mm_ok, mm_txt = mermaid_ok(env["mermaid_cli"])
    node = run(["node", "--version"])[1] if shutil.which("node") else None
    # settings.json 이 부르는 절대 경로들
    refs: list[str] = []
    sj = home / "settings.json"
    if sj.is_file():
        txt = sj.read_text(encoding="utf-8", errors="replace")
        refs = sorted(set(m.replace("\\\\", "\\") for m in re.findall(r'[A-Za-z]:\\\\[^"]+?\.(?:ps1|exe|cmd|bat|py)', txt)))
        refs += [m.replace("\\\\", "\\") for m in re.findall(r'"path"\s*:\s*"([A-Za-z]:\\\\[^"]+)"', txt)]
    mem = {}
    for sub in ("", "DICOCH_Tool_정본"):
        p = str(root / sub) if sub else str(root)
        d = home / "projects" / claude_enc(p) / "memory"
        mem[p] = len(list(d.glob("*.md"))) if d.is_dir() else 0
    wr = False
    try:
        t = root / "_업무 연계_" / "logs" / "_쓰기시험.tmp"
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text("x", encoding="utf-8")
        t.unlink()
        wr = True
    except OSError:
        pass
    try:
        admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        admin = None
    return {
        "host": platform.node(), "user": os.environ.get("USERNAME"),
        "root": str(root), "root_same_path": str(root).lower() == EXPECTED_ROOT.lower(),
        "root_writable": wr, "admin": admin,
        "python": platform.python_version(), "python_exe": sys.executable,
        "pip": pip_freeze(),
        "dciodvfy": dc, "node": node, "mermaid": mm_txt if mm_ok else None,
        "bash": find_bash(), "subst": bool(shutil.which("subst")),
        "hwp_com": hwp_com(), "font_malgun": Path(r"C:\Windows\Fonts\malgun.ttf").is_file(),
        "display_scale": display_scale(), "long_paths": long_paths(),
        "claude_home": {f: (home / f).exists() for f in env["claude_home_files"] + env["claude_home_dirs"]},
        "claude_settings_refs": {r: Path(r).exists() for r in refs},
        "bkit_source": Path(env["bkit_source"]).is_dir(),
        "claude_memory": mem,
    }


def judge(cur: dict, ref: dict | None, cfg: dict) -> list[tuple[str, str, str]]:
    env = cfg["env"]
    rows: list[tuple[str, str, str]] = []
    add = lambda s, k, m: rows.append((s, k, m))  # noqa: E731
    want_py = ref["python"] if ref else env["python"]
    # 부 판(3.14)까지 같으면 된다 — 패치 판(3.14.7↔3.14.8) 차이는 경고만
    same_minor = cur["python"].split(".")[:2] == want_py.split(".")[:2]
    add(OK if cur["python"] == want_py else (WARN if same_minor else BAD), "Python",
        f"{cur['python']} (기준 {want_py}) {cur['python_exe']}")
    if ref:
        miss = [f"{k}=={v}" for k, v in ref["pip"].items() if k not in cur["pip"]]
        diff = [f"{k} {cur['pip'][k]}≠{v}" for k, v in ref["pip"].items() if k in cur["pip"] and cur["pip"][k] != v]
        add(BAD if miss else (WARN if diff else OK), "pip 패키지",
            f"없음 {len(miss)} · 판 다름 {len(diff)} / 기준 {len(ref['pip'])}" + (f" — 없음: {', '.join(miss[:12])}" if miss else "")
            + (f" — 다름: {', '.join(diff[:8])}" if diff else ""))
    else:
        req = ["pydicom", "numpy", "openpyxl", "rdflib", "pillow", "tifffile", "pyside6", "matplotlib",
               "pandas", "lxml", "networkx", "python-docx", "pywin32"]
        miss = [r for r in req if r not in cur["pip"]]
        add(BAD if miss else OK, "pip 패키지", f"없음: {miss}" if miss else f"필수 {len(req)} 있음")
    add(OK if cur["dciodvfy"] and "PATH 밖" not in cur["dciodvfy"] else (WARN if cur["dciodvfy"] else BAD),
        "dciodvfy", cur["dciodvfy"] or "없음 — C:\\tools\\dicom3tools\\bin 복사 + PATH")
    add(OK if cur["node"] else BAD, "Node.js", cur["node"] or "없음")
    add(OK if cur["mermaid"] else BAD, "mermaid-cli", cur["mermaid"] or f"캐시에 없음 — npx -y {env['mermaid_cli']} --version 로 한 번 받아 둘 것")
    add(OK if cur["bash"] else BAD, "Git Bash", cur["bash"] or "없음 — 문서 빌드 *.sh 를 못 돈다")
    add(OK if cur["subst"] else BAD, "subst", "캡처 가상 드라이브(X:)용")
    add(OK if cur["hwp_com"] else BAD, "한컴 한글 COM", "HWPFrame.HwpObject" + ("" if cur["hwp_com"] else " 없음"))
    add(OK if cur["font_malgun"] else BAD, "맑은 고딕", "")
    sc = cur["display_scale"]
    add(OK if sc == env["display_scale_percent"] else WARN, "화면 배율",
        f"{sc}% (기준 {env['display_scale_percent']}% — 캡처는 QT_SCALE_FACTOR 로 따로 정하므로 경고만)")
    add(OK if cur["long_paths"] == 1 else WARN, "긴 경로", f"LongPathsEnabled={cur['long_paths']}")
    add(OK if cur["root_same_path"] else WARN, "21차 경로", cur["root"] + ("" if cur["root_same_path"] else
        " — 원 PC 와 다름: 최종본/02_빌드/_한바퀴_보기/*.sh 의 ROOT · Claude 메모리 폴더 이름 확인"))
    add(OK if cur["root_writable"] else BAD, "21차 쓰기 권한", "" if cur["root_writable"] else "icacls 로 계정에 모든 권한")
    for f, ok in cur["claude_home"].items():
        add(OK if ok else WARN, f"~/.claude/{f}", "" if ok else "없음")
    for r, ok in cur["claude_settings_refs"].items():
        add(OK if ok else BAD, "settings.json 경로", r + ("" if ok else " 없음 — hook/statusline/bkit 가 실패"))
    add(OK if cur["bkit_source"] else WARN, "bkit 원천", env["bkit_source"])
    for p, n in cur["claude_memory"].items():
        add(OK if n else WARN, "Claude 메모리", f"{n}개 — {claude_enc(p)[-45:]}")
    return rows


def main() -> int:
    C.force_utf8_stdout()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", default=str(C.DEFAULT_ROOT))
    p.add_argument("--config")
    p.add_argument("--save-reference", action="store_true")
    a = p.parse_args()
    root = Path(a.root).resolve()
    cfg = C.load_config(Path(a.config) if a.config else None)
    log = C.setup_log("env_check", root)
    cur = collect(root, cfg)
    ref_path = root / "_업무 연계_" / "환경_기준.json"
    if a.save_reference:
        ref_path.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
        (root / "_업무 연계_" / "pip_freeze_기준.txt").write_text(
            "\n".join(f"{k}=={v}" for k, v in sorted(cur["pip"].items())) + "\n", encoding="utf-8")
        log.info(f"기준 저장 {ref_path} · pip {len(cur['pip'])}개")
    ref = json.loads(ref_path.read_text(encoding="utf-8")) if ref_path.is_file() else None
    rows = judge(cur, ref, cfg)
    log.info(f"환경 점검 — {cur['host']} · {cur['user']} · 관리자 {cur['admin']} · 기준 {'있음' if ref else '없음(설정값)'}")
    for s, k, m in rows:
        (log.error if s == BAD else log.warning if s == WARN else log.info)(f"{s} {k:18s} {m}")
    bad = sum(1 for s, _, _ in rows if s == BAD)
    log.info(f"{'🔴 ' + str(bad) + '건 고칠 것' if bad else '✅ 막힘 없음'} · ⚠ {sum(1 for s, _, _ in rows if s == WARN)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
