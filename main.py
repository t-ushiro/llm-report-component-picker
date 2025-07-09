"""
AWS App Runner用のFastAPI実装
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import logging
from datetime import datetime

# モックジェネレーターをインポート
from report_generator_mock import MockReportGenerator

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Report Generator API",
    description="Shadcnコンポーネントを使用したレポートレイアウト生成API",
    version="1.0.0"
)

# CORS設定（必要に応じて調整）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では特定のドメインに制限
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# リクエストモデル
class ReportRequest(BaseModel):
    user_request: str
    s3_paths: List[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_request": "月次売上レポートを作成してください。日別の売上推移と製品カテゴリ別の売上を見たいです。",
                "s3_paths": [
                    "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json",
                    "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/category-sales.json"
                ]
            }
        }

# APIキー認証（本番環境用）
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """APIキー認証（環境変数で無効化可能）"""
    # API_KEY_REQUIREDがfalseの場合は認証をスキップ
    if os.getenv("API_KEY_REQUIRED", "true").lower() == "false":
        return "no-auth"
    
    if not x_api_key:
        raise HTTPException(status_code=403, detail="API Key required")
    
    if x_api_key != os.getenv("API_KEY", "your-secure-api-key"):
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    return x_api_key

# ルートエンドポイント
@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "Report Generator API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

# ヘルスチェック
@app.get("/health")
async def health():
    """ヘルスチェックエンドポイント"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "report-generator-api"
    }

# レポート生成エンドポイント
@app.post("/generate-report", dependencies=[Depends(verify_api_key)])
async def generate_report(request: ReportRequest):
    """レポート生成エンドポイント"""
    logger.info(f"Received report generation request: {request.user_request}")
    
    # S3パスの検証（ホワイトリスト）
    allowed_bucket = os.getenv("ALLOWED_S3_BUCKET", "kizukai-ds-tmp")
    for path in request.s3_paths:
        if not path.startswith(f"s3://{allowed_bucket}/"):
            logger.warning(f"Invalid S3 path attempted: {path}")
            raise HTTPException(status_code=400, detail=f"Invalid S3 path: {path}")
    
    try:
        # レポート生成
        generator = MockReportGenerator()
        report = generator.generate_report(
            user_request=request.user_request,
            s3_paths=request.s3_paths
        )
        
        logger.info(f"Report generated successfully: {report['reportId']}")
        
        return {
            "status": "success",
            "report": report,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

# サンプルS3パス
@app.get("/sample-s3-paths")
async def get_sample_s3_paths():
    """利用可能なサンプルS3パスを返す"""
    return {
        "sample_paths": [
            "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json",
            "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/category-sales.json"
        ],
        "description": "利用可能なサンプルS3パス"
    }

# 利用可能なコンポーネント
@app.get("/available-components")
async def get_available_components():
    """利用可能なコンポーネント一覧を返す"""
    return {
        "header_components": ["MainHeader", "SubHeader"],
        "main_components": ["DataTable", "BarChart", "Card", "TextField", "MarkdownField"],
        "data_sources": ["TEXT", "S3"],
        "bar_chart_required_props": ["xField", "yFields"],
        "card_required_props": ["title"]
    }

# エラーハンドラー
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTPExceptionのカスタムハンドラー"""
    return {
        "error": True,
        "message": exc.detail,
        "status_code": exc.status_code,
        "timestamp": datetime.now().isoformat()
    }