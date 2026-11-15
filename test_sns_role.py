import os
import boto3

arn = "arn:aws:sns:us-east-1:400131408828:NIDS-Alerts"
reg = "us-east-1"

print("[*] Testing default credentials (IAM Role / AWS CLI)...")
sns = boto3.client("sns", region_name=reg)
try:
    res = sns.publish(
        TopicArn=arn,
        Subject="[NIDS ALERT] Test Cảnh báo",
        Message="Test Alert via IAM Role"
    )
    print("[✓] GỬI SNS THÀNH CÔNG!", res.get("MessageId"))
except Exception as e:
    print("[✗] Error with default credentials:", type(e).__name__, e)
