from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
import os
from report_generator_mock import ReportGenerator

app = FastAPI()

# リクエストモデル
class ReportRequest(BaseModel):
    user_request: str
    s3_paths: List[str]

# APIキー認証
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    # 環境変数でAPIキー認証を無効化できる
    if os.getenv("DISABLE_API_KEY_AUTH", "false").lower() == "true":
        return "disabled"
    
    if not x_api_key:
        raise HTTPException(status_code=403, detail="API Key required")
    
    if x_api_key != os.getenv("API_KEY", "your-secure-api-key"):
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return x_api_key

# エンドポイント
@app.post("/generate-report", dependencies=[Depends(verify_api_key)])
async def generate_report(request: ReportRequest):
    # S3パスの検証（ホワイトリスト）
    allowed_bucket = os.getenv("ALLOWED_S3_BUCKET", "kizukai-ds-tmp")
    for path in request.s3_paths:
        if not path.startswith(f"s3://{allowed_bucket}/"):
            raise HTTPException(status_code=400, detail="Invalid S3 path")
    
    generator = ReportGenerator()
    report = generator.generate_report(request.user_request, request.s3_paths)
    return {"status": "success", "report": report}

# ヘルスチェック
@app.get("/health")
async def health():
    return {"status": "healthy"}

# サンプルS3パス
@app.get("/sample-s3-paths")
async def sample_s3_paths():
    return {
        "paths": [
            "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json",
            "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/category-sales.json",
            "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/product-inventory.json"
        ]
    }

# 利用可能コンポーネント一覧
@app.get("/available-components")
async def available_components():
    return {
        "header": ["MainHeader", "SubHeader"],
        "main": {
            "DataTable": {
                "source": "S3",
                "description": "データ一覧表示",
                "props": {}
            },
            "BarChart": {
                "source": "S3",
                "description": "カテゴリ別比較",
                "props": {
                    "xField": "必須",
                    "yFields": "必須（配列）"
                }
            },
            "Card": {
                "source": "TEXT",
                "description": "KPI・重要指標",
                "props": {
                    "title": "必須",
                    "description": "オプション",
                    "content": "オプション",
                    "footer": "オプション"
                }
            },
            "TextField": {
                "source": "TEXT",
                "description": "説明文",
                "props": {}
            },
            "MarkdownField": {
                "source": "TEXT",
                "description": "書式付きテキスト",
                "props": {}
            }
        }
    }