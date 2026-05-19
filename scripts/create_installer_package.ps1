# CRM Backend - Package Creator for Windows (PowerShell)
Write-Host "=========================================" -ForegroundColor Blue
Write-Host "   Creating Ubuntu Installer Package" -ForegroundColor Blue
Write-Host "=========================================" -ForegroundColor Blue
Write-Host ""

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$packageName = "crm-backend-installer_$timestamp"

Write-Host "[i] Creating package directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $packageName | Out-Null

Write-Host "[i] Copying application files..." -ForegroundColor Yellow

if (Test-Path "app")        { Copy-Item -Path "app"        -Destination "$packageName\app"        -Recurse -Force }
if (Test-Path "alembic")    { Copy-Item -Path "alembic"    -Destination "$packageName\alembic"    -Recurse -Force }
if (Test-Path "migrations") { Copy-Item -Path "migrations" -Destination "$packageName\migrations" -Recurse -Force }

$filesToCopy = @("requirements.txt", "alembic.ini", ".env.example", "install_ubuntu.sh", "install_ubuntu_debug.sh", "uninstall_ubuntu.sh", "update_ubuntu.sh", "auto_update.sh", "auto_update.bat", "INSTALLER_README.md", "QUICK_INSTALL.md", "PACKAGE_README.md", "README.md")

foreach ($file in $filesToCopy) {
    if (Test-Path $file) { Copy-Item -Path $file -Destination "$packageName\" -Force }
}

Write-Host "[i] Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$packageName\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$packageName\backups" | Out-Null
New-Item -ItemType Directory -Force -Path "$packageName\updates" | Out-Null
New-Item -ItemType Directory -Force -Path "$packageName\app\uploads\comments" | Out-Null
New-Item -ItemType Directory -Force -Path "$packageName\app\uploads\chat_messages" | Out-Null
New-Item -ItemType Directory -Force -Path "$packageName\app\uploads\tickets" | Out-Null
New-Item -ItemType Directory -Force -Path "$packageName\app\static" | Out-Null

".gitkeep" | Out-File -FilePath "$packageName\logs\.gitkeep" -Encoding ASCII
".gitkeep" | Out-File -FilePath "$packageName\backups\.gitkeep" -Encoding ASCII

Write-Host "[i] Creating installation instructions..." -ForegroundColor Yellow
"CRM BACKEND - INSTALLATION INSTRUCTIONS" | Out-File -FilePath "$packageName\INSTALL.txt" -Encoding ASCII
"========================================" | Out-File -FilePath "$packageName\INSTALL.txt" -Encoding ASCII -Append
"1. Transfer to Ubuntu: scp -r $packageName username@server:/home/username/" | Out-File -FilePath "$packageName\INSTALL.txt" -Encoding ASCII -Append
"2. On Ubuntu: cd $packageName" | Out-File -FilePath "$packageName\INSTALL.txt" -Encoding ASCII -Append
"3. Make executable: chmod +x install_ubuntu.sh" | Out-File -FilePath "$packageName\INSTALL.txt" -Encoding ASCII -Append
"4. Install: ./install_ubuntu.sh" | Out-File -FilePath "$packageName\INSTALL.txt" -Encoding ASCII -Append

Write-Host "[i] Creating zip archive..." -ForegroundColor Yellow
$zipFile = "$packageName.zip"
Compress-Archive -Path $packageName -DestinationPath $zipFile -Force
Write-Host "[V] Created $zipFile" -ForegroundColor Green

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "   Package Created Successfully!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Package: $zipFile" -ForegroundColor Cyan
$size = (Get-Item $zipFile).Length / 1MB
Write-Host "Size: $("{0:N2}" -f $size) MB" -ForegroundColor Cyan
Write-Host ""
Write-Host "Transfer to Ubuntu and run: ./install_ubuntu.sh" -ForegroundColor Yellow
