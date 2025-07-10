"""
AWS Secrets Manager utility functions
"""
import boto3
import json
import os
from typing import Optional

def get_secret(secret_name: str, region: str = "ap-northeast-1") -> Optional[str]:
    """
    AWS Secrets Managerからシークレットを取得
    
    Args:
        secret_name: シークレット名またはARN
        region: AWSリージョン
    
    Returns:
        シークレット値（文字列）
    """
    try:
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region
        )
        
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
        
        # シークレットがJSON形式の場合
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            try:
                # JSON形式の場合はパースして'api_key'フィールドを取得
                secret_dict = json.loads(secret)
                return secret_dict.get('api_key', secret)
            except json.JSONDecodeError:
                # JSON形式でない場合はそのまま返す
                return secret
        else:
            # バイナリ形式の場合（今回は使わない）
            return None
            
    except Exception as e:
        print(f"Error retrieving secret {secret_name}: {str(e)}")
        return None

def get_openai_api_key() -> str:
    """
    OpenAI APIキーを取得（環境変数またはSecrets Manager）
    
    Returns:
        OpenAI APIキー
    """
    # 環境変数をチェック
    api_key = os.getenv("OPENAI_API_KEY")
    
    # Secrets Managerを使用する設定の場合
    if os.getenv("USE_SECRETS_MANAGER", "false").lower() == "true":
        secret_arn = os.getenv(
            "OPENAI_API_KEY_SECRET_ARN",
            "arn:aws:secretsmanager:ap-northeast-1:261581654417:secret:kizukai-openai-api-key-ILO0ZM"
        )
        secret_key = get_secret(secret_arn)
        if secret_key:
            return secret_key
    
    # 環境変数から取得
    if api_key:
        return api_key
    
    raise ValueError("OpenAI API key not found in environment variables or Secrets Manager")