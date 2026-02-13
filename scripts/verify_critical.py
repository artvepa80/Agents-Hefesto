import re

from hefesto.analyzers.cloud.detectors import SecretDetector

secret = "AKIA0123456789012345"
print(f"Testing value: {secret}")
findings = SecretDetector.check_value(secret)
print(f"Findings: {findings}")

if findings:
    print("✅ Secret detected by SecretDetector")
else:
    print("❌ Secret NOT detected by SecretDetector")
