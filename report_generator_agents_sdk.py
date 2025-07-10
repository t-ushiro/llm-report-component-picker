"""
レポート生成 - OpenAI Agents SDK実装
"""

from agents import Agent, Runner, function_tool
import json
import boto3
import os
from datetime import datetime
from typing import List, Dict, Any
import logging

# ロギング設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# S3クライアントをグローバルで初期化
s3_client = boto3.client('s3')

@function_tool
def read_s3_data(s3_path: str, file_type: str = "json", preview_rows: int = None) -> Dict[str, Any]:
    """S3からCSV/JSONデータを読み込む"""
    logger.debug(f"S3データ読み込み開始: {s3_path} (type={file_type})")
    try:
        bucket, key = s3_path.replace("s3://", "").split("/", 1)
        logger.debug(f"Bucket: {bucket}, Key: {key}")
        response = s3_client.get_object(Bucket=bucket, Key=key)
        
        if file_type == "json":
            data = json.loads(response['Body'].read())
            if preview_rows and isinstance(data, list):
                data = data[:preview_rows]
            logger.info(f"JSONデータ読み込み成功: {len(data) if isinstance(data, list) else 1}件")
            return {"status": "success", "data": data, "type": "json"}
        
        elif file_type == "csv":
            import csv
            import io
            csv_content = response['Body'].read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(csv_content))
            data = list(reader)
            if preview_rows:
                data = data[:preview_rows]
            logger.info(f"CSVデータ読み込み成功: {len(data)}行")
            return {"status": "success", "data": data, "type": "csv"}
        
        else:
            return {"status": "error", "message": f"Unsupported file type: {file_type}"}
            
    except Exception as e:
        logger.error(f"S3データ読み込みエラー: {str(e)}")
        return {"status": "error", "message": str(e)}

@function_tool
def analyze_data(data: List[Dict[str, Any]], analysis_type: str = "summary", group_by: str = None) -> Dict[str, Any]:
    """データの統計情報を分析"""
    logger.debug(f"データ分析開始: type={analysis_type}, group_by={group_by}")
    if not data:
        logger.warning("分析対象データが空")
        return {"status": "error", "message": "No data to analyze"}
    
    if analysis_type == "summary":
        # データのサマリー情報を生成
        keys = list(data[0].keys()) if data else []
        row_count = len(data)
        
        numeric_fields = []
        for key in keys:
            if all(isinstance(row.get(key), (int, float)) for row in data[:10]):
                numeric_fields.append(key)
        
        logger.info(f"データサマリー: {row_count}行, {len(keys)}列, 数値列={numeric_fields}")
        return {
            "status": "success",
            "summary": {
                "row_count": row_count,
                "columns": keys,
                "numeric_fields": numeric_fields
            }
        }
    
    elif analysis_type == "aggregation" and group_by:
        # グループ別集計
        result = {}
        for item in data:
            group = item.get(group_by)
            if group not in result:
                result[group] = {"count": 0, "items": []}
            result[group]["count"] += 1
            result[group]["items"].append(item)
        
        return {"status": "success", "aggregation": result}
    
    return {"status": "error", "message": "Invalid analysis type"}

@function_tool
def generate_kpi(data: List[Dict[str, Any]], kpi_type: str, field: str) -> Dict[str, Any]:
    """KPIを計算して生成"""
    logger.debug(f"KPI生成開始: type={kpi_type}, field={field}")
    try:
        values = [float(item.get(field, 0)) for item in data if item.get(field)]
        logger.debug(f"対象値: {len(values)}件")
        
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
        logger.error(f"KPI生成エラー: {str(e)}")
        return {"status": "error", "message": str(e)}

@function_tool
def validate_s3_path(s3_path: str) -> Dict[str, Any]:
    """S3パスの存在確認"""
    try:
        bucket, key = s3_path.replace("s3://", "").split("/", 1)
        s3_client.head_object(Bucket=bucket, Key=key)
        logger.info(f"S3パス検証成功: {s3_path}")
        return {"exists": True, "path": s3_path}
    except:
        logger.warning(f"S3パス検証失敗: {s3_path}")
        return {"exists": False, "path": s3_path}

class ReportGeneratorAgentSDK:
    def __init__(self):
        self.timestamp = int(datetime.now().timestamp() * 1000)
        logger.info("ReportGeneratorAgentSDK初期化")
        
        # プロンプトを読み込み
        with open('report_generator_prompt.md', 'r', encoding='utf-8') as f:
            self.system_prompt = f.read()
        
        # エージェントを作成
        self.agent = Agent(
            name="Report Generator",
            instructions=self.system_prompt,
            tools=[
                read_s3_data,
                analyze_data,
                generate_kpi,
                validate_s3_path
            ],
            model="gpt-4o-mini"
        )
        logger.info("エージェント作成完了")
    
    def generate_report(self, user_request: str, s3_paths: List[str]) -> Dict[str, Any]:
        """レポートレイアウトを生成"""
        logger.info(f"レポート生成開始: request='{user_request[:50]}...', paths={len(s3_paths)}件")
        
        # メッセージを構築
        message = f"""
ユーザーリクエスト: {user_request}

利用可能なS3データ:
{json.dumps(s3_paths, ensure_ascii=False, indent=2)}

上記の情報を基に、以下の手順でレポートレイアウトのJSONを生成してください：
1. S3パスを検証（validate_s3_path）
2. データを読み込み（read_s3_data）
3. データを分析（analyze_data）
4. 必要に応じてKPIを計算（generate_kpi）
5. レポートレイアウトJSONを生成

レポートIDは report_{self.timestamp} を使用してください。
最終的な出力は、JSON形式のレポートレイアウトのみにしてください。
"""
        
        try:
            # エージェントを実行
            logger.debug("エージェント実行開始")
            result = Runner.run_sync(
                self.agent,
                message,
                temperature=0.7
            )
            
            logger.debug(f"エージェント実行完了: {len(result.messages)}メッセージ")
            
            # 最終出力からJSONを抽出
            final_output = result.final_output
            logger.debug(f"最終出力タイプ: {type(final_output)}")
            
            # JSONを抽出して返す
            try:
                # 文字列からJSONを抽出
                import re
                json_match = re.search(r'```json\n(.*?)\n```', final_output, re.DOTALL)
                if json_match:
                    report_json = json.loads(json_match.group(1))
                    logger.info("レポートJSON抽出成功 (コードブロック)")
                else:
                    # JSON全体がコードブロックでない場合
                    report_json = json.loads(final_output)
                    logger.info("レポートJSON抽出成功 (直接)")
                
                # 基本的な検証
                if "reportId" not in report_json:
                    report_json["reportId"] = f"report_{self.timestamp}"
                if "createdAt" not in report_json:
                    report_json["createdAt"] = datetime.now().isoformat() + "Z"
                if "createdBy" not in report_json:
                    report_json["createdBy"] = "agent_generated"
                
                return report_json
                
            except Exception as e:
                logger.error(f"JSONパースエラー: {str(e)}")
                return {
                    "error": "Failed to parse JSON",
                    "content": final_output,
                    "messages": [msg.content for msg in result.messages]
                }
                
        except Exception as e:
            logger.error(f"エージェント実行エラー: {str(e)}")
            return self._generate_fallback_report(user_request, s3_paths)
    
    def _generate_fallback_report(self, user_request: str, s3_paths: List[str]) -> Dict[str, Any]:
        """エラー時のフォールバックレポート"""
        return {
            "reportId": f"report_{self.timestamp}",
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
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY環境変数が設定されていません")
        exit(1)
    
    # ジェネレーターの初期化
    generator = ReportGeneratorAgentSDK()
    
    # サンプルリクエスト
    user_request = "月次売上レポートを作成してください。日別の売上推移と製品カテゴリ別の売上を見たいです。"
    
    # 実際のS3パス
    s3_paths = [
        "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json",
        "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/category-sales.json"
    ]
    
    # レポート生成
    result = generator.generate_report(user_request, s3_paths)
    
    # 結果を保存
    with open('generated_report_agents_sdk.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("レポートが生成されました: generated_report_agents_sdk.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))