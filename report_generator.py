"""
レポート生成AIエージェント - OpenAI Agents SDK実装サンプル
"""

from openai import OpenAI
from openai.types.beta import Assistant
import json
import boto3
from datetime import datetime
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
import logging

# ロギング設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# .envファイルから環境変数を読み込む
load_dotenv()

class ReportGeneratorAgent:
    def __init__(self, api_key: str = None):
        logger.info("ReportGeneratorAgent初期化開始")
        # APIキーが指定されていない場合はSecrets Managerから取得
        if not api_key:
            logger.debug("APIキーが未指定のため、取得処理を開始")
            api_key = self._get_openai_api_key()
        self.client = OpenAI(api_key=api_key)
        self.s3_client = boto3.client('s3')
        logger.info("ReportGeneratorAgent初期化完了")
    
    def _get_openai_api_key(self) -> str:
        """AWS Secrets ManagerからOpenAI APIキーを取得"""
        # 環境変数から直接取得する場合
        if os.getenv("OPENAI_API_KEY"):
            logger.debug("環境変数からAPIキーを取得")
            return os.getenv("OPENAI_API_KEY")
        
        # Secrets Managerから取得
        secret_name = "kizukai-openai-api-key"
        region_name = "ap-northeast-1"
        
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
        
        try:
            logger.debug(f"Secrets Managerから {secret_name} を取得中...")
            get_secret_value_response = client.get_secret_value(
                SecretId=secret_name
            )
            secret = json.loads(get_secret_value_response['SecretString'])
            logger.info("Secrets ManagerからAPIキー取得成功")
            return secret.get('api_key', '')
        except Exception as e:
            logger.error(f"Secrets Manager取得エラー: {e}")
            raise
        
    def create_agent(self):
        """レポート生成エージェントを作成"""
        logger.info("エージェント作成開始")
        with open('report_generator_prompt.md', 'r', encoding='utf-8') as f:
            system_prompt = f.read()
        logger.debug(f"プロンプト読み込み完了: {len(system_prompt)}文字")
            
        # エージェントの作成（Assistants API v2）
        agent = self.client.beta.assistants.create(
            model="gpt-4o-mini",
            name="Report Generator",
            description="Generates report layouts using Shadcn components",
            instructions=system_prompt,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "read_s3_data",
                        "description": "S3からCSV/JSONデータを読み込む",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "s3_path": {"type": "string", "description": "S3ファイルパス"},
                                "file_type": {"type": "string", "enum": ["json", "csv"], "description": "ファイルタイプ"},
                                "preview_rows": {"type": "integer", "description": "プレビュー行数（オプション）"}
                            },
                            "required": ["s3_path"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "analyze_data",
                        "description": "データの統計情報を分析",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "data": {"type": "array", "description": "分析対象データ"},
                                "analysis_type": {"type": "string", "enum": ["summary", "aggregation"], "description": "分析タイプ"},
                                "group_by": {"type": "string", "description": "グループ化キー（aggregation時）"}
                            },
                            "required": ["data", "analysis_type"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "generate_kpi",
                        "description": "KPIを計算して生成",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "data": {"type": "array", "description": "元データ"},
                                "kpi_type": {"type": "string", "enum": ["total", "average", "max", "min"], "description": "KPIタイプ"},
                                "field": {"type": "string", "description": "計算対象フィールド"}
                            },
                            "required": ["data", "kpi_type", "field"]
                        }
                    }
                },
                {
                    "type": "function", 
                    "function": {
                        "name": "validate_s3_path",
                        "description": "S3パスの存在確認とデータ形式の検証",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "s3_path": {"type": "string", "description": "検証するS3パス"}
                            },
                            "required": ["s3_path"]
                        }
                    }
                }
            ]
        )
        logger.info(f"エージェント作成完了: ID={agent.id}")
        return agent
    
    def read_s3_data(self, s3_path: str, file_type: str = "json", preview_rows: int = None) -> Dict[str, Any]:
        """S3からデータを読み込む"""
        logger.debug(f"S3データ読み込み開始: {s3_path} (type={file_type})")
        try:
            bucket, key = s3_path.replace("s3://", "").split("/", 1)
            logger.debug(f"Bucket: {bucket}, Key: {key}")
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            
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
    
    def analyze_data(self, data: List[Dict], analysis_type: str = "summary", 
                    group_by: str = None) -> Dict[str, Any]:
        """データを分析する"""
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
    
    def generate_kpi(self, data: List[Dict], kpi_type: str, field: str) -> Dict[str, Any]:
        """KPIを生成する"""
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
    
    def validate_s3_path(self, s3_path: str) -> Dict[str, Any]:
        """S3パスの存在確認"""
        try:
            bucket, key = s3_path.replace("s3://", "").split("/", 1)
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return {"exists": True, "path": s3_path}
        except:
            return {"exists": False, "path": s3_path}
    
    def generate_report(self, user_request: str, s3_paths: List[str]) -> Dict[str, Any]:
        """レポートレイアウトを生成"""
        logger.info(f"レポート生成開始: request='{user_request[:50]}...', paths={len(s3_paths)}件")
        assistant = self.create_agent()
        
        # スレッドの作成
        thread = self.client.beta.threads.create()
        logger.debug(f"スレッド作成完了: ID={thread.id}")
        
        # メッセージの追加
        message_content = f"""
ユーザーリクエスト: {user_request}

利用可能なS3データ:
{json.dumps(s3_paths, ensure_ascii=False, indent=2)}

上記の情報を基に、レポートレイアウトのJSONを生成してください。
"""
        
        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message_content
        )
        
        # アシスタントの実行
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id
        )
        logger.info(f"Run開始: ID={run.id}")
        
        # 実行完了を待機
        while run.status not in ["completed", "failed"]:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            logger.debug(f"Runステータス: {run.status}")
            
            # ツール呼び出しの処理
            if run.status == "requires_action":
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                logger.info(f"ツール呼び出し: {len(tool_calls)}件")
                tool_outputs = []
                
                for tool_call in tool_calls:
                    logger.debug(f"ツール実行: {tool_call.function.name}")
                    args = json.loads(tool_call.function.arguments)
                    logger.debug(f"引数: {args}")
                    
                    if tool_call.function.name == "read_s3_data":
                        result = self.read_s3_data(**args)
                    elif tool_call.function.name == "analyze_data":
                        result = self.analyze_data(**args)
                    elif tool_call.function.name == "generate_kpi":
                        result = self.generate_kpi(**args)
                    elif tool_call.function.name == "validate_s3_path":
                        result = self.validate_s3_path(**args)
                    else:
                        result = {"status": "error", "message": f"Unknown function: {tool_call.function.name}"}
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(result)
                    })
                
                # ツール出力を送信
                logger.debug(f"ツール出力送信: {len(tool_outputs)}件")
                self.client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )
        
        # 結果を取得
        logger.info(f"Run完了: ステータス={run.status}")
        messages = self.client.beta.threads.messages.list(thread_id=thread.id)
        logger.debug(f"メッセージ数: {len(messages.data)}件")
        
        # 最新のアシスタントメッセージからJSONを抽出
        for message in messages.data:
            if message.role == "assistant":
                content = message.content[0].text.value
                # JSON部分を抽出
                try:
                    import re
                    json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(1))
                        logger.info("レポートJSON抽出成功 (コードブロック)")
                        return result
                    else:
                        # JSON全体がコードブロックでない場合
                        result = json.loads(content)
                        logger.info("レポートJSON抽出成功 (直接)")
                        return result
                except Exception as e:
                    logger.error(f"JSONパースエラー: {str(e)}")
                    return {"error": "Failed to parse JSON", "content": content}
        
        logger.error("エージェントからのレスポンスがありません")
        return {"error": "No response from agent"}


# 使用例
if __name__ == "__main__":
    # 初期化（APIキーは自動的にSecrets Managerから取得される）
    agent = ReportGeneratorAgent()
    
    # サンプルリクエスト
    user_request = "月次売上レポートを作成してください。日別の売上推移と製品カテゴリ別の売上を見たいです。"
    
    # 実際のS3パス
    s3_paths = [
        "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/daily-sales.json",
        "s3://kizukai-ds-tmp/ai_report_json_mock/input_data/category-sales.json"
    ]
    
    # レポート生成
    result = agent.generate_report(user_request, s3_paths)
    
    # 結果を保存
    with open('generated_report.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("レポートが生成されました: generated_report.json")