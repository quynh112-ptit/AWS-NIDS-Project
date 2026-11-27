import os
import boto3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
ak = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
sk = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
reg = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")).strip()
arn = os.getenv("SNS_TOPIC_ARN", "").strip()

print(f"[*] Access Key: {ak[:4]}****" if ak else "[*] Access Key: (không có - dùng IAM Role)")
print("[*] Secret Key: " + ("(đã ẩn)" if sk else "(không có)"))
print(f"[*] Region: {reg}")
print(f"[*] SNS ARN: {arn}")

if not ak or not sk:
    print("[!] Chú ý: Không tìm thấy Access Key / Secret Key trong .env. Sử dụng IAM Role mặc định...")
    sns = boto3.client("sns", region_name=reg)
else:
    sns = boto3.client(
        "sns",
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        region_name=reg
    )

try:
    res = sns.publish(
        TopicArn=arn,
        Subject="[NIDS ALERT] Test Cảnh báo",
        Message="[NIDS SECURITY ALERT]\n⚠️ Phát hiện bất thường mạng từ hệ thống giám sát NIDS Demo!"
    )
    print(f"[✓] GỬI SNS THÀNH CÔNG! MessageId: {res.get('MessageId')}")
except Exception as e:
    print(f"[✗] Lỗi gửi SNS: {type(e).__name__}: {e}")
