#!/usr/bin/env python3
"""
本地 Cloud Run 模擬器
用於在本地測試 Cloud Run 環境
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_local_simulation():
    """在本地模擬 Cloud Run 環境"""
    print("🚀 本地 Cloud Run 模擬器")
    print("=" * 50)

    # 設定環境變數（模擬 Cloud Run）
    env = os.environ.copy()
    env.update({
        'PORT': '8080',
        'K_SERVICE': 'financial-system-local',
        'K_REVISION': 'local-001',
        'K_CONFIGURATION': 'financial-system-local',
        'SERVICE_ACCOUNT_EMAIL': 'local-dev@financial-system.iam.gserviceaccount.com',

        # 模擬雲端路徑
        'DATA_DIR': '/tmp/data',
        'OUTPUT_DIR': '/tmp/outputs',
        'LOG_DIR': '/tmp/logs',

        # 從 .env.cloud 讀取
        'PYTHONPATH': str(Path(__file__).parent),
    })

    # 載入雲端環境變數
    env_file = Path('.env.cloud')
    if env_file.exists():
        print("📄 載入 .env.cloud 配置")
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env[key] = value
                    print(f"   {key}={value[:20]}{'...' if len(value) > 20 else ''}")

    # 建立必要目錄
    for dir_path in ['/tmp/data', '/tmp/outputs', '/tmp/logs']:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    # 啟動應用
    print("\n🏃 啟動應用...")
    cmd = [sys.executable, '-m', 'financial_system.cli', 'run']

    try:
        subprocess.run(cmd, env=env, check=True)
    except KeyboardInterrupt:
        print("\n⏹️  應用已停止")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 應用執行失敗: {e}")
        return 1

    return 0

def run_docker_simulation():
    """使用 Docker 模擬 Cloud Run 環境"""
    print("🐳 Docker Cloud Run 模擬器")
    print("=" * 50)

    image_name = "financial-system:local"

    # 建立映像
    print("🏗️  建立 Docker 映像...")
    build_cmd = [
        "docker", "build",
        "-t", image_name,
        "-f", "Dockerfile",
        "."
    ]

    try:
        subprocess.run(build_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker 建立失敗: {e}")
        return 1

    # 運行容器
    print("🏃 運行容器...")
    run_cmd = [
        "docker", "run",
        "--rm",
        "-p", "8080:8080",
        "-e", "PORT=8080",
        "-e", "K_SERVICE=financial-system-docker",
        "-v", f"{Path.cwd() / 'data'}:/tmp/data",
        "-v", f"{Path.cwd() / 'outputs'}:/tmp/outputs",
        "-v", f"{Path.cwd() / 'logs'}:/tmp/logs",
        "--name", "financial-system-dev",
        image_name
    ]

    try:
        subprocess.run(run_cmd, check=True)
    except KeyboardInterrupt:
        print("\n⏹️  容器已停止")
        # 清理容器
        subprocess.run(["docker", "rm", "-f", "financial-system-dev"], check=False)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 容器執行失敗: {e}")
        return 1

    return 0

def setup_dev_environment():
    """設定開發環境"""
    print("🔧 設定開發環境")
    print("=" * 50)

    # 安裝依賴
    print("📦 安裝 Python 依賴...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            "-r", "requirements-cloud.txt"
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ 依賴安裝失敗: {e}")
        return 1

    # 檢查工具
    tools = ['docker', 'gcloud']
    for tool in tools:
        try:
            result = subprocess.run([tool, '--version'],
                                  capture_output=True, text=True, check=True)
            print(f"✅ {tool}: {result.stdout.strip().split()[0]}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"⚠️  {tool}: 未安裝")

    print("\n✅ 開發環境設定完成")
    return 0

def main():
    parser = argparse.ArgumentParser(description='Cloud Run 本地模擬器')
    parser.add_argument('command',
                       choices=['local', 'docker', 'setup'],
                       help='執行命令')
    parser.add_argument('--port', default='8080',
                       help='服務端口 (預設: 8080)')

    args = parser.parse_args()

    if args.command == 'local':
        return run_local_simulation()
    elif args.command == 'docker':
        return run_docker_simulation()
    elif args.command == 'setup':
        return setup_dev_environment()

if __name__ == '__main__':
    sys.exit(main())
