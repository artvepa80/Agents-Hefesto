from hefesto.analyzers.cloud.arm import ANALYZERS


def test_arm_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "ArmAnalyzer"


def test_arm_secrets_detection():
    analyzer = ANALYZERS[0]
    
    # Test case: Insecure parameters
    content = """
    {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {
            "adminPassword": {
                "type": "string",
                "defaultValue": "CorrectHorseBatteryStaple"
            },
            "apiToken": {
                "type": "secureString"
            }
        },
        "resources": []
    }
    """
    findings = analyzer.analyze(content, "azuredeploy.json")
    
    # Expect 2 findings: 1 for defaultValue, 1 for type: string
    assert len(findings) >= 2
    assert any("hardcoded defaultValue" in f.evidence for f in findings)
    assert any("uses type 'string'" in f.evidence for f in findings)
