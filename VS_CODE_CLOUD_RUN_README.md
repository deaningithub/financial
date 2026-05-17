# VS Code + Cloud Run 開發環境設置指南

本指南將幫助您設置一個完整的本地 VS Code 開發環境，與 Google Cloud Run 無縫集成。

## 📋 總覽

```
本地 VS Code ←→ GitHub ←→ Cloud Run
     ↓              ↓           ↓
   編輯代碼 → 推送代碼 → 自動部署
     ↓              ↓           ↓
   調試測試 ←  CI/CD ← 雲端運行
```

## 🚀 快速開始

### 步驟 1：安裝必要工具

```powershell
# 1. 安裝 VS Code
# https://code.visualstudio.com/

# 2. 安裝推薦插件
# 在 VS Code 中按 Ctrl+Shift+P，輸入 "Extensions: Show Recommended"
# 安裝所有推薦的插件

# 3. 安裝 Google Cloud SDK
# https://cloud.google.com/sdk/docs/install-cloud-sdk

# 4. 安裝 Docker Desktop
# https://www.docker.com/products/docker-desktop

# 5. 驗證安裝
gcloud --version
docker --version
```

### 步驟 2：設置開發環境

```powershell
# 1. 複製項目
git clone https://github.com/your-username/financial-system.git
cd financial-system

# 2. 設置 Python 環境
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements-cloud.txt

# 3. 設置 Google Cloud
gcloud init
gcloud config set project YOUR_PROJECT_ID

# 4. 運行設置助手
python setup_github.py template  # 生成環境變數模板
python setup_github.py secrets   # 設置 GitHub Secrets 指南
```

### 步驟 3：本地開發

```powershell
# 1. 在 VS Code 中打開項目
code .

# 2. 使用 VS Code 任務
# Ctrl+Shift+P → "Tasks: Run Task" → 選擇任務

# 3. 本地測試
python local_dev.py local    # 本地模擬 Cloud Run
python local_dev.py docker   # Docker 模擬 Cloud Run

# 4. 代碼格式化
# Ctrl+Shift+P → "Python: Format Document"
```

### 步驟 4：部署到雲端

```powershell
# 1. 推送代碼到 GitHub
git add .
git commit -m "feat: 添加新功能"
git push origin main

# 2. 自動觸發 GitHub Actions 部署
# 查看: https://github.com/your-repo/actions

# 3. 或手動部署
python deploy_cloud_run.py

# 4. 檢查部署狀態
gcloud run services describe financial-system --region=asia-east1
```

## 🔧 VS Code 配置詳解

### 推薦插件

| 插件 | 用途 | 安裝命令 |
|------|------|---------|
| **Python** | Python 開發 | `ms-python.python` |
| **Pylance** | Python 語言服務 | `ms-python.vscode-pylance` |
| **Black** | 代碼格式化 | `ms-python.black-formatter` |
| **Docker** | Docker 支持 | `ms-azuretools.vscode-docker` |
| **Cloud Code** | Google Cloud 集成 | `googlecloudtools.cloudcode` |
| **GitHub Actions** | CI/CD 支持 | `github.vscode-github-actions` |
| **GitLens** | Git 增強功能 | `eamodio.gitlens` |

### VS Code 任務

在 VS Code 中按 `Ctrl+Shift+P`，輸入 "Tasks: Run Task"：

- **安裝依賴** - 安裝 Python 依賴
- **運行測試** - 執行測試套件
- **代碼格式化** - 格式化代碼
- **本地運行** - 本地運行應用
- **建立 Docker 映像** - 建立容器映像
- **部署到 Cloud Run** - 部署到雲端
- **檢查 Cloud Run 日誌** - 查看雲端日誌

### 調試配置

在 VS Code 中按 `F5` 或使用調試面板：

- **Python: 當前文件** - 調試當前打開的文件
- **Python: 主程序** - 調試主應用
- **Python: 測試系統** - 調試測試
- **Docker: 附加到容器** - 調試 Docker 容器

## 🔄 開發工作流程

### 日常開發

```mermaid
graph LR
    A[編輯代碼] --> B[本地測試]
    B --> C[提交代碼]
    C --> D[推送 GitHub]
    D --> E[GitHub Actions]
    E --> F[部署 Cloud Run]
    F --> G[雲端測試]
```

### 具體步驟

1. **編輯代碼**
   - 在 VS Code 中修改代碼
   - 使用自動格式化 (Ctrl+S)

2. **本地測試**
   ```powershell
   # 使用 VS Code 任務
   Ctrl+Shift+P → "Tasks: Run Task" → "本地運行"

   # 或使用模擬器
   python local_dev.py local
   ```

3. **提交代碼**
   ```powershell
   git add .
   git commit -m "feat: 添加新功能"
   ```

4. **推送並部署**
   ```powershell
   git push origin main
   # GitHub Actions 會自動部署
   ```

5. **檢查部署**
   - 查看 GitHub Actions 日誌
   - 檢查 Cloud Run 服務狀態

## 🐛 調試與故障排除

### 本地調試

```powershell
# 1. 使用 VS Code 調試器
# F5 或 調試面板 → 選擇配置

# 2. 查看日誌
# Ctrl+Shift+P → "Python: Show Output"

# 3. 使用斷點
# 點擊行號左側設置斷點
```

### 雲端調試

```powershell
# 1. 查看 Cloud Run 日誌
gcloud run services logs read financial-system --region=asia-east1

# 2. 使用 VS Code 任務
# "檢查 Cloud Run 日誌"

# 3. 遠程調試 (高級)
# 在代碼中添加調試服務器
# 使用 SSH 隧道連接
```

### 常見問題

| 問題 | 解決方案 |
|------|---------|
| **模塊未找到** | 檢查 Python 解釋器和依賴安裝 |
| **Docker 建立失敗** | 檢查 Dockerfile 和 .dockerignore |
| **部署失敗** | 查看 GitHub Actions 日誌 |
| **環境變數錯誤** | 檢查 .env.cloud 文件 |
| **權限錯誤** | 驗證 GCP 服務帳戶權限 |

## 🔐 安全配置

### GitHub Secrets

在 GitHub 倉庫設置以下 Secrets：

```
GCP_PROJECT_ID        # Google Cloud 專案 ID
GCP_SA_KEY           # 服務帳戶金鑰 (base64)
CLOUD_SQL_CONNECTION_NAME  # Cloud SQL 連接字符串
DB_USER              # 數據庫用戶名
DB_PASSWORD          # 數據庫密碼
OPENAI_API_KEY       # OpenAI API 金鑰
```

### 本地安全

```powershell
# 1. 不要提交敏感文件
echo ".env*" >> .gitignore
echo "sa-key.json" >> .gitignore

# 2. 使用環境變數
# 不要在代碼中硬編碼密鑰

# 3. 定期輪換金鑰
# 每 90 天輪換服務帳戶金鑰
```

## 📊 監控與日誌

### Cloud Run 監控

```powershell
# 1. Cloud Run 儀表板
# https://console.cloud.google.com/run

# 2. 日誌查看
gcloud run services logs read financial-system --region=asia-east1 --follow

# 3. 指標監控
# https://console.cloud.google.com/monitoring
```

### GitHub Actions 監控

```powershell
# 1. Actions 儀表板
# https://github.com/your-repo/actions

# 2. 工作流程狀態
# 查看每個推送的部署狀態
```

## 🚀 進階功能

### 熱重載開發

```powershell
# 1. 安裝 reload 依賴
pip install reload

# 2. 修改代碼添加重載
import reload
reload.watch()

# 3. 本地開發時自動重載
```

### 遠程開發

```powershell
# 1. 使用 GitHub Codespaces
# 在 GitHub 中開啟 Codespaces

# 2. 或使用 VS Code Remote SSH
# 連接到雲端 VM 進行開發
```

### 自動化測試

```powershell
# 1. 設置測試
# 在 .vscode/settings.json 中配置 pytest

# 2. 運行測試
# Ctrl+Shift+P → "Python: Run All Tests"

# 3. 測試覆蓋率
pip install pytest-cov
pytest --cov=financial_system
```

## 📞 支持

如果遇到問題：

1. 檢查此文檔的故障排除部分
2. 查看 GitHub Issues
3. 聯繫開發團隊

---

**🎉 現在您已經設置好完整的 VS Code + Cloud Run 開發環境！**