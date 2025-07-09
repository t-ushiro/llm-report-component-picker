# Report Generator API - Deployment Guide

## 概要
Shadcnコンポーネントを使用したレポートレイアウト生成APIのデプロイガイド

## ローカルテスト

### 1. Dockerビルド
```bash
docker build -t report-generator-api .
```

### 2. ローカル実行
```bash
docker run -p 8000:8000 \
  -e API_KEY_REQUIRED=false \
  -e ALLOWED_S3_BUCKET=kizukai-ds-tmp \
  report-generator-api
```

### 3. 動作確認
```bash
# ヘルスチェック
curl http://localhost:8000/health

# レポート生成
curl -X POST http://localhost:8000/generate-report \
  -H "Content-Type: application/json" \
  -d '{
    "user_request": "月次売上レポートを作成してください",
    "s3_paths": [
      "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json"
    ]
  }'
```

## GitHubへのプッシュ

### 1. 必要なファイル
- `main.py` - FastAPIアプリケーション
- `report_generator_mock.py` - レポート生成ロジック
- `requirements.txt` - Python依存関係
- `Dockerfile` - Dockerイメージ定義
- `apprunner.yaml` - App Runner設定（オプション）
- `.dockerignore` - Docker除外ファイル

### 2. Gitコマンド
```bash
git init
git add main.py report_generator_mock.py requirements.txt Dockerfile apprunner.yaml .dockerignore
git commit -m "Initial commit: Report Generator API for AWS App Runner"
git remote add origin https://github.com/KiZUKAI-Inc/kizukai-llm-report-component-picker.git
git push -u origin main
```

## AWS App Runnerデプロイ

### 前提条件
- AWSアカウント
- ECRリポジトリへのアクセス権限
- IAMロール（S3読み取り権限付き）

### デプロイ手順
1. ECRにDockerイメージをプッシュ
2. App Runnerサービスを作成
3. 環境変数を設定:
   - `API_KEY`: セキュアなAPIキー
   - `ALLOWED_S3_BUCKET`: kizukai-ds-tmp
   - `API_KEY_REQUIRED`: true（本番環境）

## エンドポイント

- `GET /` - ルート情報
- `GET /health` - ヘルスチェック
- `POST /generate-report` - レポート生成（要APIキー）
- `GET /sample-s3-paths` - サンプルS3パス
- `GET /available-components` - 利用可能コンポーネント

## セキュリティ

- APIキー認証（X-API-Keyヘッダー）
- S3パスのホワイトリスト検証
- CORS設定（本番環境では要調整）