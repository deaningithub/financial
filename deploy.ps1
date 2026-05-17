# Google Cloud Run 部署腳本 (PowerShell)
# 使用: .\deploy.ps1

param(
    [string]$Command = "full",
    [string]$ProjectId = "",
    [string]$ServiceName = "financial-system",
    [string]$Region = "asia-east1"
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

# 第 1 步：驗證先決條件
function Check-Prerequisites {
    Write-Info "檢查先決條件..."
    
    # 檢查 gcloud
    if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
        Write-Error "gcloud CLI 未安裝。請訪問: https://cloud.google.com/sdk/docs/install-cloud-sdk"
    }
    
    # 檢查 Docker
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "Docker 未安裝。請訪問: https://docs.docker.com/get-docker/"
    }
    
    Write-Success "先決條件已驗證"
}

# 第 2 步：設定 Google Cloud
function Setup-GCloud {
    Write-Info "設定 Google Cloud..."
    
    if (-not $ProjectId) {
        $ProjectId = gcloud config get-value project
        if (-not $ProjectId) {
            Write-Error "未設定 Google Cloud 項目"
        }
    }
    
    Write-Success "專案設定: $ProjectId"
    return $ProjectId
}

# 第 3 步：啟用必要的 API
function Enable-APIs {
    Write-Info "啟用必要的 API..."
    
    $apis = @(
        "run.googleapis.com",
        "containerregistry.googleapis.com",
        "cloudbuild.googleapis.com",
        "cloudscheduler.googleapis.com",
        "sqladmin.googleapis.com",
        "logging.googleapis.com"
    )
    
    foreach ($api in $apis) {
        Write-Info "啟用 $api..."
        gcloud services enable $api --quiet 2>$null
    }
    
    Write-Success "所有 API 已啟用"
}

# 第 4 步：建立服務帳戶
function Setup-ServiceAccount {
    param([string]$ProjectId)
    
    Write-Info "設定服務帳戶..."
    
    $saName = "financial-system-sa"
    $saEmail = "$saName@$ProjectId.iam.gserviceaccount.com"
    
    # 檢查服務帳戶是否存在
    $saExists = gcloud iam service-accounts list --format="value(email)" --filter="email:$saEmail" --quiet 2>$null
    
    if (-not $saExists) {
        Write-Info "建立服務帳戶: $saName"
        gcloud iam service-accounts create $saName `
            --display-name="Financial System Service Account" `
            --quiet 2>$null
    }
    
    # 授予 Editor 角色
    Write-Info "授予權限..."
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:$saEmail" `
        --role="roles/editor" `
        --quiet 2>$null
    
    Write-Success "服務帳戶已設定: $saEmail"
}

# 第 5 步：建立 Docker 映像
function Build-Docker-Image {
    param([string]$ProjectId)
    
    Write-Info "建立 Docker 映像..."
    
    $imageName = "gcr.io/$ProjectId/$ServiceName"
    
    Write-Host "執行: docker build -t $imageName:latest ."
    docker build -t "$imageName:latest" .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker 建立失敗"
    }
    
    Write-Success "Docker 映像已建立: $imageName"
    return $imageName
}

# 第 6 步：推送到 Container Registry
function Push-To-Registry {
    param([string]$ImageName)
    
    Write-Info "推送映像到 Google Container Registry..."
    
    Write-Host "執行: docker push $ImageName:latest"
    docker push "$ImageName:latest"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "映像推送失敗"
    }
    
    Write-Success "映像已推送到 GCR"
}

# 第 7 步：部署到 Cloud Run
function Deploy-To-CloudRun {
    param([string]$ProjectId, [string]$ImageName)
    
    Write-Info "部署到 Google Cloud Run..."
    
    $deployCmd = @(
        "gcloud", "run", "deploy",
        $ServiceName,
        "--image", "$ImageName`:latest",
        "--region", $Region,
        "--platform", "managed",
        "--allow-unauthenticated",
        "--memory", "1Gi",
        "--timeout", "3600",
        "--max-instances", "100",
        "--quiet"
    )
    
    Write-Host "執行: $($deployCmd -join ' ')"
    & $deployCmd[0] $deployCmd[1..($deployCmd.Count-1)]
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Cloud Run 部署失敗"
    }
    
    Write-Success "已部署到 Cloud Run"
}

# 第 8 步：設定 Cloud Scheduler
function Setup-CloudScheduler {
    param([string]$ProjectId)
    
    Write-Info "設定 Cloud Scheduler..."
    
    # 獲取服務 URL
    $serviceUrl = gcloud run services describe $ServiceName `
        --region $Region `
        --format "value(status.url)" `
        --quiet 2>$null
    
    Write-Success "服務 URL: $serviceUrl"
    
    # 建立排程工作
    $schedulerName = "$ServiceName-daily"
    
    Write-Info "建立排程工作: $schedulerName"
    gcloud scheduler jobs create http $schedulerName `
        --schedule="0 0 * * 1-5" `
        --time-zone="Asia/Taipei" `
        --uri="$serviceUrl/run" `
        --http-method="POST" `
        --location=$Region `
        --quiet 2>$null
    
    Write-Success "Cloud Scheduler 已設定"
}

# 主執行函數
function Main {
    Write-Host "${Blue}"
    Write-Host "╔════════════════════════════════════════════════════╗"
    Write-Host "║   Google Cloud Run 部署管理工具                 ║"
    Write-Host "╚════════════════════════════════════════════════════╝"
    Write-Host "${Reset}"
    
    Check-Prerequisites
    
    if ($Command -eq "check") {
        Write-Success "所有先決條件已驗證"
        return
    }
    
    $ProjectId = Setup-GCloud
    
    if ($Command -eq "setup" -or $Command -eq "full") {
        Enable-APIs
        Setup-ServiceAccount -ProjectId $ProjectId
    }
    
    if ($Command -eq "build" -or $Command -eq "full") {
        $imageName = Build-Docker-Image -ProjectId $ProjectId
        Push-To-Registry -ImageName $imageName
    }
    
    if ($Command -eq "deploy" -or $Command -eq "full") {
        $imageName = "gcr.io/$ProjectId/$ServiceName"
        Deploy-To-CloudRun -ProjectId $ProjectId -ImageName $imageName
        Setup-CloudScheduler -ProjectId $ProjectId
    }
    
    Write-Host ""
    Write-Success "部署流程完成！"
    Write-Host ""
    
    $dashboardUrl = "https://console.cloud.google.com/run/detail/$Region/$ServiceName"
    Write-Info "監控儀表板: $dashboardUrl"
}

Main
