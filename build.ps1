# Nhentai Downloader 打包脚本
$ErrorActionPreference = "Stop"

$PROJECT_DIR = $PSScriptRoot
$DIST_DIR = "$PROJECT_DIR\dist"
$SPEC_FILE = "$PROJECT_DIR\nhentai_downloader.spec"

# 清理旧构建
if (Test-Path "$DIST_DIR") {
    Remove-Item -Recurse -Force "$DIST_DIR"
}

# 打包
py -m PyInstaller `
    --noconfirm `
    --onefile `
    --name "NhentaiDownloader" `
    --add-data "$PROJECT_DIR\config.py;." `
    --add-data "$PROJECT_DIR\api_client.py;." `
    --add-data "$PROJECT_DIR\downloader.py;." `
    --add-data "$PROJECT_DIR\pdf_builder.py;." `
    --add-data "$PROJECT_DIR\viewer.py;." `
    --console `
    --icon "$PROJECT_DIR\icon.ico" `
    $PROJECT_DIR\app.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=========================="
    Write-Host "打包完成！EXE 位于: $DIST_DIR\NhentaiDownloader.exe"
    Write-Host "=========================="
} else {
    Write-Host "打包失败"
    exit 1
}