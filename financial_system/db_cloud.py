"""
Cloud SQL 連接層
支持 PostgreSQL 連接到 Google Cloud SQL
"""
from __future__ import annotations

import os
from typing import Optional
from sqlalchemy import create_engine, pool
from google.cloud.sql.connector import Connector

# 方案 A: Cloud SQL Connector（推薦）
def get_cloud_sql_engine():
    """建立 Cloud SQL 連接池"""
    if not os.getenv('CLOUD_SQL_CONNECTION_NAME'):
        raise ValueError("CLOUD_SQL_CONNECTION_NAME 未設定")
    
    connector = Connector()
    
    def getconn():
        return connector.connect(
            os.getenv('CLOUD_SQL_CONNECTION_NAME'),
            "pg8000",
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD'),
            db=os.getenv('DB_NAME', 'financial_system'),
        )
    
    engine = create_engine(
        "postgresql://",
        creator=getconn,
        poolclass=pool.NullPool,  # Cloud Run 不需要連接池
    )
    return engine


# 方案 B: 標準連接字符串（備選）
def get_postgres_engine():
    """建立標準 PostgreSQL 連接"""
    connection_string = os.getenv(
        'DATABASE_URL',
        'postgresql://postgres:password@localhost/financial_system'
    )
    
    engine = create_engine(
        connection_string,
        poolclass=pool.NullPool,
        echo=os.getenv('SQL_DEBUG', 'false').lower() == 'true'
    )
    return engine


def get_db_engine():
    """自動選擇連接方案"""
    if os.getenv('CLOUD_SQL_CONNECTION_NAME'):
        return get_cloud_sql_engine()
    else:
        return get_postgres_engine()


# SQLite 相容層（用於本地開發）
import sqlite3
from contextlib import contextmanager

@contextmanager
def get_sqlite_connection():
    """本地開發用"""
    db_path = os.getenv('SQLITE_DB_PATH', 'data/financial_data.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
