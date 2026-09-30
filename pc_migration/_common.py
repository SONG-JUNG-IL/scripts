"""PC 이전·복귀 스크립트 공통 모듈 — 설정 읽기 · 범위 걷기 · 해시 · 목록(manifest) 읽고 쓰기 · 차분.

목록 파일(TSV) 꼴::

    # DICOCH-MANIFEST v1
    # mode=scope|all  root=<만든 자리>  made=<YYYY-MM-DD HH:MM:SS>  host=<컴퓨터 이름>
    <상대경로>\t<크기>\t<mtime_ns>\t<sha1>

상대경로는 21차 폴더 기준이고 구분자는 '/'. 모든 스크립트는 기본이 "읽기만" 이다.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import os
import platform
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
HANDOFF_DIR = TOOLS_DIR.parent                 # _업무 연계_
DEFAULT_ROOT = HANDOFF_DIR.parent              # 21차_20260824
CONFIG_PATH = TOOLS_DIR / "이전설정.json"
MANIFEST_MAGIC = "# DICOCH-MANIFEST v1"
CHUNK = 1 << 20                                # 1 MiB
HASH_WORKERS = 8


# ── 설정 ──────────────────────────────────────────────────────────────
def load_config(path: Path | None = None) -> dict:
    """설정 JSON 을 읽는다.

    Args:
        path: 설정 파일. 없으면 tools/이전설정.json.
    Returns:
        설정 dict.
    Raises:
        FileNotFoundError: 설정 파일이 없을 때.
    """
    p = path or CONFIG_PATH
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def expand(s: str) -> str:
    """%VAR% · ~ 를 펼치고 구분자를 OS 꼴로 바꾼다."""
    return os.path.expanduser(os.path.expandvars(s)).replace("/", os.sep)


# ── 로그 ──────────────────────────────────────────────────────────────
def setup_log(name: str, root: Path) -> logging.Logger:
    """화면 + `_업무 연계_/logs/{name}_{시각}.log` 이중 출력 로거를 만든다."""
    log_dir = root / "_업무 연계_" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    fh = logging.FileHandler(log_dir / f"{name}_{datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def force_utf8_stdout() -> None:
    """Windows 콘솔에서 한글이 깨지지 않게 표준 출력을 UTF-8 로 둔다."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


# ── 범위 걷기 ──────────────────────────────────────────────────────────
def _norm(rel: str) -> str:
    rel = rel.replace("\\", "/").strip("/")
    return "" if rel == "." else rel


def _under(rel: str, prefixes: list[str]) -> bool:
    return any(rel == p or rel.startswith(p + "/") for p in prefixes)


class Filter:
    """exclude 규칙(상대경로 접두 · 폴더 이름 · 확장자)."""

    def __init__(self, cfg: dict, extra: list[str] | None = None) -> None:
        self.prefixes = [_norm(p) for p in cfg.get("exclude", []) + (extra or [])]
        self.dir_names = set(cfg.get("exclude_dir_names", []))
        self.suffixes = tuple(s.lower() for s in cfg.get("exclude_file_suffixes", []))

    def skip_dir(self, rel: str, name: str) -> bool:
        return name in self.dir_names or _under(rel, self.prefixes)

    def skip_file(self, rel: str) -> bool:
        return rel.lower().endswith(self.suffixes) or _under(rel, self.prefixes)


def _walk(root: Path, start_rel: str, flt: Filter, files_only: bool):
    """start_rel 아래 파일의 상대경로를 낸다(symlink·junction 은 따라가지 않는다)."""
    base = root / start_rel if start_rel else root
    if base.is_file():
        yield start_rel
        return
    if not base.is_dir():
        return
    if files_only:
        for e in os.scandir(base):
            if e.is_file(follow_symlinks=False):
                rel = _norm(f"{start_rel}/{e.name}")
                if not flt.skip_file(rel):
                    yield rel
        return
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        drel = _norm(os.path.relpath(dirpath, root).replace(os.sep, "/"))
        dirnames[:] = [d for d in dirnames if not flt.skip_dir(_norm(f"{drel}/{d}"), d)]
        for fn in filenames:
            rel = _norm(f"{drel}/{fn}")
            if not flt.skip_file(rel):
                yield rel


def scope_files(root: Path, cfg: dict, for_manifest: bool = True) -> list[str]:
    """설정 scope 가 가리키는 파일 목록(상대경로, 정렬).

    Args:
        root: 21차 폴더.
        cfg: 설정.
        for_manifest: True 면 "manifest": false 항목을 뺀다.
    """
    flt = Filter(cfg)
    out: set[str] = set()
    for ent in cfg["scope"]:
        if for_manifest and ent.get("manifest", True) is False:
            continue
        out.update(_walk(root, _norm(ent["path"]), flt, bool(ent.get("files_only"))))
    return sorted(out)


def all_files(root: Path, cfg: dict) -> list[str]:
    """21차 폴더 전체를 exclude 규칙(+ final_extra_exclude · manifest:false 항목)으로 거른 목록."""
    extra = list(cfg.get("final_extra_exclude", []))
    extra += [_norm(e["path"]) for e in cfg["scope"] if e.get("manifest", True) is False and _norm(e["path"])]
    return sorted(_walk(root, "", Filter(cfg, extra), False))


def scope_missing(root: Path, cfg: dict) -> list[str]:
    """scope 에 적혔는데 실제로 없는 항목."""
    return [e["path"] for e in cfg["scope"] if not (root / _norm(e["path"])).exists()]


# ── 해시 · 목록 ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Entry:
    size: int
    mtime_ns: int
    sha1: str


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def measure(root: Path, rels: list[str], log: logging.Logger | None = None,
            quick_from: dict[str, Entry] | None = None) -> dict[str, Entry]:
    """파일마다 크기·mtime·sha1 을 잰다.

    Args:
        quick_from: 주면 크기·mtime 이 같은 파일은 그 sha1 을 믿고 다시 읽지 않는다(--quick).
    """
    def one(rel: str) -> tuple[str, Entry]:
        p = root / rel
        st = p.stat()
        if quick_from and rel in quick_from:
            old = quick_from[rel]
            if old.size == st.st_size and old.mtime_ns == st.st_mtime_ns:
                return rel, old
        return rel, Entry(st.st_size, st.st_mtime_ns, sha1_of(p))

    out: dict[str, Entry] = {}
    total = len(rels)
    with ThreadPoolExecutor(HASH_WORKERS) as ex:
        for i, (rel, ent) in enumerate(ex.map(one, rels), 1):
            out[rel] = ent
            if log and (i % 2000 == 0 or i == total):
                log.info(f"  잼 {i:,}/{total:,}")
    return out


def write_manifest(path: Path, entries: dict[str, Entry], mode: str, root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(MANIFEST_MAGIC + "\n")
        f.write(f"# mode={mode}\troot={root}\tmade={datetime.now():%Y-%m-%d %H:%M:%S}"
                f"\thost={platform.node()}\tfiles={len(entries)}"
                f"\tbytes={sum(e.size for e in entries.values())}\n")
        for rel in sorted(entries):
            e = entries[rel]
            f.write(f"{rel}\t{e.size}\t{e.mtime_ns}\t{e.sha1}\n")


def read_manifest(path: Path) -> tuple[dict[str, str], dict[str, Entry]]:
    """목록 파일을 읽는다.

    Returns:
        (머리 정보 dict, {상대경로: Entry})
    Raises:
        ValueError: 목록 파일 꼴이 아닐 때.
    """
    head: dict[str, str] = {}
    entries: dict[str, Entry] = {}
    with open(path, encoding="utf-8") as f:
        first = f.readline().rstrip("\n")
        if first != MANIFEST_MAGIC:
            raise ValueError(f"목록 파일이 아닙니다: {path}")
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("#"):
                for kv in line[1:].strip().split("\t"):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        head[k.strip()] = v
                continue
            if not line:
                continue
            rel, size, mt, sha = line.split("\t")
            entries[rel] = Entry(int(size), int(mt), sha)
    return head, entries


# ── 차분 ──────────────────────────────────────────────────────────────
def diff(old: dict[str, Entry], new: dict[str, Entry]) -> dict[str, list]:
    """두 목록을 다섯 무리로 가른다.

    Returns:
        {"added": [rel], "changed": [rel], "moved": [[from, to]], "deleted": [rel], "same": 개수}
        이동은 sha1 이 같은 삭제·추가 한 쌍이다(같은 파일 이름을 먼저 짝짓는다). 빈 파일은 이동으로 보지 않는다.
    """
    gone = [r for r in old if r not in new]
    born = [r for r in new if r not in old]
    changed = sorted(r for r in old if r in new and old[r].sha1 != new[r].sha1)
    same = sum(1 for r in old if r in new and old[r].sha1 == new[r].sha1)

    by_sha: dict[str, list[str]] = {}
    for r in born:
        if new[r].size > 0:
            by_sha.setdefault(new[r].sha1, []).append(r)
    moved: list[list[str]] = []
    used: set[str] = set()
    moved_from: set[str] = set()
    # 같은 이름 우선 → 그다음 아무거나
    for pass_same_name in (True, False):
        for r in gone:
            if r in moved_from or old[r].size == 0:
                continue
            cands = [c for c in by_sha.get(old[r].sha1, []) if c not in used]
            if pass_same_name:
                cands = [c for c in cands if c.rsplit("/", 1)[-1] == r.rsplit("/", 1)[-1]]
            if cands:
                moved.append([r, cands[0]])
                used.add(cands[0])
                moved_from.add(r)
    return {
        "added": sorted(r for r in born if r not in used),
        "changed": changed,
        "moved": sorted(moved),
        "deleted": sorted(r for r in gone if r not in moved_from),
        "same": same,
    }


def in_volatile(rel: str, cfg: dict) -> bool:
    return _under(rel, [_norm(v) for v in cfg.get("volatile", [])]) or any(
        fnmatch.fnmatch(rel, _norm(v)) for v in cfg.get("volatile", []))


def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return str(n)


def summarize(d: dict[str, list]) -> str:
    return (f"추가 {len(d['added'])} · 변경 {len(d['changed'])} · 이동 {len(d['moved'])} · "
            f"삭제 {len(d['deleted'])} · 그대로 {d['same']}")
