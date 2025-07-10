# AWS App Runner デプロイ手順書

## 概要
`report_generator_mock.py`をAWS App RunnerでAPI化するための実装・デプロイ手順書です。

## 前提条件
- AWSアカウントの準備
- AWS CLIのインストールと設定
- Docker Desktopのインストール
- Python 3.9以上

## 実装手順

### 1. FastAPIアプリケーションの作成

#### 1.1 新規ファイル `main.py` を作成
```python
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
```

### 2. 依存関係の定義

#### 2.1 `requirements.txt` を作成
```
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.4.2
python-multipart==0.0.6
```

### 3. Dockerfileの作成

#### 3.1 `Dockerfile` を作成
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードのコピー
COPY report_generator_mock.py .
COPY main.py .

# 非rootユーザーで実行
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# ポート8000で起動
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4. App Runner設定ファイルの作成

#### 4.1 `apprunner.yaml` を作成（オプション）
```yaml
version: 1.0
runtime: docker
build:
  commands:
    build:
      - echo "No build commands"
run:
  runtime-version: latest
  command: uvicorn main:app --host 0.0.0.0 --port 8000
  network:
    port: 8000
    env: PORT
  env:
    - name: API_KEY
      value: "your-secure-api-key"
    - name: ALLOWED_S3_BUCKET
      value: "kizukai-ds-tmp"
```

## デプロイ手順

### 1. ECRリポジトリの作成
```bash
# リポジトリ作成
aws ecr create-repository --repository-name report-generator-api --region ap-northeast-1

# ログイン
aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin [ACCOUNT_ID].dkr.ecr.ap-northeast-1.amazonaws.com
```

### 2. Dockerイメージのビルドとプッシュ
```bash
# ビルド
docker build -t report-generator-api .

# タグ付け
docker tag report-generator-api:latest [ACCOUNT_ID].dkr.ecr.ap-northeast-1.amazonaws.com/report-generator-api:latest

# プッシュ
docker push [ACCOUNT_ID].dkr.ecr.ap-northeast-1.amazonaws.com/report-generator-api:latest
```

### 3. IAMロールの作成

#### 3.1 信頼ポリシー (`trust-policy.json`)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "tasks.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

#### 3.2 S3アクセスポリシー (`s3-policy.json`)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::kizukai-ds-tmp/ai_report_json_mock/*",
        "arn:aws:s3:::kizukai-ds-tmp"
      ]
    }
  ]
}
```

#### 3.3 ロール作成コマンド
```bash
# ロール作成
aws iam create-role --role-name AppRunnerS3AccessRole --assume-role-policy-document file://trust-policy.json

# ポリシー作成
aws iam create-policy --policy-name AppRunnerS3ReadPolicy --policy-document file://s3-policy.json

# ポリシーのアタッチ
aws iam attach-role-policy --role-name AppRunnerS3AccessRole --policy-arn arn:aws:iam::[ACCOUNT_ID]:policy/AppRunnerS3ReadPolicy
```

### 4. App Runnerサービスの作成

#### 4.1 AWS コンソールでの作成
1. AWS App Runnerコンソールを開く
2. 「サービスの作成」をクリック
3. ソース: 「Container registry」→「Amazon ECR」を選択
4. イメージURIを入力
5. デプロイ設定:
   - 手動デプロイまたは自動デプロイを選択
6. サービス設定:
   - サービス名: `report-generator-api`
   - CPU: 0.25 vCPU
   - メモリ: 0.5 GB
   - 環境変数:
     - `API_KEY`: セキュアなAPIキー
     - `ALLOWED_S3_BUCKET`: `kizukai-ds-tmp`
7. セキュリティ:
   - インスタンスロール: 作成した`AppRunnerS3AccessRole`を選択
8. 「作成」をクリック

#### 4.2 AWS CLIでの作成
```bash
aws apprunner create-service \
  --service-name "report-generator-api" \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "[ACCOUNT_ID].dkr.ecr.ap-northeast-1.amazonaws.com/report-generator-api:latest",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "API_KEY": "your-secure-api-key",
          "ALLOWED_S3_BUCKET": "kizukai-ds-tmp"
        }
      },
      "ImageRepositoryType": "ECR"
    },
    "AutoDeploymentsEnabled": false
  }' \
  --instance-configuration '{
    "Cpu": "0.25 vCPU",
    "Memory": "0.5 GB",
    "InstanceRoleArn": "arn:aws:iam::[ACCOUNT_ID]:role/AppRunnerS3AccessRole"
  }'
```

## セキュリティ設定

### 1. APIキー管理
- AWS Systems Manager Parameter Storeを使用
- 環境変数として注入

### 2. ネットワーク制限（オプション）
- AWS WAFでIP制限を設定
- レート制限の実装

### 3. CORS設定（必要に応じて）
main.pyに以下を追加:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],
    allow_methods=["POST"],
    allow_headers=["*"],
)
```

## 動作確認

### 1. ヘルスチェック
```bash
curl https://[YOUR-APP-RUNNER-URL]/health
```

### 2. API呼び出しテスト
```bash
curl -X POST https://[YOUR-APP-RUNNER-URL]/generate-report \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-api-key" \
  -d '{
    "user_request": "月次売上レポートを作成してください",
    "s3_paths": [
      "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json",
      "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/category-sales.json"
    ]
  }'
```

## トラブルシューティング

### 1. S3アクセスエラー
- IAMロールの権限を確認
- S3バケットポリシーを確認

### 2. APIキーエラー
- 環境変数が正しく設定されているか確認
- ヘッダー名が`X-API-Key`になっているか確認

### 3. デプロイエラー
- ECRイメージが正しくプッシュされているか確認
- App Runnerのサービスロールを確認

## 注意事項
- APIキーは定期的に更新
- S3バケットへのアクセスは最小権限の原則に従う
- 本番環境では監視・アラートを設定
- コスト管理のため、自動スケーリング設定を適切に調整