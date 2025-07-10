from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
import os
from report_generator_mock import MockReportGenerator

app = FastAPI()

# リクエストモデル
class ReportRequest(BaseModel):
    user_request: str
    s3_paths: List[str]

# APIキー認証
async def verify_api_key(x_api_key: str = Header(...)):
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
    
    generator = MockReportGenerator()
    report = generator.generate_report(request.user_request, request.s3_paths)
    return report

# ヘルスチェック
@app.get("/health")
async def health():
    return {"status": "healthy"}