# 새 PC 설치 순서 — DESKTOP-V96QTPS (조사 2026-09-30 20:53 기준)

> 근거: `새PC_환경조사.txt`(newpc_survey.ps1 결과).
> 목표: 10-02 오전 복사 전에 설치를 끝내 두어, 그날에는 **복사 → 목록 대조 → env_check** 만 한다.

## 0. 조사 결과 요약

| 항목 | 새 PC 현황 | 판정 | 할 일 |
|---|---|---|---|
| 계정 · 권한 | `USER`, 관리자 그룹 소속(지금 창은 비관리자) | ✅ | §1 은 **관리자 PowerShell** 에서 |
| 이전 자리 | `C:\Users\WIN11PRO_512` 없음 | — | §1 에서 만든다 |
| 디스크 | C: NTFS, 여유 875GB | ✅ | — |
| 외장 드라이브 | **연결된 것 없음** | ⚠ | 10-02 전에 NTFS 외장(16GB 이상) 준비. 글자가 E: 가 아니면 명령의 `E:` 를 바꾼다 |
| Python | `python` = **miniconda 3.12.4**(233개 패키지). uv 가 받은 3.14.6 이 따로 있음. 3.14.7 없음 | 🔴 | §2 전용 가상환경(venv). miniconda 는 건드리지 않는다 |
| pip | `pip` = miniconda 것(시스템 PATH) | ⚠ | 늘 `python -m pip` 으로 친다 |
| Node · mermaid | Node 24.18.0, mermaid-cli 없음 | ⚠ | §3 에서 11.17.0 을 미리 받는다 |
| Git Bash | 있음, WSL bash 없음 | ✅ | — |
| dicom3tools | `C:\tools\dicom3tools\bin` 에 이미 있고 PATH 에도 있음 | ⚠ | §5 에서 원 PC 것과 같은 판인지 해시로 대조 |
| 한컴 한글 | **한컴오피스 2018**, COM 등록됨 | ⚠ | 원 PC 판과 다르면 쪽 수가 달라질 수 있다(§4) |
| 보안 프로그램 | PATH 에 **Softcamp SDK/SDS** | 🔴 | §4 에서 한글 저장 파일이 암호화되는지 시험 |
| 긴 경로 | `LongPathsEnabled=0` | ⚠ | §1 에서 1 로 |
| subst · X: | 있음 · X: 비어 있음 | ✅ | — |
| Claude | CLI 2.1.214(`~\.local\bin`) + npm 전역 2.1.270 **두 벌**. `~\.claude` 에 이 PC 자체 `CLAUDE.md` · `settings.json` 있음 | ⚠ | §6. 원 PC 설정은 **덮어쓰지 말고 합친다** |
| 실행 정책 | CurrentUser = RemoteSigned | ✅ | 로컬 .ps1 실행 가능 |

## 1. 폴더 · 권한 · 긴 경로 (관리자 PowerShell, 한 번)

시작 메뉴 → "Windows PowerShell" 우클릭 → **관리자 권한으로 실행**.

```powershell
New-Item -ItemType Directory -Force "C:\Users\WIN11PRO_512\claude-work3\DICOCH 설계명세서 설명" | Out-Null
New-Item -ItemType Directory -Force "C:\Users\WIN11PRO_512\.claude" | Out-Null
icacls "C:\Users\WIN11PRO_512" /grant "USER:(OI)(CI)F" /T
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWord -Force | Out-Null
```

- `USER` 로 직접 적은 까닭: 관리자 창을 다른 계정으로 열면 `%USERNAME%` 이 그 계정이 되기 때문이다.
- 긴 경로 설정은 다시 로그인한 뒤부터 적용된다.

## 2. Python 3.14.7 전용 가상환경 (일반 PowerShell)

miniconda(3.12, tensorflow · torch 등 다른 업무용)는 그대로 두고, DICOCH 전용 venv 를 **21차 폴더 밖**에 만든다.
21차 안에 두면 복귀 목록(`--all`)에 수천 개 파일이 섞인다.

**방법 A — Python 설치 관리자(`py`가 WindowsApps 에 있으므로 이것일 가능성이 높다)**

```powershell
py install 3.14.7
py list                                            # 3.14.7 이 보여야 한다
py -V:3.14 -m venv "C:\Users\USER\venvs\dicoch"
& "C:\Users\USER\venvs\dicoch\Scripts\python.exe" --version    # Python 3.14.7
```

**방법 B — uv(방법 A 가 안 될 때)**

```powershell
uv --version
uv python install 3.14.7
uv venv "C:\Users\USER\venvs\dicoch" --python 3.14.7 --seed    # --seed: venv 안에 pip 를 넣는다(env_check 가 pip freeze 를 쓴다)
```

**패키지** — 원 PC 의 `_업무 연계_\pip_freeze_기준.txt`(91개)를 가져와서:

```powershell
& "C:\Users\USER\venvs\dicoch\Scripts\python.exe" -m pip install -r "<경로>\pip_freeze_기준.txt"
& "C:\Users\USER\venvs\dicoch\Scripts\python.exe" -m pip check
```

- 이 파일을 이 대화에 올려 주면 설치 전에 3.14 용 휠이 없는 패키지가 있는지 먼저 본다.
- 3.14.7 을 못 구하면 이미 있는 3.14.6 으로 만들어도 된다(`env_check` 는 패치 판 차이를 ⚠ 로만 본다).

## 3. mermaid-cli 11.17.0 미리 받기 (일반 PowerShell)

```powershell
npx.cmd -y @mermaid-js/mermaid-cli@11.17.0 --version      # 11.17.0 이 찍혀야 한다(처음엔 Chromium 을 받느라 몇 분)
```

- 🔴 12.x 는 빌드가 멈춘다. 전역 설치(`npm i -g`)는 하지 않는다.
- Node 판(새 PC 24.18.0)은 원 PC 조사 결과와 견준다(§7).

## 4. 한컴 한글 — 보안 프로그램 암호화 시험 🔴 (가장 먼저 확인)

새 PC 에 문서 보안 프로그램(Softcamp)이 있다. 이것이 한글 · Office 가 저장하는 파일을 암호화하면 두 가지가 깨진다.
- 문서 세션의 HWPX → PDF 변환 산출물을 원 PC 에서 못 연다.
- 복귀 때 그 파일이 원 PC 의 정상 파일을 덮는다.

**시험:** 한글을 열어 새 문서에 아무 글자나 적고, 바탕화면에 `drm시험.hwpx` 로 저장한다. 이어서 **파일 → PDF로 저장하기** 로 `drm시험.pdf` 도 만든다. 그다음 아래를 친다.

```powershell
$d = [Environment]::GetFolderPath('Desktop')
foreach ($f in "$d\drm시험.hwpx", "$d\drm시험.pdf") {
    $b = [IO.File]::ReadAllBytes($f)[0..7]
    '{0,-12} {1,-10} [{2}]' -f (Split-Path $f -Leaf), [Text.Encoding]::ASCII.GetString($b), (($b | ForEach-Object { $_.ToString('X2') }) -join ' ')
}
```

| 결과 | 뜻 | 대응 |
|---|---|---|
| hwpx 가 `PK` 로, pdf 가 `%PDF` 로 시작 | 암호화 안 됨 | 그대로 진행 |
| 그 밖의 글자(예: `SCDSA…`)로 시작 | **암호화됨** | ① 원 PC 에도 Softcamp 가 있는지 본다(§7). ② 없으면 한글이 저장하는 작업(HWPX · PDF 빌드, 쪽번호)은 복귀 뒤 원 PC 에서 하거나, 전산 담당에게 21차 폴더 예외를 요청한다 |

- 복귀 스크립트에도 같은 검사를 넣었다. `return_apply.py` 가 옮길 파일의 머리를 보고 이상하면 **미리 보기 단계에서 멈춘다**(②-2).
- 새 PC 에서 작업하는 중에도 `python manifest.py magic "<21차>\최종본"` 으로 수시로 볼 수 있다.
- **한글 판**: 새 PC 는 2018(10.0)이다. 원 PC 판이 다르면 같은 HWPX 라도 쪽 나눔이 달라질 수 있다. 쪽 수에 기대는 산출(쪽번호 · 목차 쪽)은 새 PC 결과를 확정본으로 쓰지 말고 복귀 뒤 원 PC 에서 다시 뽑는다.

## 5. dicom3tools 판 대조

새 PC 에 이미 있으므로 복사하지 않는다. 대신 **같은 판인지** 본다. 판이 다르면 dciodvfy 경고 문구가 달라져 게이트 결과가 어긋난다.
아래를 원 PC 와 새 PC 에서 각각 쳐서 두 값을 견준다.

```powershell
(Get-FileHash C:\tools\dicom3tools\bin\dciodvfy.exe -Algorithm SHA1).Hash
```

다르면 10-02 에 원 PC 의 `C:\tools\dicom3tools\` 를 외장으로 가져와, 새 PC 것을 `C:\tools\dicom3tools_새PC원래\` 로 이름 바꾼 뒤 그 자리에 둔다.

## 6. Claude

1. **지금 이 PC 설정을 백업한다**(10-02 에 원 PC 설정과 합칠 때 되돌릴 수 있게):
   ```powershell
   $b = "$env:USERPROFILE\.claude\backups\이전전_$(Get-Date -Format yyyyMMdd_HHmm)"
   New-Item -ItemType Directory -Force $b | Out-Null
   Copy-Item "$env:USERPROFILE\.claude\CLAUDE.md", "$env:USERPROFILE\.claude\settings.json" $b
   ```
2. **한 벌로 정리하고 올린다**: PATH 에서 `~\.local\bin`(2.1.214)이 먼저 잡힌다. npm 전역 사본(2.1.270)은 지워서 헷갈림을 없앤다.
   ```powershell
   npm.cmd uninstall -g @anthropic-ai/claude-code
   claude update
   claude --version            # 원 PC 와 비슷한 판(원 PC 세션 기록상 2.1.284)
   ```
3. **10-02, 원 PC 설정 반영**(외장 `_환경\` 에서):
   - `claude-guard.ps1`, `statusline.ps1` → `C:\Users\WIN11PRO_512\.claude\` (원 PC `settings.json` 이 이 절대 경로를 부른다)
   - `bkit-claude-code\` → `C:\Users\WIN11PRO_512\bkit-claude-code\`
   - `CLAUDE.md`, `settings.json` → `C:\Users\USER\.claude\` 에 **덮어쓰지 않는다.** 이 PC 에도 자기 설정이 있으므로 두 벌을 견주어 합친다(원 PC 의 hooks · statusLine · 플러그인 줄을 이 PC 파일에 더한다). 합치기가 번거로우면 새 Claude 세션에 두 파일을 보여 주고 합치게 한다.
   - `skills\` → `C:\Users\USER\.claude\skills\` (같은 이름이 있으면 건너뛴다)
   - 메모리 → Claude 로 21차 폴더와 `DICOCH_Tool_정본` 을 한 번씩 연 뒤, 생긴 `C:\Users\USER\.claude\projects\C--Users-WIN11PRO-512-…\memory\` 에 넣는다. 경로가 원 PC 와 같으므로 폴더 이름도 같다.

## 7. 원 PC 에서도 같은 조사를 한 번 (10-01 까지)

원 PC 에서 `newpc_survey.ps1` 을 그대로 붙여 넣어 돌리고, 결과 파일을 이 대화에 올린다. 두 결과를 견주어 아래를 확정한다.

- 원 PC 의 한글 판, Softcamp 유무, Node · Claude 판, dciodvfy 해시(§5)
- `C:\Users\WIN11PRO_512\.claude\` 에 무엇이 있는지(§6-3 에서 가져갈 목록)

## 8. 작업 시작 도구 — venv 를 켜고 Claude 를 연다

Claude Code 의 Bash 도구는 **Claude 를 띄운 창의 환경을 물려받는다.** 이 PC 에서 그냥 `claude` 를 치면 세션 안의 `python` 이 miniconda 3.12 가 되어, 게이트 결과가 원 PC 와 어긋난다.
그러므로 DICOCH 작업은 늘 아래 시작 스크립트로 연다. 아래를 **일반 PowerShell 에 붙여 넣으면** 시작 스크립트 파일이 만들어진다(UTF-8 BOM 으로 저장해 한글 경로가 깨지지 않는다).

```powershell
@'
param([ValidateSet('doc', 'code')][string]$Session = 'doc')
# DICOCH 작업 시작: 전용 venv 를 켜고 21차(문서 세션) 또는 DICOCH_Tool_정본(코드 세션)에서 Claude 를 연다.
$root = 'C:\Users\WIN11PRO_512\claude-work3\DICOCH 설계명세서 설명\21차_20260824'
$venv = 'C:\Users\USER\venvs\dicoch'
if (-not (Test-Path "$venv\Scripts\Activate.ps1")) { Write-Host "venv 가 없습니다: $venv" -ForegroundColor Red; return }
& "$venv\Scripts\Activate.ps1"
$env:PYTHONIOENCODING = 'utf-8'
$dir = if ($Session -eq 'code') { Join-Path $root 'DICOCH_Tool_정본' } else { $root }
if (-not (Test-Path $dir)) { Write-Host "작업 폴더가 없습니다: $dir" -ForegroundColor Red; return }
Set-Location $dir
Write-Host "python = $((Get-Command python).Source)  ($(python --version))" -ForegroundColor Green
claude
'@ | Set-Content -Path "$env:USERPROFILE\DICOCH_시작.ps1" -Encoding UTF8
```

쓰는 법:

```powershell
& "$env:USERPROFILE\DICOCH_시작.ps1"                 # 문서 세션(21차 루트)
& "$env:USERPROFILE\DICOCH_시작.ps1" -Session code   # 코드 세션(DICOCH_Tool_정본)
```

- 이전 스크립트(`manifest.py` · `env_check.py` 등)도 venv 를 켠 창에서 돌린다.
- 새 세션에서 처음 한 번 `python -c "import sys; print(sys.executable)"` 로 venv 파이썬인지 확인시킨다.

## 9. 10-02 도착 뒤 확인 (실행순서 §3 과 같음)

1. `python manifest.py verify --manifest ..\manifest_기준_….tsv` → ✅
2. `python env_check.py` → 🔴 0 (venv 를 켠 창에서)
3. `python manifest.py magic "<21차>\최종본"` → 이미 있는 파일 머리 확인(복사본이 정상인지)
4. 게이트 · 문서 사슬(`& "C:\Program Files\Git\bin\bash.exe" …chain_ch1.sh`) · GUI · 캡처 한 장
