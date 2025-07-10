# Report Generator API

Shadcnコンポーネントを使用したレポートレイアウト生成API for AWS App Runner

## 概要
このAPIは、自然言語のリクエストとS3データパスから、適切なShadcnコンポーネントを選択してレポートレイアウトをJSON形式で生成します。

## ファイル構成

- `main.py` - FastAPIアプリケーション
- `report_generator_mock.py` - レポート生成ロジック
- `requirements.txt` - Python依存関係
- `apprunner.yaml` - AWS App Runner設定

## エンドポイント

### POST /generate-report
レポートレイアウトを生成します。

**リクエスト例:**
```json
{
  "user_request": "月次売上レポートを作成してください",
  "s3_paths": [
    "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json",
    "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/category-sales.json"
  ]
}
```

**レスポンス例:**
```json
{
  "status": "success",
  "report": {
    "reportId": "report_1234567890",
    "title": "月次売上レポート",
    "sections": {
      "header": [...],
      "main": [...]
    }
  }
}
```

### その他のエンドポイント
- `GET /health` - ヘルスチェック
- `GET /sample-s3-paths` - サンプルS3パス
- `GET /available-components` - 利用可能コンポーネント一覧

## 利用可能なコンポーネント

### ヘッダーセクション
- **MainHeader** - メインタイトル
- **SubHeader** - サブタイトル

### メインセクション
- **DataTable** - データ一覧表示（S3データ）
- **BarChart** - 棒グラフ（S3データ、xField/yFields指定）
- **Card** - KPI表示（テキストデータ）
- **TextField** - 説明文
- **MarkdownField** - 書式付きテキスト

## データソース

- **S3** - JSON形式のデータファイル（DataTable、BarChart用）
- **TEXT** - 直接指定するテキスト（Card、TextField等）

## 特徴

- データソースをS3とTEXTの2種類に統一してシンプルな実装
- BarChartは最小限の必須Props（xField、yFields）のみ
- 最大10個のメインセクションをサポート
- AWS App Runnerでのデプロイに最適化

## ローカル開発
```bash
# 依存関係のインストール
pip install -r requirements.txt

# サーバー起動
uvicorn main:app --reload
```

## デプロイ
AWS App Runnerでのデプロイをサポートしています。詳細は`README_DEPLOY.md`を参照してください。

## セキュリティ
- APIキー認証（X-API-Keyヘッダー）
- S3パスのホワイトリスト検証
- 環境変数で認証の有効/無効を制御可能