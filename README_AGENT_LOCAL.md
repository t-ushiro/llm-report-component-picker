# OpenAI Agents SDK ローカル実行ガイド

## 概要
このドキュメントでは、OpenAI Agents SDKを使用したレポート生成エージェントをローカル環境で実行する方法を説明します。

## 前提条件

1. **Python 3.9以上**がインストールされていること
2. **AWS認証情報**が設定されていること（S3アクセス用）
3. **OpenAI APIキー**を持っていること

## セットアップ手順

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env`ファイルを作成し、以下の内容を設定します：

```bash
# .envファイルを作成
cp .env.example .env

# .envファイルを編集
# 以下の値を設定してください：
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx  # あなたのOpenAI APIキー
AWS_REGION=ap-northeast-1
DISABLE_API_KEY_AUTH=true  # ローカルテスト用
```

### 3. AWS認証設定

AWS CLIが設定されていることを確認：

```bash
aws configure list
```

設定されていない場合：

```bash
aws configure
# AWS Access Key ID: [あなたのアクセスキー]
# AWS Secret Access Key: [あなたのシークレットキー]
# Default region name: ap-northeast-1
# Default output format: json
```

## 実行方法

### 方法1: テストスクリプトを使用（推奨）

```bash
# 基本的なエージェントテスト
python test_agent_local.py

# 個別ツールのテスト
python test_agent_local.py --tools
```

### 方法2: 直接実行

```bash
python report_generator.py
```

### 方法3: FastAPI経由でテスト

```bash
# APIサーバー起動
DISABLE_API_KEY_AUTH=true uvicorn main:app --reload

# 別ターミナルでテスト
curl -X POST http://localhost:8000/generate-report \
  -H "Content-Type: application/json" \
  -d '{
    "user_request": "月次売上レポートを作成してください",
    "s3_paths": [
      "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json"
    ]
  }'
```

## デバッグ情報

### ログファイル

実行時に以下のログファイルが生成されます：

- `agent_debug.log` - 詳細なデバッグログ
- `test_output_*.json` - テスト結果のJSON

### ログレベルの調整

`test_agent_local.py`の以下の部分を編集してログレベルを変更できます：

```python
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG, INFO, WARNING, ERROR から選択
    ...
)
```

## トラブルシューティング

### よくあるエラーと対処法

1. **OpenAI APIキーエラー**
   ```
   Error: Invalid API key
   ```
   → `.env`ファイルのOPENAI_API_KEYを確認

2. **S3アクセスエラー**
   ```
   Error: Access Denied
   ```
   → AWS認証情報を確認、S3バケットへのアクセス権限を確認

3. **モジュールインポートエラー**
   ```
   ModuleNotFoundError: No module named 'openai'
   ```
   → `pip install -r requirements.txt`を再実行

4. **Assistants APIのレート制限**
   ```
   Error: Rate limit exceeded
   ```
   → 少し時間を置いてから再実行

## エージェントの構成

### 利用可能なツール

1. **read_s3_data** - S3からJSON/CSVデータを読み込み
2. **analyze_data** - データの統計情報を分析
3. **generate_kpi** - KPIを計算（合計、平均、最大値、最小値）
4. **validate_s3_path** - S3パスの存在確認

### 処理フロー

1. ユーザーリクエストを受け取る
2. S3パスを検証（validate_s3_path）
3. データを読み込み（read_s3_data）
4. データを分析（analyze_data）
5. 必要に応じてKPIを計算（generate_kpi）
6. レポートレイアウトJSONを生成

## 開発のヒント

- デバッグログを活用してエージェントの動作を詳細に確認
- `--tools`オプションで個別ツールの動作を検証
- `agent_debug.log`でツール呼び出しの詳細を確認
- テスト結果のJSONファイルでレポート構造を確認

## 次のステップ

1. 新しいツールの追加（`report_generator.py`に実装）
2. プロンプトの調整（`report_generator_prompt.md`を編集）
3. 新しいコンポーネントタイプの追加
4. AWS App Runnerへのデプロイ（`AWS_AppRunner_デプロイ手順書.md`参照）