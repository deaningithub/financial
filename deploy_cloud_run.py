#!/usr/bin/env python3
"""
Google Cloud Run 部署管理腳本
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv

def run_command(cmd, description=""):
    """執行命令並處理錯誤"""
    if description:
        print(f"▶️  {description}")
    
    print(f"   $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ 錯誤: {result.stderr}")
        sys.exit(1)
    
    if result.stdout:
        print(f"   {result.stdout.strip()}")
    
    return result.stdout.strip()


def deploy_to_cloud_run():
    """部署到 Google Cloud Run"""
    
    # 載入環境變數
    load_dotenv('.env.cloud')
    
    project_id = os.getenv('GCP_PROJECT_ID')
    service_name = os.getenv('SERVICE_NAME', 'financial-system')
    region = os.getenv('GCP_REGION', 'asia-east1')
    
    if not project_id:
        print("❌ 缺少 GCP_PROJECT_ID")
        sys.exit(1)
    
    print("🚀 Google Cloud Run 部署流程")
    print("=" * 50)
    
    # 第 1 步：驗證環境
    print("\n📋 第 1 步：驗證環境")
    run_command(['gcloud', '--version'], "檢查 gcloud CLI")
    run_command(['gcloud', 'config', 'get-value', 'project'], "檢查當前項目")
    
    # 第 2 步：建立容器映像
    print("\n🐳 第 2 步：建立容器映像")
    image_name = f'gcr.io/{project_id}/{service_name}'
    run_command(
        ['docker', 'build', '-t', f'{image_name}:latest', '.'],
        f"建立 Docker 映像: {image_name}"
    )
    
    # 第 3 步：推送到 Container Registry
    print("\n📤 第 3 步：推送到 Container Registry")
    run_command(
        ['docker', 'push', f'{image_name}:latest'],
        "推送映像到 GCR"
    )
    
    # 第 4 步：部署到 Cloud Run
    print("\n☁️  第 4 步：部署到 Cloud Run")
    
    deploy_cmd = [
        'gcloud', 'run', 'deploy',
        service_name,
        '--image', f'{image_name}:latest',
        '--region', region,
        '--platform', 'managed',
        '--allow-unauthenticated',
        '--memory', '1Gi',
        '--timeout', '3600',
        '--max-instances', '100',
        '--set-env-vars',
        ','.join([
            f'CLOUD_SQL_CONNECTION_NAME={os.getenv("CLOUD_SQL_CONNECTION_NAME", "")}',
            f'DB_USER={os.getenv("DB_USER", "")}',
            f'DB_PASSWORD={os.getenv("DB_PASSWORD", "")}',
            f'OPENAI_API_KEY={os.getenv("OPENAI_API_KEY", "")}',
            f'OPENAI_MODEL={os.getenv("OPENAI_MODEL", "gpt-5.5")}',
            f'NEWS_QUERY_LIMIT={os.getenv("NEWS_QUERY_LIMIT", "60")}',
            f'KEYWORD_LIMIT={os.getenv("KEYWORD_LIMIT", "20")}',
            f'POLICY_QUERY_LIMIT={os.getenv("POLICY_QUERY_LIMIT", "24")}',
        ]),
        '--set-cloudsql-instances', os.getenv("CLOUD_SQL_CONNECTION_NAME", "")
    ]
    
    run_command(deploy_cmd, "部署服務到 Cloud Run")
    
    # 第 5 步：獲取服務 URL
    print("\n🔗 第 5 步：獲取服務 URL")
    url = run_command(
        [
            'gcloud', 'run', 'services', 'describe',
            service_name,
            '--region', region,
            '--format', 'value(status.url)'
        ],
        "獲取服務 URL"
    )
    
    print("\n" + "=" * 50)
    print("✅ 部署成功！")
    print(f"   服務 URL: {url}")
    print(f"   專案: {project_id}")
    print(f"   區域: {region}")
    print("=" * 50)
    
    return url


def setup_cloud_scheduler():
    """設定 Cloud Scheduler 定時任務"""
    
    load_dotenv('.env.cloud')
    
    project_id = os.getenv('GCP_PROJECT_ID')
    service_name = os.getenv('SERVICE_NAME', 'financial-system')
    region = os.getenv('GCP_REGION', 'asia-east1')
    schedule = os.getenv('SCHEDULE', '0 0 * * 1-5')  # Weekdays only, Asia/Taipei.
    
    scheduler_name = f'{service_name}-scheduler'
    
    print("\n⏰ 設定 Cloud Scheduler")
    print("=" * 50)
    
    # 獲取 Cloud Run URL
    url = run_command(
        [
            'gcloud', 'run', 'services', 'describe',
            service_name,
            '--region', region,
            '--format', 'value(status.url)'
        ],
        "獲取服務 URL"
    )
    
    # 建立排程工作
    run_command(
        [
            'gcloud', 'scheduler', 'jobs', 'create', 'http',
            scheduler_name,
            '--schedule', schedule,
            '--time-zone', 'Asia/Taipei',
            '--uri', f'{url}/run',
            '--http-method', 'POST',
            '--location', region,
            '--oidc-service-account-email',
            f'financial-system-sa@{project_id}.iam.gserviceaccount.com',
            '--oidc-token-audience', url
        ],
        f"建立排程工作: {scheduler_name}"
    )
    
    print(f"\n✅ 已設定每日排程")
    print(f"   排程: {schedule}")
    print(f"   時區: Asia/Taipei")


def setup_monitoring():
    """設定監控告警"""
    
    load_dotenv('.env.cloud')
    
    project_id = os.getenv('GCP_PROJECT_ID')
    service_name = os.getenv('SERVICE_NAME', 'financial-system')
    
    print("\n📊 設定監控")
    print("=" * 50)
    
    # 建立日誌路由到 Cloud Logging
    print(f"✅ 日誌自動轉發到 Cloud Logging")
    print(f"   專案: {project_id}")
    print(f"   服務: {service_name}")
    
    # 輸出監控儀表板連結
    dashboard_url = f'https://console.cloud.google.com/run/detail/{os.getenv("GCP_REGION", "asia-east1")}/{service_name}'
    print(f"\n📈 監控儀表板:")
    print(f"   {dashboard_url}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'deploy':
            deploy_to_cloud_run()
        elif command == 'scheduler':
            setup_cloud_scheduler()
        elif command == 'monitoring':
            setup_monitoring()
        else:
            print(f"未知命令: {command}")
            sys.exit(1)
    else:
        # 執行完整部署
        deploy_to_cloud_run()
        setup_cloud_scheduler()
        setup_monitoring()
