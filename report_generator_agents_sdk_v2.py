"""
レポート生成 - OpenAI Agents SDK実装 (v3)
"""

from agents import Agent, Runner, function_tool
import json
import boto3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass
import re
import asyncio

# ロギング設定 - 必要最低限のログのみ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

# S3クライアントをグローバルで初期化
s3_client = boto3.client('s3')

# データクラスで型を定義
@dataclass
class S3ReadResult:
    status: str
    data: Optional[List[dict]] = None
    type: Optional[str] = None
    message: Optional[str] = None

@dataclass
class AnalysisResult:
    status: str
    summary: Optional[dict] = None
    aggregation: Optional[dict] = None
    message: Optional[str] = None

@dataclass
class KPIResult:
    status: str
    kpi: Optional[dict] = None
    message: Optional[str] = None

@dataclass
class S3PathValidation:
    exists: bool
    path: str

@dataclass
class ReportLayout:
    reportId: str
    title: str
    createdAt: str
    createdBy: str
    sections: dict

@function_tool
def read_s3_data(s3_path: str, file_type: str = "json", preview_rows: Optional[int] = None) -> dict:
    """S3からCSV/JSONデータを読み込む"""
    try:
        bucket, key = s3_path.replace("s3://", "").split("/", 1)
        response = s3_client.get_object(Bucket=bucket, Key=key)
        
        if file_type == "json":
            data = json.loads(response['Body'].read())
            if preview_rows and isinstance(data, list):
                data = data[:preview_rows]
            return {"status": "success", "data": data, "type": "json"}
        
        elif file_type == "csv":
            import csv
            import io
            csv_content = response['Body'].read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(csv_content))
            data = list(reader)
            logger.info(f"CSVデータ読み込み成功: {len(data)}行")
            logger.info(f"CSVデータ: {data}")
            if preview_rows:
                data = data[:preview_rows]
            return {"status": "success", "data": data, "type": "csv"}
        
        else:
            return {"status": "error", "message": f"Unsupported file type: {file_type}"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

@function_tool
def validate_s3_path(s3_path: str) -> dict:
    """S3パスの存在確認"""
    try:
        bucket, key = s3_path.replace("s3://", "").split("/", 1)
        s3_client.head_object(Bucket=bucket, Key=key)
        return {"exists": True, "path": s3_path}
    except:
        return {"exists": False, "path": s3_path}

@function_tool
def analyze_json_data(json_data: str) -> dict:
    """JSONデータの統計情報を分析（JSON文字列を受け取る）"""
    try:
        # JSON文字列をパース
        data = json.loads(json_data)
        
        if not data or not isinstance(data, list):
            return {"status": "error", "message": "No data to analyze or data is not a list"}
        
        # データのサマリー情報を生成
        keys = list(data[0].keys()) if data else []
        row_count = len(data)
        
        numeric_fields = []
        for key in keys:
            if all(isinstance(row.get(key), (int, float)) for row in data[:10]):
                numeric_fields.append(key)
        
        return {
            "status": "success",
            "summary": {
                "row_count": row_count,
                "columns": keys,
                "numeric_fields": numeric_fields
            }
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@function_tool
def calculate_kpi(json_data: str, kpi_type: str, field: str) -> dict:
    """JSONデータからKPIを計算（JSON文字列を受け取る）"""
    try:
        # JSON文字列をパース
        data = json.loads(json_data)
        
        if not isinstance(data, list):
            return {"status": "error", "message": "Data must be a list"}
        
        values = [float(item.get(field, 0)) for item in data if item.get(field)]
        
        if kpi_type == "total":
            return {"status": "success", "kpi": {"type": "total", "value": sum(values)}}
        elif kpi_type == "average":
            return {"status": "success", "kpi": {"type": "average", "value": sum(values) / len(values) if values else 0}}
        elif kpi_type == "max":
            return {"status": "success", "kpi": {"type": "max", "value": max(values) if values else 0}}
        elif kpi_type == "min":
            return {"status": "success", "kpi": {"type": "min", "value": min(values) if values else 0}}
        else:
            return {"status": "error", "message": f"Unknown KPI type: {kpi_type}"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

# プロンプトを読み込み
with open('report_generator_prompt.md', 'r', encoding='utf-8') as f:
    system_prompt = f.read()

# 追加の指示
system_prompt += """

## 重要な注意事項
- analyze_json_dataとcalculate_kpiには、JSON文字列として渡してください
- 例: analyze_json_data(json_data='[{"sales": 100}, {"sales": 200}]')
- 最終的な出力は、JSON形式のレポートレイアウトのみにしてください
"""

# Report Generator Agent
report_generator_agent = Agent(
    name="Report Generator",
    instructions=system_prompt,
    tools=[
        read_s3_data,
        validate_s3_path,
        analyze_json_data,
        calculate_kpi
    ],
    model="gpt-4o-mini"
)
    
async def generate_report(user_request: str, s3_paths: List[str]) -> Dict[str, Any]:
    """レポートレイアウトを生成"""
    timestamp = int(datetime.now().timestamp() * 1000)
    logger.info(f"レポート生成開始: paths={len(s3_paths)}件")
    
    # メッセージを構築
    message = f"""
ユーザーリクエスト: {user_request}

利用可能なS3データ:
{json.dumps(s3_paths, ensure_ascii=False, indent=2)}

上記の情報を基に、以下の手順でレポートレイアウトのJSONを生成してください：
1. S3パスを検証（validate_s3_path）
2. データを読み込み（read_s3_data）
3. データを分析（analyze_json_data）- データはJSON文字列として渡す
4. 必要に応じてKPIを計算（calculate_kpi）- データはJSON文字列として渡す
5. レポートレイアウトJSONを生成

レポートIDは report_{timestamp} を使用してください。
"""
    
    try:
        # エージェント実行
        result = await Runner.run(
            report_generator_agent,
            message
        )
        
        # 最終出力を処理
        final_output = result.final_output
        
        # 文字列の場合はJSONを抽出
        if isinstance(final_output, str):
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', final_output, re.DOTALL)
            if json_match:
                report_json = json.loads(json_match.group(1))
            else:
                try:
                    report_json = json.loads(final_output)
                except:
                    raise ValueError("Invalid JSON output")
        else:
            # 辞書の場合
            report_json = final_output
        
        # 基本的な検証
        if "reportId" not in report_json:
            report_json["reportId"] = f"report_{timestamp}"
        if "createdAt" not in report_json:
            report_json["createdAt"] = datetime.now().isoformat() + "Z"
        if "createdBy" not in report_json:
            report_json["createdBy"] = "agent_generated"
        
        logger.info("レポート生成成功")
        return report_json
        
    except Exception as e:
        logger.error(f"レポート生成エラー: {str(e)}")
        return _generate_fallback_report(user_request, s3_paths, timestamp)

def _generate_fallback_report(user_request: str, s3_paths: List[str], timestamp: int) -> Dict[str, Any]:
    """エラー時のフォールバックレポート"""
    return {
        "reportId": f"report_{timestamp}",
        "title": "レポート",
        "createdAt": datetime.now().isoformat() + "Z",
        "createdBy": "agent_generated",
        "sections": {
            "header": [
                {
                    "id": "section_header_1",
                    "type": "Default",
                    "component": "MainHeader",
                    "contents": [
                        {
                            "source": "TEXT",
                            "component": "MainHeader",
                            "value": "レポート",
                            "props": {}
                        }
                    ]
                }
            ],
            "main": [
                {
                    "id": "section_main_1",
                    "type": "Default",
                    "component": "TextField",
                    "title": "エラー",
                    "description": "",
                    "contents": [
                        {
                            "source": "TEXT",
                            "component": "TextField",
                            "value": "レポート生成中にエラーが発生しました。",
                            "props": {}
                        }
                    ]
                }
            ]
        }
    }


# 使用例
if __name__ == "__main__":
    # 環境変数からAPIキーを設定
    from dotenv import load_dotenv
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY環境変数が設定されていません")
        exit(1)
    
    # サンプルリクエスト
    user_request = "月次売上レポートを作成してください。日別の売上推移と製品カテゴリ別の売上を見たいです。"
    
    # 実際のS3パス
    s3_paths = [
        "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json",
        "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/category-sales.json"
    ]
    
    # レポート生成
    result = asyncio.run(generate_report(user_request, s3_paths))
    
    # 結果を保存
    with open('generated_report_agents_sdk.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("レポートが生成されました: generated_report_agents_sdk.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))