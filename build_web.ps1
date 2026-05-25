# Nhentai Downloader Web 版打包脚本
$ErrorActionPreference = "Stop"

$PROJECT_DIR = $PSScriptRoot
$DIST_DIR = "$PROJECT_DIR\dist_web"

# 清理旧构建
if (Test-Path "$DIST_DIR") {
    Remove-Item -Recurse -Force "$DIST_DIR"
}

Write-Host "开始打包 NhentaiDownloader_Web..."

# 打包
py -m PyInstaller `
    --noconfirm `
    --onefile `
    --name "NhentaiDownloader_Web" `
    --specpath "$PROJECT_DIR" `
    --distpath "$DIST_DIR" `
    "$PROJECT_DIR\NhentaiDownloader_Web.spec"

if ($LASTEXITCODE -eq 0) {
    $EXE_PATH = "$DIST_DIR\NhentaiDownloader_Web.exe"
    $EXE_SIZE = (Get-Item $EXE_PATH).Length / 1MB

    Write-Host ""
    Write-Host "=================================="
    Write-Host "打包完成！"
    Write-Host "EXE 路径: $EXE_PATH"
    Write-Host "文件大小: $([math]::Round($EXE_SIZE, 1)) MB"
    Write-Host "=================================="
    Write-Host ""
    Write-Host "运行方式: 双击 EXE，自动打开浏览器界面"
    Write-Host "按 Ctrl+C 停止服务"
} else {
    Write-Host "打包失败，退出码: $LASTEXITCODE"
    exit 1
}