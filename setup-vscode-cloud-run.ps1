# VS Code + Cloud Run 開發環境設置腳本
# 使用: .\setup-vscode-cloud-run.ps1

param(
    [switch]$SkipToolsCheck,
    [switch]$SkipExtensions,
    [switch]$SkipGitHub,
    [switch]$SkipCloud,
    [string]$ProjectId = "",
    [string]$GitHubRepo = ""
)

# 色彩定義
$Green = "`e[32m"
$Red = "`e[31m"
$Yellow = "`e[33m"
$Blue = "`e[34m"
$Reset = "`e[0m"

function Write-Info {
    param([string]$Message)
    Write-Host "${Blue}ℹ️  ${Message}${Reset}"
}

function Write-Success {
    param([string]$Message)
    Write-Host "${Green}✅ ${Message}${Reset}"
}

function Write-Error {
    param([string]$Message)
    Write-Host "${Red}❌ ${Message}${Reset}"
    exit 1
}

function Write-Warning {
    param([string]$Message)
    Write-Host "${Yellow}⚠️  ${Message}${Reset}"
}

# 第 1 步：檢查必要工具
function Check-Tools {
    if ($SkipToolsCheck) { return }

    Write-Info "檢查必要工具..."

    $tools = @(
        @{Name = "git"; Command = "git --version"; InstallUrl = "https://git-scm.com/downloads"},
        @{Name = "python"; Command = "python --version"; InstallUrl = "https://python.org/downloads"},
        @{Name = "docker"; Command = "docker --version"; InstallUrl = "https://docker.com/get-started"},
        @{Name = "gcloud"; Command = "gcloud --version"; InstallUrl = "https://cloud.google.com/sdk/docs/install-cloud-sdk"}
    )

    $missingTools = @()

    foreach ($tool in $tools) {
        try {
            $result = Invoke-Expression $tool.Command 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "$($tool.Name) 已安裝"
            } else {
                $missingTools += $tool
            }
        } catch {
            $missingTools += $tool
        }
    }

    if ($missingTools.Count -gt 0) {
        Write-Warning "缺少以下工具："
        foreach ($tool in $missingTools) {
            Write-Host "  - $($tool.Name): $($tool.InstallUrl)"
        }
        Write-Error "請先安裝缺少的工具，然後重新運行此腳本"
    }

    Write-Success "所有工具已安裝"
}

# 第 2 步：設置 VS Code 插件
function Setup-VSCodeExtensions {
    if ($SkipExtensions) { return }

    Write-Info "設置 VS Code 插件..."

    $extensions = @(
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-python.black-formatter",
        "ms-python.flake8",
        "ms-azuretools.vscode-docker",
        "googlecloudtools.cloudcode",
        "github.vscode-github-actions",
        "eamodio.gitlens",
        "ms-vscode-remote.remote-containers",
        "redhat.vscode-yaml"
    )

    foreach ($ext in $extensions) {
        Write-Info "安裝 $ext..."
        try {
            & code --install-extension $ext --force 2>$null
            Write-Success "$ext 已安裝"
        } catch {
            Write-Warning "$ext 安裝失敗 (可能已安裝)"
        }
    }

    Write-Success "VS Code 插件設置完成"
}

# 第 3 步：設置 Git 和 GitHub
function Setup-GitHub {
    if ($SkipGitHub) { return }

    Write-Info "設置 Git 和 GitHub..."

    # 檢查 Git 配置
    $gitConfig = git config --list --local 2>$null
    if (-not $gitConfig) {
        Write-Info "配置 Git 用戶信息..."
        $name = Read-Host "請輸入您的 Git 用戶名"
        $email = Read-Host "請輸入您的 Git 郵箱"

        git config --local user.name $name
        git config --local user.email $email
        Write-Success "Git 配置完成"
    }

    # 檢查遠程倉庫
    $remote = git remote -v 2>$null
    if (-not $remote) {
        if (-not $GitHubRepo) {
            $GitHubRepo = Read-Host "請輸入 GitHub 倉庫 URL (例如: https://github.com/username/repo.git)"
        }

        if ($GitHubRepo) {
            git remote add origin $GitHubRepo
            Write-Success "GitHub 遠程倉庫已設置"
        }
    }

    # 生成 GitHub Secrets 指南
    Write-Info "運行 GitHub Secrets 設置助手..."
    python setup_github.py template
    python setup_github.py secrets

    Write-Success "Git 和 GitHub 設置完成"
}

# 第 4 步：設置 Google Cloud
function Setup-GoogleCloud {
    if ($SkipCloud) { return }

    Write-Info "設置 Google Cloud..."

    # 檢查 gcloud 登錄
    $account = gcloud config get-value account 2>$null
    if (-not $account -or $account -eq "(unset)") {
        Write-Info "請登錄 Google Cloud..."
        gcloud auth login
    }

    # 設置專案
    if (-not $ProjectId) {
        $ProjectId = Read-Host "請輸入 Google Cloud 專案 ID"
    }

    if ($ProjectId) {
        gcloud config set project $ProjectId
        Write-Success "專案已設置: $ProjectId"

        # 啟用 API
        Write-Info "啟用必要的 API..."
        $apis = @(
            "run.googleapis.com",
            "containerregistry.googleapis.com",
            "cloudbuild.googleapis.com",
            "cloudscheduler.googleapis.com",
            "sqladmin.googleapis.com"
        )

        foreach ($api in $apis) {
            gcloud services enable $api --quiet 2>$null
        }

        Write-Success "API 已啟用"
    }

    Write-Success "Google Cloud 設置完成"
}

# 第 5 步：設置本地開發環境
function Setup-LocalEnvironment {
    Write-Info "設置本地開發環境..."

    # 安裝 Python 依賴
    Write-Info "安裝 Python 依賴..."
    python -m pip install --upgrade pip
    pip install -r requirements-cloud.txt

    # 檢查環境變數文件
    $envFile = ".env.cloud"
    if (-not (Test-Path $envFile)) {
        Write-Warning ".env.cloud 文件不存在"
        Write-Info "請運行: python setup_github.py template"
        Write-Info "然後編輯 .env.cloud 文件"
    }

    # 測試本地運行
    Write-Info "測試本地環境..."
    try {
        python -c "import financial_system; print('✅ 模塊導入成功')" 2>$null
        Write-Success "本地環境測試通過"
    } catch {
        Write-Warning "本地環境測試失敗，請檢查依賴安裝"
    }

    Write-Success "本地開發環境設置完成"
}

# 第 6 步：最終檢查和說明
function Final-Check {
    Write-Info "執行最終檢查..."

    $checks = @(
        @{Name = "VS Code"; Command = "code --version"; Required = $true},
        @{Name = "Python 依賴"; Command = "python -c 'import financial_system'"; Required = $true},
        @{Name = "Docker"; Command = "docker --version"; Required = $true},
        @{Name = "Google Cloud"; Command = "gcloud config get-value project"; Required = $true},
        @{Name = "Git"; Command = "git --version"; Required = $true}
    )

    $allPassed = $true

    foreach ($check in $checks) {
        try {
            $result = Invoke-Expression $check.Command 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Success "$($check.Name) ✓"
            } else {
                if ($check.Required) {
                    Write-Error "$($check.Name) ✗"
                    $allPassed = $false
                } else {
                    Write-Warning "$($check.Name) ✗ (可選)"
                }
            }
        } catch {
            if ($check.Required) {
                Write-Error "$($check.Name) ✗"
                $allPassed = $false
            } else {
                Write-Warning "$($check.Name) ✗ (可選)"
            }
        }
    }

    if ($allPassed) {
        Write-Host ""
        Write-Host "${Green}╔══════════════════════════════════════════════════════════╗${Reset}"
        Write-Host "${Green}║   🎉 設置完成！您現在可以開始開發了                   ║${Reset}"
        Write-Host "${Green}╚══════════════════════════════════════════════════════════╝${Reset}"
        Write-Host ""

        Write-Info "下一步："
        Write-Host "1. 在 VS Code 中打開項目: code ."
        Write-Host "2. 閱讀完整指南: VS_CODE_CLOUD_RUN_README.md"
        Write-Host "3. 開始開發: 編輯代碼 → 推送 → 自動部署"
        Write-Host ""
        Write-Host "常用命令："
        Write-Host "  本地測試: python local_dev.py local"
        Write-Host "  部署雲端: python deploy_cloud_run.py"
        Write-Host "  查看日誌: gcloud run services logs read financial-system"
    } else {
        Write-Error "設置未完成，請檢查上述錯誤"
    }
}

# 主函數
function Main {
    Write-Host "${Blue}"
    Write-Host "╔══════════════════════════════════════════════════════╗"
    Write-Host "║  VS Code + Cloud Run 開發環境設置工具              ║"
    Write-Host "╚══════════════════════════════════════════════════════╝"
    Write-Host "${Reset}"

    Write-Host "此腳本將幫助您設置完整的開發環境"
    Write-Host ""

    Check-Tools
    Setup-VSCodeExtensions
    Setup-GitHub
    Setup-GoogleCloud
    Setup-LocalEnvironment
    Final-Check
}

Main
