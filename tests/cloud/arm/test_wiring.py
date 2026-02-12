from hefesto.analyzers.cloud.arm import ANALYZERS


def test_arm_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "ArmAnalyzer"


def test_arm_secrets_detection():
    analyzer = ANALYZERS[0]

    # Test case: Insecure parameters
    schema_url = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    content = f"""
    {{
        "$schema": "{schema_url}",
        "contentVersion": "1.0.0.0",
        "parameters": {{
            "adminPassword": {{
                "type": "string",
                "defaultValue": "CorrectHorseBatteryStaple"
            }}
        }},
        "resources": [
            {{
                "type": "Microsoft.Web/sites",
                "properties": {{
                    "password": "MySecretPassword"
                }}
            }}
        ]
    }}
    """
    findings = analyzer.analyze(content, "azuredeploy.json")

    # Expect 2 findings: 1 for defaultValue (HIGH), 1 for resource property (HIGH/CRITICAL)
    assert len(findings) >= 2
    assert all(f.format == "arm" for f in findings)


def test_arm_deduplication():
    analyzer = ANALYZERS[0]
    content = """
    {
        "resources": [
            {
                "properties": {
                    "awsKey": "AKIA1234567890ABCDEF"
                }
            }
        ]
    }
    """
    findings = analyzer.analyze(content, "template.json")
    assert len(findings) == 1
    assert findings[0].severity == "CRITICAL"


def test_arm_insecure_defaults():
    analyzer = ANALYZERS[0]

    content = """
    {
        "resources": [
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "nsg-test",
                "properties": {
                    "securityRules": [
                        {
                            "name": "AllowSSH",
                            "properties": {
                                "access": "Allow",
                                "direction": "Inbound",
                                "sourceAddressPrefix": "*",
                                "destinationPortRange": "22"
                            }
                        }
                    ]
                }
            },
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "publicstorage",
                "properties": {
                    "allowBlobPublicAccess": true,
                    "networkAcls": {
                        "defaultAction": "Allow"
                    }
                }
            }
        ]
    }
    """
    findings = analyzer.analyze(content, "insecure.json")

    nsg_findings = [f for f in findings if "NSG Rule" in f.evidence]
    storage_blob = [f for f in findings if "allowBlobPublicAccess" in f.evidence]
    storage_acl = [f for f in findings if "networkAcls.defaultAction" in f.evidence]

    assert len(nsg_findings) == 1
    assert nsg_findings[0].severity == "CRITICAL"

    assert len(storage_blob) == 1
    assert storage_blob[0].severity == "HIGH"

    assert len(storage_acl) == 1
    assert storage_acl[0].severity == "MEDIUM"
