#!/usr/bin/env bash
# Cloud SQL PostgreSQL 初始化腳本

set -e

# 顏色定義
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🗄️  Cloud SQL PostgreSQL 初始化${NC}"
echo "=================================================="

# 配置
PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project)}
INSTANCE_NAME=${INSTANCE_NAME:-"financial-system-db"}
REGION=${GCP_REGION:-"asia-east1"}
DB_VERSION="POSTGRES_15"

echo -e "${BLUE}步驟 1: 建立 Cloud SQL 實例${NC}"
echo "執行: gcloud sql instances create $INSTANCE_NAME ..."

gcloud sql instances create $INSTANCE_NAME \
    --database-version=$DB_VERSION \
    --tier=db-f1-micro \
    --region=$REGION \
    --availability-type=ZONAL \
    --backup-start-time=00:00 \
    --retained-backups-count=7 \
    --transaction-log-retention-days=7 \
    --database-flags=cloudsql_iam_authentication=on \
    --quiet

echo -e "${GREEN}✅ 實例已建立${NC}"

echo -e "${BLUE}步驟 2: 建立數據庫${NC}"

gcloud sql databases create financial_system \
    --instance=$INSTANCE_NAME

echo -e "${GREEN}✅ 數據庫已建立${NC}"

echo -e "${BLUE}步驟 3: 建立資料庫用戶${NC}"

# 生成隨機密碼
DB_PASSWORD=$(openssl rand -base64 32)

gcloud sql users create postgres \
    --instance=$INSTANCE_NAME \
    --password=$DB_PASSWORD

echo -e "${GREEN}✅ 用戶已建立${NC}"
echo "密碼: $DB_PASSWORD"
echo "⚠️  請保存這個密碼並設定到環境變數中"

echo -e "${BLUE}步驟 4: 配置連接${NC}"

CONNECTION_NAME="$PROJECT_ID:$REGION:$INSTANCE_NAME"
echo "連接字符串 (Cloud SQL Connector): $CONNECTION_NAME"

echo ""
echo -e "${GREEN}✅ Cloud SQL 初始化完成${NC}"
echo ""
echo "設定環境變數:"
echo "  export CLOUD_SQL_CONNECTION_NAME='$CONNECTION_NAME'"
echo "  export DB_PASSWORD='$DB_PASSWORD'"
