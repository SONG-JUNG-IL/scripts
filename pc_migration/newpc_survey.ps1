& {
# PC 환경 조사 2판 — 원 PC · 새 PC 공통. 읽기만 한다(예외: 이전 자리 쓰기 시험 파일 하나를 만들고 바로 지움).
# 결과: 바탕화면\환경조사_<PC이름>_<시각>.txt  (관리자 권한 불필요 · 일반 PowerShell 창)
$desk = [Environment]::GetFolderPath('Desktop')
$out  = Join-Path $desk ("환경조사_{0}_{1}.txt" -f $env:COMPUTERNAME, (Get-Date -Format 'yyyyMMdd_HHmm'))
$ROOT = 'C:\Users\WIN11PRO_512\claude-work3\DICOCH 설계명세서 설명\21차_20260824'
$VENV = Join-Path $env:USERPROFILE 'venvs\dicoch'
$NEED = 'pydicom','numpy','openpyxl','rdflib','pillow','tifffile','pyside6','matplotlib','pandas','lxml','networkx','python-docx','pywin32','pyinstaller'

function V {
    # 명령이 있으면 판(version)과 실제 경로를, 없으면 '없음'을 낸다
    param([string]$Cmd, [string[]]$A = @('--version'))
    $c = Get-Command $Cmd -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $c) { return ('{0,-12} 없음' -f $Cmd) }
    $src = if ($c.Source) { $c.Source } else { $c.Definition }
    try { $v = (& $src @A 2>&1 | ForEach-Object { "$_" } | Select-Object -First 3) -join ' / ' }
    catch { $v = "실행 오류: $($_.Exception.Message)" }
    $note = if ($src -like '*WindowsApps*') { '  ⚠ WindowsApps 경로 — Microsoft Store 별칭일 수 있음' } else { '' }
    '{0,-12} {1}  [{2}]{3}' -f $Cmd, $v, $src, $note
}

function Freeze {
    # 주어진 python 의 pip freeze 개수 · 필수 중 없는 것 · 전체 목록
    param([string]$Py, [string]$Label)
    $freeze = @(& $Py -m pip freeze 2>$null)
    "$Label pip freeze  $($freeze.Count)개"
    $have = @($freeze | ForEach-Object { ($_ -split '==| @ ')[0].ToLower() })
    "  필수 중 없음: $((@($NEED | Where-Object { $have -notcontains $_ })) -join ', ')"
    $freeze | ForEach-Object { "  $_" }
}

function Head8 {
    # 파일 첫 8바이트(ASCII · 16진) — hwpx 는 PK, pdf 는 %PDF 로 시작해야 정상
    param([string]$Path)
    try {
        $fs = [IO.File]::OpenRead($Path)
        try { $b = New-Object byte[] 8; $n = $fs.Read($b, 0, 8) } finally { $fs.Close() }
        $b = $b[0..([Math]::Max($n, 1) - 1)]
        '{0,-10} [{1}]' -f ([Text.Encoding]::ASCII.GetString($b) -replace '[^\x20-\x7E]', '.'), (($b | ForEach-Object { $_.ToString('X2') }) -join ' ')
    } catch { "읽기 실패: $($_.Exception.Message)" }
}

& {
    '== 1. 기본'
    "조사 시각   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  시간대 $((Get-TimeZone).Id)  (조사판 2)"
    "PC / 계정   $env:COMPUTERNAME / $env:USERNAME  (프로필 $env:USERPROFILE)"
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        "OS          $($os.Caption) $($os.Version) (빌드 $($os.BuildNumber))  RAM $([math]::Round($os.TotalVisibleMemorySize/1MB,1))GB"
        "CPU         $((Get-CimInstance Win32_Processor | Select-Object -First 1).Name)"
        "GPU         $((Get-CimInstance Win32_VideoController | ForEach-Object Name) -join ' / ')"
    } catch { "OS 조회 실패: $($_.Exception.Message)" }
    "PowerShell  $($PSVersionTable.PSVersion)"
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        "관리자 창    $(([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))  (False 여도 계정이 관리자 그룹이면 된다)"
    } catch { "관리자 창    조회 실패: $($_.Exception.Message)" }
    try { "관리자 그룹  $((Get-LocalGroupMember -SID 'S-1-5-32-544' | ForEach-Object Name) -join ', ')" }
    catch { "관리자 그룹  조회 실패: $($_.Exception.Message)" }
    "실행 정책"
    Get-ExecutionPolicy -List | ForEach-Object { '  {0,-14} {1}' -f $_.Scope, $_.ExecutionPolicy }

    ''
    '== 2. 디스크 (21차 사본 약 8GB + 산출 여유 · 외장은 NTFS 16GB 이상 · DriveType Removable = 외장)'
    try {
        Get-Volume | Where-Object DriveLetter | Sort-Object DriveLetter | ForEach-Object {
            '  {0}:  {1,-6} {2,-10} 여유 {3,7:N1}GB / 전체 {4,7:N1}GB  {5}' -f $_.DriveLetter, $_.FileSystemType, $_.DriveType,
                ($_.SizeRemaining/1GB), ($_.Size/1GB), $_.FileSystemLabel }
    } catch {
        Get-PSDrive -PSProvider FileSystem | ForEach-Object { '  {0}:  여유 {1:N1}GB' -f $_.Name, ($_.Free/1GB) }
    }

    ''
    '== 3. Python (기준 3.14.7)'
    V py @('-0p')
    V py @('list')
    V uv
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        'uv 가 가진 Python'
        & uv python list --only-installed 2>&1 | ForEach-Object { "  $_" }
    }
    V python
    V pip
    $py = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    if ($py -and $py -notlike '*WindowsApps*') { Freeze $py '기본 python' }
    else { '기본 python pip freeze  건너뜀(python 이 없거나 Store 별칭)' }

    ''
    "== 4. DICOCH 전용 가상환경 ($VENV)"
    $vpy = Join-Path $VENV 'Scripts\python.exe'
    if (Test-Path $vpy) {
        "venv python  $(& $vpy --version 2>&1)  [$vpy]"
        "Activate.ps1 $(Test-Path (Join-Path $VENV 'Scripts\Activate.ps1'))"
        Freeze $vpy 'venv'
    } else { 'venv 없음 — 설치순서 §2' }
    "시작 스크립트  $(Test-Path (Join-Path $env:USERPROFILE 'DICOCH_시작.ps1'))  ($env:USERPROFILE\DICOCH_시작.ps1)"

    ''
    '== 5. Node · mermaid (기준 @mermaid-js/mermaid-cli@11.17.0)'
    V node
    V npm.cmd
    V npx.cmd
    if (Get-Command npm.cmd -ErrorAction SilentlyContinue) {
        '전역 npm 패키지'
        & npm.cmd ls -g --depth=0 2>&1 | ForEach-Object { "  $_" }
        $cache = (& npm.cmd config get cache 2>$null | Select-Object -First 1)
        if (-not $cache) { $cache = Join-Path $env:LOCALAPPDATA 'npm-cache' }
        $mm = @(Get-ChildItem (Join-Path $cache '_npx') -Directory -ErrorAction SilentlyContinue |
              ForEach-Object { Join-Path $_.FullName 'node_modules\@mermaid-js\mermaid-cli\package.json' } |
              Where-Object { Test-Path $_ } | ForEach-Object { (Get-Content $_ -Raw | ConvertFrom-Json).version })
        "npx 캐시의 mermaid-cli  $(if ($mm) { $mm -join ', ' } else { '없음 — 설치순서 §3' })  ($cache\_npx)"
    }
    $pp = Join-Path $env:USERPROFILE '.cache\puppeteer'
    "puppeteer 브라우저  $(if (Test-Path $pp) { (Get-ChildItem $pp -Directory -Name) -join ', ' } else { '없음' })"

    ''
    '== 6. 빌드 · 검증 도구'
    V git
    $gb = 'C:\Program Files\Git\bin\bash.exe'
    "Git Bash    $(if (Test-Path $gb) { (& $gb --version 2>&1 | Select-Object -First 1) } else { '없음' })  ($gb)"
    "WSL bash    $(Test-Path "$env:WINDIR\System32\bash.exe")  (True 면 'bash' 만 칠 때 이것이 잡힐 수 있음)"
    $dc = 'C:\tools\dicom3tools\bin\dciodvfy.exe'
    "dciodvfy    있음 $(Test-Path $dc) · PATH $([bool](Get-Command dciodvfy -ErrorAction SilentlyContinue)) · DICOCH_DCIODVFY=$env:DICOCH_DCIODVFY"
    if (Test-Path $dc) {
        "  SHA1 $((Get-FileHash $dc -Algorithm SHA1).Hash)  수정 $((Get-Item $dc).LastWriteTime.ToString('yyyy-MM-dd'))  (원 PC 와 같아야 한다)"
    }
    "subst       $([bool](Get-Command subst -ErrorAction SilentlyContinue)) · X: 사용 중 $(Test-Path 'X:\')"
    try { "긴 경로    LongPathsEnabled=$((Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -ErrorAction Stop).LongPathsEnabled)  (1 이어야 · 바꾼 뒤 다시 로그인)" }
    catch { '긴 경로    조회 실패' }
    "맑은 고딕   $(Test-Path "$env:WINDIR\Fonts\malgun.ttf")"
    V winget

    ''
    '== 7. 한컴 한글'
    "한글 COM    $(Test-Path 'Registry::HKEY_CLASSES_ROOT\HWPFrame.HwpObject')  (HWPFrame.HwpObject)"
    try {
        $clsid = (Get-ItemProperty 'Registry::HKEY_CLASSES_ROOT\HWPFrame.HwpObject\CLSID' -ErrorAction Stop).'(default)'
        $srv = $null
        foreach ($k in "Registry::HKEY_CLASSES_ROOT\CLSID\$clsid\LocalServer32", "Registry::HKEY_CLASSES_ROOT\WOW6432Node\CLSID\$clsid\LocalServer32") {
            if (-not $srv) { $srv = (Get-ItemProperty $k -ErrorAction SilentlyContinue).'(default)' }
        }
        $exe = ($srv -replace '^"([^"]+)".*$', '$1') -replace '\s+/.*$', ''
        if ($exe -and (Test-Path $exe)) {
            $vi = (Get-Item $exe).VersionInfo
            "한글 실행 파일  $exe  판 $($vi.ProductVersion) (파일 $($vi.FileVersion))"
        } else { "한글 실행 파일  찾지 못함 ($srv)" }
    } catch { "한글 판 조회 실패: $($_.Exception.Message)" }

    ''
    '== 8. 문서 보안 프로그램(DRM) · 암호화 시험 파일'
    "PATH 의 Softcamp  $((@($env:Path -split ';' | Where-Object { $_ -match 'Softcamp' })) -join ', ')"
    try {
        $svc = @(Get-CimInstance Win32_Service | Where-Object { $_.PathName -match 'Softcamp' -or $_.DisplayName -match 'Softcamp|소프트캠프|DRM|Document Security' })
        "보안 서비스  $($svc.Count)개"
        $svc | ForEach-Object { '  {0,-30} {1,-8} {2}' -f $_.DisplayName, $_.State, $_.PathName }
    } catch { "서비스 조회 실패: $($_.Exception.Message)" }
    foreach ($f in 'drm시험.hwpx', 'drm시험.pdf') {
        $p = Join-Path $desk $f
        if (Test-Path $p) { '  {0,-14} {1}' -f $f, (Head8 $p) } else { '  {0,-14} 없음(설치순서 §4 시험 전)' -f $f }
    }
    '  → hwpx 는 PK, pdf 는 %PDF 로 시작해야 정상. 다른 글자면 암호화 의심'

    ''
    '== 9. Claude'
    V claude
    "~\.local\bin\claude.exe  $(Test-Path (Join-Path $env:USERPROFILE '.local\bin\claude.exe'))"
    "Claude 데스크톱  $(Test-Path "$env:LOCALAPPDATA\AnthropicClaude")"
    $ch = Join-Path $env:USERPROFILE '.claude'
    "~\.claude  $(Test-Path $ch)"
    if (Test-Path $ch) {
        Get-ChildItem $ch -Force | ForEach-Object { '  {0,-32} {1}' -f $_.Name, $(if ($_.PSIsContainer) { '<폴더>' } else { '{0:N0}B' -f $_.Length }) }
        $bk = @(Get-ChildItem (Join-Path $ch 'backups') -Directory -Filter '이전전_*' -ErrorAction SilentlyContinue | ForEach-Object Name)
        "  설정 백업(이전전_*)  $(if ($bk) { $bk -join ', ' } else { '없음 — 설치순서 §6-1' })"
        $pj = Join-Path $ch 'projects'
        'DICOCH 메모리 폴더(projects\C--Users-WIN11PRO-512-*)'
        Get-ChildItem $pj -Directory -Filter 'C--Users-WIN11PRO-512*' -ErrorAction SilentlyContinue | ForEach-Object {
            $m = Join-Path $_.FullName 'memory'
            '  {0}  memory {1}개' -f $_.Name, @(Get-ChildItem $m -Filter *.md -ErrorAction SilentlyContinue).Count
        }
    }

    ''
    '== 10. 이전 자리 · 권한'
    foreach ($p in 'C:\Users\WIN11PRO_512', 'C:\Users\WIN11PRO_512\claude-work3', (Split-Path $ROOT), $ROOT,
                   'C:\Users\WIN11PRO_512\.claude', 'C:\Users\WIN11PRO_512\.claude\claude-guard.ps1',
                   'C:\Users\WIN11PRO_512\.claude\statusline.ps1', 'C:\Users\WIN11PRO_512\bkit-claude-code', 'C:\tools') {
        '  {0,-70} {1}' -f $p, (Test-Path $p)
    }
    if (Test-Path 'C:\Users\WIN11PRO_512') {
        '권한(C:\Users\WIN11PRO_512 에서 이 계정)'
        (Get-Acl 'C:\Users\WIN11PRO_512').Access | Where-Object { "$($_.IdentityReference)" -like "*\$env:USERNAME" } |
            ForEach-Object { '  {0}  {1}  상속 {2}' -f $_.IdentityReference, $_.FileSystemRights, $_.InheritanceFlags }
    }
    $wdir = Split-Path $ROOT
    if (Test-Path $wdir) {
        $t = Join-Path $wdir '_쓰기시험.tmp'
        try { Set-Content -Path $t -Value x -ErrorAction Stop; Remove-Item $t -ErrorAction Stop; "쓰기 시험  ✅ $wdir" }
        catch { "쓰기 시험  🔴 $($_.Exception.Message) — 설치순서 §1 icacls" }
    }
    if (Test-Path $ROOT) {
        $n = @(Get-ChildItem $ROOT -Force -Name)
        "21차 폴더 첫 단계 $($n.Count)개: $($n -join ', ')"
    }

    ''
    '== 11. 설치된 프로그램(관련만)'
    $keys = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    Get-ItemProperty $keys -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match '한글|한컴|Hancom|Hwp|Python|Node\.js|^Git|Claude|uv|Softcamp|소프트캠프|Visual C\+\+ (2015|2022|v14)' } |
        Sort-Object DisplayName -Unique | ForEach-Object { '  {0}  {1}' -f $_.DisplayName, $_.DisplayVersion }

    ''
    '== 12. PATH'
    $env:Path -split ';' | Where-Object { $_ } | ForEach-Object { "  $_" }
} *>&1 | ForEach-Object { "$_" } | Out-File -FilePath $out -Encoding utf8

Write-Host "저장했습니다: $out" -ForegroundColor Green
notepad $out
}
