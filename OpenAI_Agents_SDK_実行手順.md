# OpenAI Agents SDK実装 - ローカル実行手順

## 概要
OpenAI Agents SDKを使用したレポート生成機能の実装です。

## 前提条件

### 1. Python環境
- Python 3.9以上が必要（3.13では動作しない場合があります）
- 推奨: Python 3.9

### 2. 必要なパッケージ
```bash
pip install openai==1.35.0
pip install openai-agents==0.1.0
pip install boto3
pip install python-dotenv
```

### 3. 環境変数設定
`.env`ファイルに以下を設定:
```
OPENAI_API_KEY=your-api-key-here
```

### 4. AWS認証情報
`~/.aws/credentials`に以下の形式で設定:
```
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
region = ap-northeast-1
```

## 実装ファイル

### 1. report_generator_agents_sdk_v2.py
- OpenAI Agents SDK実装本体
- 非同期関数ベースの実装
- データクラスを使用した型定義
- 4つのツール関数を提供:
  - `validate_s3_path`: S3パスの検証
  - `read_s3_data`: S3からのデータ読み込み
  - `analyze_json_data`: JSONデータの分析
  - `calculate_kpi`: KPI計算

### 2. test_agents_sdk_local.py
- テストスクリプト
- 3つのテストケースを実行
- 個別ツールのテストも可能

## 実行方法

### 1. 基本実行
```bash
python3.9 test_agents_sdk_local.py
```

### 2. 個別ツールテスト
```bash
python3.9 test_agents_sdk_local.py --tools
```

### 3. 単独実行
```python
import asyncio
from report_generator_agents_sdk_v2 import generate_report

# レポート生成
user_request = "月次売上レポートを作成してください"
s3_paths = ["s3://bucket/data.json"]

result = asyncio.run(generate_report(user_request, s3_paths))
print(result)
```

## 実行結果

成功時の出力例:
```
============================================================
OpenAI Agents SDK テスト開始
============================================================

[1] 環境変数確認
✓ OPENAI_API_KEY: 設定済み (51文字)

[2] エージェント初期化
✓ 関数ベースの実装のため初期化不要

[4] テストケース: 基本的な売上レポート
    リクエスト: 月次売上レポートを作成してください。売上のKPIと日別の推移を見たいです。
    S3パス: ['s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json']
----------------------------------------
✓ レポート生成成功
  → 結果を test_output_agents_sdk_1.json に保存しました
  → ヘッダーセクション: 1個
  → メインセクション: 2個
    - Card: 売上サマリー
    - DataTable: 日別売上データ
```

## 出力ファイル

生成されるファイル:
- `test_output_agents_sdk_1.json`: 基本的な売上レポート
- `test_output_agents_sdk_2.json`: カテゴリ別レポート
- `test_output_agents_sdk_3.json`: 複数データソースレポート
- `agents_sdk_debug.log`: デバッグログ

## デバッグ

### ログレベルの変更
```python
logging.basicConfig(level=logging.DEBUG)  # 詳細ログ
logging.basicConfig(level=logging.INFO)   # 通常ログ
```

### 一般的なエラーと対処法

1. **ModuleNotFoundError: No module named 'agents'**
   - 原因: openai-agents パッケージが未インストール
   - 対処: `pip install openai-agents==0.1.0`

2. **Python version mismatch**
   - 原因: Python 3.13などで実行している
   - 対処: Python 3.9を使用

3. **S3アクセスエラー**
   - 原因: AWS認証情報が未設定
   - 対処: `~/.aws/credentials`を確認

## 注意事項

1. OpenAI Agents SDKは最新のフレームワークのため、APIが変更される可能性があります
2. エージェントは複数のツールを自動的に組み合わせて実行します
3. レポート生成には数秒〜数十秒かかる場合があります

## 参考リンク

- [OpenAI Agents SDK Documentation](https://github.com/openai/agents)
- [OpenAI API Documentation](https://platform.openai.com/docs)