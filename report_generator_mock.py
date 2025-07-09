"""
レポート生成のモック実装（OpenAI APIを使用しない）
"""

import json
from datetime import datetime
from typing import List, Dict, Any
import re

class MockReportGenerator:
    def __init__(self):
        self.timestamp = int(datetime.now().timestamp() * 1000)
    
    def analyze_request(self, user_request: str) -> Dict[str, Any]:
        """ユーザーリクエストを分析してコンポーネントを決定"""
        components = []
        
        # キーワードに基づいてコンポーネントを決定
        if "売上" in user_request or "推移" in user_request:
            components.append("DataTable")
        if "カテゴリ" in user_request or "比較" in user_request or "別" in user_request:
            components.append("BarChart")
        if "KPI" in user_request or "指標" in user_request or "サマリー" in user_request:
            components.append("Card")
            
        # タイトルを抽出
        title_match = re.search(r'(.+?レポート)', user_request)
        title = title_match.group(1) if title_match else "レポート"
        
        return {
            "title": title,
            "components": components if components else ["Card", "DataTable"]
        }
    
    def generate_report(self, user_request: str, s3_paths: List[str]) -> Dict[str, Any]:
        """レポートレイアウトを生成"""
        analysis = self.analyze_request(user_request)
        
        # 基本構造を作成
        report = {
            "reportId": f"report_{self.timestamp}",
            "title": analysis["title"],
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
                                "value": analysis["title"],
                                "props": {}
                            }
                        ]
                    }
                ],
                "main": []
            }
        }
        
        section_id = 1
        
        # Cardセクションを追加（必要な場合）
        if "Card" in analysis["components"]:
            report["sections"]["main"].append({
                "id": f"section_main_{section_id}",
                "type": "Default",
                "component": "Card",
                "title": "売上サマリー",
                "description": "主要KPI",
                "contents": [
                    {
                        "source": "TEXT",
                        "component": "Card",
                        "value": "",
                        "props": {
                            "title": "今月の売上",
                            "description": "前月比 +15%",
                            "content": "¥45,280,000",
                            "footer": "目標達成率: 112%"
                        }
                    }
                ]
            })
            section_id += 1
        
        # DataTableセクションを追加（必要な場合）
        if "DataTable" in analysis["components"] and len(s3_paths) > 0:
            # 日別売上データを探す
            daily_sales_path = next((p for p in s3_paths if "daily" in p), s3_paths[0])
            report["sections"]["main"].append({
                "id": f"section_main_{section_id}",
                "type": "Default",
                "component": "DataTable",
                "title": "売上詳細データ",
                "description": "日別の売上推移",
                "contents": [
                    {
                        "source": "S3",
                        "component": "DataTable",
                        "value": daily_sales_path,
                        "props": {}
                    }
                ]
            })
            section_id += 1
        
        # BarChartセクションを追加（必要な場合）
        if "BarChart" in analysis["components"] and len(s3_paths) > 1:
            # カテゴリ別データを探す
            category_sales_path = next((p for p in s3_paths if "category" in p), s3_paths[1] if len(s3_paths) > 1 else s3_paths[0])
            report["sections"]["main"].append({
                "id": f"section_main_{section_id}",
                "type": "Default",
                "component": "BarChart",
                "title": "製品カテゴリ別売上",
                "description": "カテゴリ別の売上比較",
                "contents": [
                    {
                        "source": "S3",
                        "component": "BarChart",
                        "value": category_sales_path,
                        "props": {
                            "xField": "category",
                            "yFields": ["sales", "profit"]
                        }
                    }
                ]
            })
            section_id += 1
        
        # TextFieldセクションを追加
        report["sections"]["main"].append({
            "id": f"section_main_{section_id}",
            "type": "Default",
            "component": "TextField",
            "title": "補足情報",
            "description": "",
            "contents": [
                {
                    "source": "TEXT",
                    "component": "TextField",
                    "value": "このレポートは自動生成されました。データは指定されたS3パスから取得しています。",
                    "props": {}
                }
            ]
        })
        
        return report


# 使用例
if __name__ == "__main__":
    # モックジェネレーターの初期化
    generator = MockReportGenerator()
    
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
    with open('generated_report.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print("レポートが生成されました: generated_report.json")
    print(json.dumps(result, ensure_ascii=False, indent=2))