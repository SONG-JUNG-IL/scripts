& {
# 새 PC 환경 조사 — 읽기만 한다. 결과는 바탕화면\새PC_환경조사.txt 한 파일에만 쓴다(관리자 권한 불필요).
$out = Join-Path ([Environment]::GetFolderPath('Desktop')) '새PC_환경조사.txt'

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

& {
    '== 1. 기본'
    "조사 시각   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  시간대 $((Get-TimeZone).Id)"
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
    '== 2. 디스크 (21차 사본 약 8GB + 산출 여유 필요 · 외장은 NTFS 권장)'
    try {
        Get-Volume | Where-Object DriveLetter | Sort-Object DriveLetter | ForEach-Object {
            '  {0}:  {1,-6} {2,-8} 여유 {3,7:N1}GB / 전체 {4,7:N1}GB  {5}' -f $_.DriveLetter, $_.FileSystemType, $_.DriveType,
                ($_.SizeRemaining/1GB), ($_.Size/1GB), $_.FileSystemLabel }
    } catch {
        Get-PSDrive -PSProvider FileSystem | ForEach-Object { '  {0}:  여유 {1:N1}GB' -f $_.Name, ($_.Free/1GB) }
    }

    ''
    '== 3. Python (기준 3.14.7)'
    V py @('-0p')
    V python
    V pip
    $py = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    if ($py -and $py -notlike '*WindowsApps*') {
        $freeze = & $py -m pip freeze 2>$null
        "pip freeze  $(@($freeze).Count)개"
        $have = @($freeze | ForEach-Object { ($_ -split '==')[0].ToLower() })
        $need = 'pydicom','numpy','openpyxl','rdflib','pillow','tifffile','pyside6','matplotlib','pandas','lxml','networkx','python-docx','pywin32','pyinstaller'
        "  필수 중 없음: $((@($need | Where-Object { $have -notcontains $_ })) -join ', ')"
        $freeze | ForEach-Object { "  $_" }
    } else { 'pip freeze  건너뜀(python 이 없거나 Store 별칭)' }

    ''
    '== 4. Node · mermaid (기준 @mermaid-js/mermaid-cli@11.17.0)'
    V node
    V npm.cmd
    V npx.cmd
    if (Get-Command npm.cmd -ErrorAction SilentlyContinue) {
        '전역 npm 패키지'
        & npm.cmd ls -g --depth=0 2>&1 | ForEach-Object { "  $_" }
    }

    ''
    '== 5. 빌드 · 검증 도구'
    V git
    "Git Bash    $(Test-Path 'C:\Program Files\Git\bin\bash.exe')  (C:\Program Files\Git\bin\bash.exe)"
    "WSL bash    $(Test-Path "$env:WINDIR\System32\bash.exe")  (True 면 'bash' 만 칠 때 이것이 잡힐 수 있음)"
    "dciodvfy    C:\tools\dicom3tools\bin: $(Test-Path 'C:\tools\dicom3tools\bin\dciodvfy.exe') · PATH: $([bool](Get-Command dciodvfy -ErrorAction SilentlyContinue)) · DICOCH_DCIODVFY=$env:DICOCH_DCIODVFY"
    "한글 COM    $(Test-Path 'Registry::HKEY_CLASSES_ROOT\HWPFrame.HwpObject')  (HWPFrame.HwpObject)"
    "맑은 고딕   $(Test-Path "$env:WINDIR\Fonts\malgun.ttf")"
    "subst       $([bool](Get-Command subst -ErrorAction SilentlyContinue)) · X: 사용 중 $(Test-Path 'X:\')"
    try { "긴 경로    LongPathsEnabled=$((Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -ErrorAction Stop).LongPathsEnabled)" }
    catch { '긴 경로    조회 실패' }
    V winget

    ''
    '== 6. Claude'
    V claude
    "Claude 데스크톱  $(Test-Path "$env:LOCALAPPDATA\AnthropicClaude")"
    $ch = Join-Path $env:USERPROFILE '.claude'
    "~\.claude  $(Test-Path $ch)"
    if (Test-Path $ch) { Get-ChildItem $ch -Force -Name | ForEach-Object { "  $_" } }

    ''
    '== 7. 이전 자리'
    foreach ($p in 'C:\Users\WIN11PRO_512', 'C:\Users\WIN11PRO_512\claude-work3', 'C:\Users\WIN11PRO_512\.claude', 'C:\Users\WIN11PRO_512\bkit-claude-code', 'C:\tools') {
        '  {0,-45} {1}' -f $p, (Test-Path $p)
    }

    ''
    '== 8. 설치된 프로그램(관련만)'
    $keys = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    Get-ItemProperty $keys -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match '한글|한컴|Hancom|Hwp|Python|Node\.js|^Git|Claude|Visual C\+\+' } |
        Sort-Object DisplayName -Unique | ForEach-Object { '  {0}  {1}' -f $_.DisplayName, $_.DisplayVersion }

    ''
    '== 9. PATH'
    $env:Path -split ';' | Where-Object { $_ } | ForEach-Object { "  $_" }
} *>&1 | ForEach-Object { "$_" } | Out-File -FilePath $out -Encoding utf8

Write-Host "저장했습니다: $out" -ForegroundColor Green
notepad $out
}
