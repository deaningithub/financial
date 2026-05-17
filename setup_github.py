#!/usr/bin/env python3
"""
GitHub Secrets 設置助手
幫助設置 Cloud Run 部署所需的 GitHub Secrets
"""
import os
import json
import base64
from pathlib import Path

def generate_service_account_key():
    """生成服務帳戶金鑰"""
    print("🔑 服務帳戶金鑰設置")
    print("=" * 50)

    key_path = Path('sa-key.json')
    if key_path.exists():
        print("✅ 找到現有金鑰文件")
        return key_path

    print("請執行以下命令建立服務帳戶金鑰：")
    print()
    print("1. 建立服務帳戶：")
    print("   gcloud iam service-accounts create financial-system-sa \\")
    print("     --display-name='Financial System Service Account'")
    print()
    print("2. 授予權限：")
    print("   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \\")
    print("     --member='serviceAccount:financial-system-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com' \\")
    print("     --role='roles/editor'")
    print()
    print("3. 建立金鑰：")
    print("   gcloud iam service-accounts keys create sa-key.json \\")
    print("     --iam-account=financial-system-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com")
    print()
    print("然後重新運行此腳本")

    return None

def setup_github_secrets():
    """設置 GitHub Secrets"""
    print("🔐 GitHub Secrets 設置")
    print("=" * 50)

    # 檢查服務帳戶金鑰
    key_path = generate_service_account_key()
    if not key_path:
        return

    # 讀取金鑰
    with open(key_path, 'r') as f:
        sa_key = json.load(f)

    # 從金鑰提取專案 ID
    project_id = sa_key['project_id']

    print(f"專案 ID: {project_id}")
    print()

    # 載入環境變數
    env_file = Path('.env.cloud')
    env_vars = {}

    if env_file.exists():
        print("📄 讀取環境變數...")
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
                    except ValueError:
                        continue

    # 顯示需要設置的 Secrets
    secrets = {
        'GCP_PROJECT_ID': project_id,
        'GCP_SA_KEY': base64.b64encode(json.dumps(sa_key).encode()).decode(),
        'CLOUD_SQL_CONNECTION_NAME': env_vars.get('CLOUD_SQL_CONNECTION_NAME', ''),
        'DB_USER': env_vars.get('DB_USER', 'postgres'),
        'DB_PASSWORD': env_vars.get('DB_PASSWORD', ''),
        'OPENAI_API_KEY': env_vars.get('OPENAI_API_KEY', ''),
    }

    print("請在 GitHub 倉庫中設置以下 Secrets：")
    print("路徑: https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions")
    print()

    for name, value in secrets.items():
        if value:
            display_value = value[:20] + "..." if len(value) > 20 else value
            status = "✅ 已設置" if value else "❌ 需要設置"
            print(f"{name}: {display_value} ({status})")
        else:
            print(f"{name}: ❌ 需要設置")

    print()
    print("重要提醒：")
    print("1. GCP_SA_KEY 必須是 base64 編碼的 JSON")
    print("2. 不要在代碼中硬編碼這些值")
    print("3. 定期輪換服務帳戶金鑰")
    print("4. 使用最小權限原則")

def generate_env_template():
    """生成環境變數模板"""
    print("📝 環境變數模板")
    print("=" * 50)

    template = """# Google Cloud 環境變數模板
# 複製此文件為 .env.cloud 並填入實際值

# Google Cloud 配置
GCP_PROJECT_ID=your-project-id
GCP_REGION=asia-east1
SERVICE_NAME=financial-system

# Cloud SQL 配置
CLOUD_SQL_CONNECTION_NAME=your-project-id:asia-east1:financial-system-db
DB_USER=postgres
DB_PASSWORD=your-secure-password

# API 金鑰
OPENAI_API_KEY=sk-your-openai-key

# 應用配置
FINANCIAL_TIMEZONE=Asia/Taipei
LOG_LEVEL=INFO

# Google Sheets 配置
GOOGLE_SHEET_MONITOR_ENABLED=true
GOOGLE_SHEET_MONITOR_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit

# Cloud Storage 配置
GCS_BUCKET_NAME=financial-system-reports
"""

    template_path = Path('.env.cloud.template')
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(template)

    print(f"✅ 已生成模板文件: {template_path}")
    print("請複製為 .env.cloud 並填入實際值")

def main():
    print("🚀 GitHub Secrets 設置助手")
    print("=" * 60)

    commands = {
        'secrets': setup_github_secrets,
        'template': generate_env_template,
        'all': lambda: (generate_env_template(), setup_github_secrets()),
    }

    import sys
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command in commands:
            commands[command]()
        else:
            print(f"未知命令: {command}")
            print(f"可用命令: {', '.join(commands.keys())}")
    else:
        print("請選擇命令:")
        print("  secrets  - 設置 GitHub Secrets")
        print("  template - 生成環境變數模板")
        print("  all      - 執行所有設置")

if __name__ == '__main__':
    main()
