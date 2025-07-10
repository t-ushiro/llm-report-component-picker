#!/bin/bash

# AWS App Runnerデプロイスクリプト

# 色付き出力用
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}AWS App Runner デプロイスクリプト${NC}"
echo "=================================="

# 必要な変数
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="ap-northeast-1"
REPOSITORY_NAME="report-generator-api"
SERVICE_NAME="report-generator-api"

if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}エラー: AWSアカウントIDを取得できません。AWS CLIが設定されているか確認してください。${NC}"
    exit 1
fi

echo -e "${YELLOW}AWSアカウントID: $ACCOUNT_ID${NC}"
echo -e "${YELLOW}リージョン: $REGION${NC}"

# 1. ECRリポジトリの作成
echo -e "\n${GREEN}1. ECRリポジトリを作成中...${NC}"
aws ecr create-repository --repository-name $REPOSITORY_NAME --region $REGION 2>/dev/null || echo "リポジトリは既に存在します"

# 2. ECRログイン
echo -e "\n${GREEN}2. ECRにログイン中...${NC}"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# 3. Dockerイメージのビルド
echo -e "\n${GREEN}3. Dockerイメージをビルド中...${NC}"
docker build -t $REPOSITORY_NAME .

# 4. タグ付けとプッシュ
echo -e "\n${GREEN}4. イメージをECRにプッシュ中...${NC}"
docker tag $REPOSITORY_NAME:latest $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPOSITORY_NAME:latest
docker push $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPOSITORY_NAME:latest

# 5. IAMロールの作成
echo -e "\n${GREEN}5. IAMロールを作成中...${NC}"
aws iam create-role --role-name AppRunnerS3AccessRole --assume-role-policy-document file://trust-policy.json 2>/dev/null || echo "ロールは既に存在します"

# 6. IAMポリシーの作成
echo -e "\n${GREEN}6. IAMポリシーを作成中...${NC}"
POLICY_ARN=$(aws iam create-policy --policy-name AppRunnerS3ReadPolicy --policy-document file://s3-policy.json --query Policy.Arn --output text 2>/dev/null)
if [ -z "$POLICY_ARN" ]; then
    POLICY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/AppRunnerS3ReadPolicy"
    echo "ポリシーは既に存在します"
fi

# 7. ポリシーをロールにアタッチ
echo -e "\n${GREEN}7. ポリシーをロールにアタッチ中...${NC}"
aws iam attach-role-policy --role-name AppRunnerS3AccessRole --policy-arn $POLICY_ARN

echo -e "\n${GREEN}デプロイ準備が完了しました！${NC}"
echo "=================================="
echo -e "${YELLOW}次のステップ:${NC}"
echo "1. AWS App Runnerコンソールにアクセス: https://console.aws.amazon.com/apprunner"
echo "2. 'Create service' をクリック"
echo "3. Source: Container registry → Amazon ECR"
echo "4. Image URI: $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPOSITORY_NAME:latest"
echo "5. Service name: $SERVICE_NAME"
echo "6. Environment variables:"
echo "   - API_KEY_REQUIRED = false (開発環境)"
echo "   - ALLOWED_S3_BUCKET = kizukai-ds-tmp"
echo "7. Instance role: AppRunnerS3AccessRole"
echo ""
echo -e "${GREEN}または、以下のCLIコマンドを実行:${NC}"
echo ""
cat << EOF
aws apprunner create-service \\
  --service-name "$SERVICE_NAME" \\
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPOSITORY_NAME:latest",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "API_KEY_REQUIRED": "false",
          "ALLOWED_S3_BUCKET": "kizukai-ds-tmp"
        }
      },
      "ImageRepositoryType": "ECR"
    },
    "AutoDeploymentsEnabled": false
  }' \\
  --instance-configuration '{
    "Cpu": "0.25 vCPU",
    "Memory": "0.5 GB",
    "InstanceRoleArn": "arn:aws:iam::$ACCOUNT_ID:role/AppRunnerS3AccessRole"
  }'
EOF