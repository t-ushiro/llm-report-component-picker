from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from agents import Agent, Runner, function_tool,WebSearchTool
import pandas as pd
import json
import asyncio
from dotenv import load_dotenv
import os
import re
from agents.tracing import set_tracing_disabled, set_tracing_export_api_key

# .envファイルを読み込む
load_dotenv()

# APIキーが設定されているか確認
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEYが設定されていません。.envファイルを確認してください。")





# トレース機能を有効化（デフォルトで有効）
set_tracing_disabled(False)

# APIキーをトレースエクスポート用に設定
set_tracing_export_api_key(os.getenv("OPENAI_API_KEY"))


@dataclass
class Goal:
    goal: str
    period: str

@dataclass
class CSVMetadata:
    id: str
    columns: List[str]
    period: str
    row_count: int

@dataclass
class Requirement:
    metrics: List[str]
    granularity: str
    period: str

@dataclass
class DataGap:
    missing_columns: List[str]
    missing_periods: List[str]
    granularity_mismatch: str | None = None

@dataclass
class ReportSection:
    title: str
    subsections: List[Dict[str, Any]]
    component_type: Optional[str] = None
    props: Optional[Dict[str, Any]] = None

@function_tool
def read_csv_head(file_path: str, n_rows: int) -> pd.DataFrame:
    """Read the first n rows of a CSV file and return metadata."""
    try:
        df = pd.read_csv(file_path, nrows=n_rows)
        total_rows = sum(1 for _ in open(file_path)) - 1  # Subtract header row
        
        # Try to identify date columns
        date_columns = []
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]) or \
               any(keyword in col.lower() for keyword in ['date', 'time', 'period']):
                date_columns.append(col)
        
        return {
            "data": df,
            "total_rows": total_rows,
            "date_columns": date_columns
        }
    except Exception as e:
        return {"error": str(e)}

@function_tool
def generate_json_report(sections: list) -> str:
    """Generate JSON report from sections."""
    report = {
        "report": {
            "title": "Generated Report",
            "sections": sections,
            "metadata": {
                "generated_at": pd.Timestamp.now().isoformat(),
                "version": "1.0"
            }
        }
    }
    return json.dumps(report, indent=2)

# Goal Analyzer Agent
goal_analyzer = Agent(
    name="Goal Analyzer",
    instructions="""入力テキストから目的と期間を抽出します。
    Goalオブジェクトの形式で返してください。
    
    入力例: "2024年第1四半期の売上データを分析して"
    出力例: {
        "goal": "売上データの分析",
        "period": "2024年第1四半期"
    }
    
    以下の点に注意してください：
    1. 主要な目的（goal）の特定
    2. 期間情報の抽出
    3. 両方のフィールドが適切にフォーマットされていることの確認
    """,
    tools=[read_csv_head],
    output_type=Goal,
)

# CSV Metadata Analyzer Agent
csv_analyzer = Agent(
    name="CSV Metadata Analyzer",
    instructions="""CSVファイルを分析し、列名、期間、行数などのメタデータを抽出します。
    CSVMetadataオブジェクトのリストを返してください。
    
    各CSVファイルについて：
    1. 最初の数行を読み込んで構造を理解
    2. 列名を抽出
    3. 日付/時間列を特定して期間を決定
    4. 総行数をカウント
    
    出力例: {
        "id": "sales_data_2024",
        "columns": ["日付", "商品", "売上", "数量"],
        "period": "2024-01 から 2024-03",
        "row_count": 1000
    }
    
    read_csv_headツールを使用してファイル構造を分析してください。
    """,
    tools=[read_csv_head],
    output_type=CSVMetadata,
)

# Requirement Analyzer Agent
requirement_analyzer = Agent(
    name="Requirement Analyzer",
    instructions="""目的に基づいて、必要な指標、粒度、期間を決定します。
    Requirementオブジェクトを返してください。
    
    目的を分析して以下を特定：
    1. 必要な指標（例：売上、収益、成長率）
    2. データの粒度（日次、週次、月次など）
    3. 分析期間
    
    入力例: {
        "goal": "売上データの分析",
        "period": "2024年第1四半期"
    }
    
    出力例: {
        "metrics": ["総売上", "商品別売上", "成長率"],
        "granularity": "日次",
        "period": "2024-01-01 から 2024-03-31"
    }
    
    一般的なビジネス指標やKPIを考慮して要件を決定してください。
    """,
    output_type=Requirement,
)

# Data Gap Analyzer Agent
gap_analyzer = Agent(
    name="Data Gap Analyzer",
    instructions="""要件と利用可能なデータを比較して、不足している部分を特定します。
    DataGapオブジェクトを返してください。
    
    各要件について：
    1. 必要な指標がデータに含まれているか確認
    2. データの粒度が要件と一致するか確認
    3. 期間がカバーされているか確認
    
    入力例: {
        "requirements": {
            "metrics": ["総売上", "商品別売上"],
            "granularity": "日次",
            "period": "2024-01-01 から 2024-03-31"
        },
        "metadata": [{
            "columns": ["日付", "商品", "売上"],
            "period": "2024-01 から 2024-02"
        }]
    }
    
    出力例: {
        "missing_columns": ["成長率"],
        "missing_periods": ["2024-03"],
        "granularity_mismatch": "日次データが週次データに変換されていない可能性"
    }
    
    不足しているデータとその理由を具体的に示してください。
    """,
    output_type=DataGap,
)

# Data Completer Agent
data_completer = Agent(
    name="Data Completer",
    instructions="""不足しているデータを検索し、必要に応じて追加のアップロードを要求します。
    更新されたデータまたは追加アップロードの要求を返してください。
    
    各ギャップについて：
    1. Webソースから不足データを検索
    2. Webデータが利用できない場合は追加アップロードを要求
    3. 必要なデータについて明確な指示を提供
    
    入力例: {
        "missing_columns": ["成長率"],
        "missing_periods": ["2024-03"]
    }
    
    出力例: {
        "web_data_found": {
            "成長率": "https://example.com/growth_data.csv"
        },
        "additional_uploads_needed": {
            "2024-03": "2024年3月の売上データをアップロードしてください"
        }
    }
    
    WebSearchToolを使用して不足情報を検索してください。
    """,
    tools=[WebSearchTool()],
    # output_type=DataCompletion,
)

# Report Planner Agent
report_planner = Agent(
    name="Report Planner",
    instructions="""レポートの構造（セクションとサブセクション）を計画します。
    ReportSectionオブジェクトのリストを返してください。
    
    以下の点を考慮した論理的な構造を作成：
    1. エグゼクティブサマリーから開始
    2. 関連する指標をグループ化
    3. 概要から詳細分析へと進展
    4. アクション可能な洞察を含める
    
    入力例: {
        "goal": "売上データの分析",
        "requirements": {
            "metrics": ["総売上", "商品別売上"],
            "granularity": "日次",
            "period": "2024-01-01 から 2024-03-31"
        }
    }
    
    出力例: [{
        "title": "エグゼクティブサマリー",
        "subsections": [
            {
                "title": "主要な発見",
                "content": "主要な洞察の概要"
            }
        ],
        "component_type": "text",
        "props": {
            "style": "summary"
        }
    }, {
        "title": "売上分析",
        "subsections": [
            {
                "title": "総売上推移",
                "content": "日次売上推移の分析"
            }
        ],
        "component_type": "line_chart",
        "props": {
            "x_axis": "日付",
            "y_axis": "売上"
        }
    }]
    
    情報の流れを明確かつ論理的に作成することに焦点を当ててください。
    """,
    # output_type=ReportSection,
)

# Component Designer Agent
component_designer = Agent(
    name="Component Designer",
    instructions="""各セクションの可視化コンポーネントを設計します。
    コンポーネントの詳細を含む更新されたReportSectionオブジェクトを返してください。
    
    各セクションについて：
    1. 適切な可視化タイプを選択
    2. データマッピングを設定
    3. 表示プロパティを設定
    
    利用可能なコンポーネントタイプ：
    - line_chart: 時系列データ用
    - bar_chart: カテゴリ比較用
    - pie_chart: 比率分析用
    - table: 詳細データ表示用
    - text: テキストコンテンツ用
    
    入力例: [{
        "title": "売上分析",
        "subsections": [
            {
                "title": "総売上推移",
                "content": "日次売上推移の分析"
            }
        ]
    }]
    
    出力例: [{
        "title": "売上分析",
        "subsections": [
            {
                "title": "総売上推移",
                "content": "日次売上推移の分析",
                "component_type": "line_chart",
                "props": {
                    "x_axis": "日付",
                    "y_axis": "売上",
                    "title": "日次売上推移",
                    "show_grid": true,
                    "y_axis_format": "currency"
                }
            }
        ]
    }]
    
    データタイプと可視化のベストプラクティスを考慮してください。
    """,
    # output_type=ReportSection,
)

# JSON Generator Agent
json_generator = Agent(
    name="JSON Generator",
    instructions="""レポートの最終JSON構造を生成します。
    JSON文字列を返してください。
    
    JSON構造は以下を満たす必要があります：
    1. ReportSectionスキーマに従う
    2. 必要なメタデータを含む
    3. 適切にフォーマットされ、有効である
    
    入力例: [{
        "title": "売上分析",
        "subsections": [
            {
                "title": "総売上推移",
                "component_type": "line_chart",
                "props": {
                    "x_axis": "日付",
                    "y_axis": "売上"
                }
            }
        ]
    }]
    
    出力例: {
        "report": {
            "title": "売上分析レポート",
            "sections": [
                {
                    "title": "売上分析",
                    "subsections": [
                        {
                            "title": "総売上推移",
                            "component_type": "line_chart",
                            "props": {
                                "x_axis": "日付",
                                "y_axis": "売上"
                            }
                        }
                    ]
                }
            ],
            "metadata": {
                "generated_at": "2024-03-20T10:00:00Z",
                "version": "1.0"
            }
        }
    }
    
    generate_json_reportツールを使用して最終JSONを作成してください。
    """,
    tools=[generate_json_report],
)

# Validator Agent
validator = Agent(
    name="Validator",
    instructions="""生成されたJSONを検証し、問題がないか確認します。
    検証結果と必要な修正を提案してください。
    
    以下を確認：
    1. JSON構文の有効性
    2. 必須フィールドの存在
    3. データ型の一貫性
    4. コンポーネントプロパティの有効性
    5. セクション構造の整合性
    
    入力例: {
        "report": {
            "title": "売上分析レポート",
            "sections": [...]
        }
    }
    
    出力例: {
        "is_valid": true,
        "issues": [],
        "suggestions": []
    }
    
    または問題が見つかった場合：
    {
        "is_valid": false,
        "issues": [
            {
                "section": "売上分析",
                "problem": "line_chartコンポーネントに必須プロパティ'x_axis'がありません",
                "suggestion": "コンポーネントのpropsにx_axisプロパティを追加してください"
            }
        ],
        "suggestions": [
            "冒頭にサマリーセクションを追加することを検討してください"
        ]
    }
    
    明確で実行可能なフィードバックを提供してください。
    """,
)

async def process_csv_report(input_text: str, csv_files: List[str]) -> str:
    """Main function to process CSV files and generate a report."""
    
    # Step 1: Analyze goal
    goal_result = await Runner.run(goal_analyzer, input_text)
    print("goal_result.final_output:", goal_result.final_output)  # デバッグ用
    # 文字列ならパース
    if isinstance(goal_result.final_output, Goal):
        goal = goal_result.final_output
    else:
        if isinstance(goal_result.final_output, str):
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', goal_result.final_output, re.DOTALL)
            if json_match:
                goal_dict = json.loads(json_match.group(1))
            else:
                goal_dict = json.loads(goal_result.final_output)
        else:
            goal_dict = goal_result.final_output
        goal = Goal(**goal_dict)
    
    # Step 2: Analyze CSV metadata
    csv_metadata_results = []
    for csv_file in csv_files:
        result = await Runner.run(csv_analyzer, csv_file)
        print("csv_analyzer result.final_output:", result.final_output)  # デバッグ用
        if not result.final_output:
            raise ValueError(f"CSV analyzer returned empty output for file: {csv_file}")
        if isinstance(result.final_output, CSVMetadata):
            csv_metadata_results.append(result.final_output)
        else:
            if isinstance(result.final_output, str):
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', result.final_output, re.DOTALL)
                if json_match:
                    meta_dict = json.loads(json_match.group(1))
                else:
                    # Markdown形式をパース
                    id_match = re.search(r'\*\*(ID|ファイル名)\*\*:\s*(.+)', result.final_output)
                    columns_match = re.search(r'\*\*列名\*\*:\s*(\[.*\])', result.final_output)
                    period_match = re.search(r'\*\*期間\*\*:\s*(.+)', result.final_output)
                    row_count_match = re.search(r'\*\*行数\*\*:\s*(\d+)', result.final_output)
                    if id_match and columns_match and period_match and row_count_match:
                        meta_dict = {
                            "id": id_match.group(2).strip(),
                            "columns": json.loads(columns_match.group(1)),
                            "period": period_match.group(1).strip(),
                            "row_count": int(row_count_match.group(1))
                        }
                    else:
                        raise ValueError(f"CSV analyzer output does not contain valid metadata: {result.final_output}")
            else:
                meta_dict = result.final_output
            csv_metadata_results.append(CSVMetadata(**meta_dict))
    
    # Step 3: Analyze requirements
    req_result = await Runner.run(requirement_analyzer, input_text)
    print("req_result.final_output:", req_result.final_output)  # デバッグ用
    if not req_result.final_output:
        raise ValueError("Requirements analyzer returned empty output")
    if isinstance(req_result.final_output, Requirement):
        requirements = req_result.final_output
    else:
        if isinstance(req_result.final_output, str):
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', req_result.final_output, re.DOTALL)
            if json_match:
                req_dict = json.loads(json_match.group(1))
            else:
                raise ValueError(f"Requirements output does not contain valid JSON: {req_result.final_output}")
        else:
            req_dict = req_result.final_output
        requirements = Requirement(**req_dict)
    
    # Step 4: Analyze data gaps
    gap_result = await Runner.run(gap_analyzer, json.dumps({
        "goal": goal.__dict__ if hasattr(goal, '__dict__') else goal,
        "csv_metadata": [meta.__dict__ if hasattr(meta, '__dict__') else meta for meta in csv_metadata_results],
        "requirements": requirements.__dict__ if hasattr(requirements, '__dict__') else requirements
    }))
    print("gap_result.final_output:", gap_result.final_output)  # デバッグ用
    if not gap_result.final_output:
        raise ValueError("Data gap analyzer returned empty output")
    if isinstance(gap_result.final_output, DataGap):
        gaps = gap_result.final_output
    else:
        if isinstance(gap_result.final_output, str):
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', gap_result.final_output, re.DOTALL)
            if json_match:
                gap_dict = json.loads(json_match.group(1))
            else:
                raise ValueError(f"Data gap output does not contain valid JSON: {gap_result.final_output}")
        else:
            gap_dict = gap_result.final_output
        gaps = DataGap(**gap_dict)
    
    # Step 5: Complete missing data
    if gaps.missing_columns or gaps.missing_periods:
        completer_result = await Runner.run(data_completer, json.dumps(gaps.__dict__))
        print("completer_result.final_output:", completer_result.final_output)  # デバッグ用
        if not completer_result.final_output:
            raise ValueError("Data completer returned empty output")
        if isinstance(completer_result.final_output, str):
            # JSON部分を抽出
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', completer_result.final_output, re.DOTALL)
            if json_match:
                completer_dict = json.loads(json_match.group(1))
            else:
                # JSONでなければテキストとして保存
                completer_dict = {"raw_text": completer_result.final_output}
        else:
            completer_dict = completer_result.final_output
        # Handle data completion results（必要に応じて raw_text を利用）
    
    # Step 6-7: Plan report structure
    plan_result = await Runner.run(report_planner, json.dumps({
        "goal": goal.__dict__,
        "requirements": requirements.__dict__,
        "metadata": [m.__dict__ for m in csv_metadata_results]
    }))
    print("plan_result.final_output:", plan_result.final_output)  # デバッグ用
    if not plan_result.final_output:
        raise ValueError("Report planner returned empty output")
    if isinstance(plan_result.final_output, str):
        # ```json ... ``` または ```python ... ``` で囲まれた部分を抽出
        json_match = re.search(r'```(?:json|python)\s*(\[.*?\])\s*```', plan_result.final_output, re.DOTALL)
        if json_match:
            sections_data = json.loads(json_match.group(1))
        else:
            try:
                sections_data = json.loads(plan_result.final_output)
            except json.JSONDecodeError:
                raise ValueError(f"Plan result output does not contain valid JSON: {plan_result.final_output}")
    else:
        sections_data = plan_result.final_output
    sections = [ReportSection(**s) for s in sections_data]

    # Step 8-9: Design components
    design_result = await Runner.run(component_designer, json.dumps({"sections": [s.__dict__ for s in sections]}))
    print("design_result.final_output:", design_result.final_output)  # デバッグ用
    if not design_result.final_output:
        raise ValueError("Component designer returned empty output")
    if isinstance(design_result.final_output, str):
        # ```json ... ``` で囲まれた部分を抽出
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', design_result.final_output, re.DOTALL)
        if json_match:
            sections_data = json.loads(json_match.group(1))
        else:
            try:
                sections_data = json.loads(design_result.final_output)
            except json.JSONDecodeError:
                raise ValueError(f"Design result output does not contain valid JSON: {design_result.final_output}")
    else:
        sections_data = design_result.final_output
    sections = [ReportSection(**s) for s in sections_data["sections"]]

    # Step 10-11: Generate JSON
    json_result = await Runner.run(json_generator, json.dumps([s.__dict__ for s in sections]))
    print("json_result.final_output:", json_result.final_output)  # デバッグ用
    if not json_result.final_output:
        raise ValueError("JSON generator returned empty output")
    if isinstance(json_result.final_output, str):
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', json_result.final_output, re.DOTALL)
        if json_match:
            final_json = json.loads(json_match.group(1))
        else:
            try:
                final_json = json.loads(json_result.final_output)
            except json.JSONDecodeError:
                raise ValueError(f"JSON generator output does not contain valid JSON: {json_result.final_output}")
    else:
        final_json = json_result.final_output
    
    # Step 12: Validate
    validation_result = await Runner.run(validator, json_result.final_output)
    if hasattr(validation_result.final_output, 'get') and validation_result.final_output.get("has_issues", False):
        # Handle validation issues
        pass
    
    return json_result.final_output

if __name__ == "__main__":
    # サンプル使用例
    input_text = "2024年第1四半期の売上データを分析して、商品別の売上推移と成長率を確認したい"
    csv_files = ["sales_data_2024_q1.csv"]
    result = asyncio.run(process_csv_report(input_text, csv_files))
    print(result)
