from hefesto.analyzers.cloud.cloudformation import ANALYZERS


def test_cloudformation_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "CloudFormationAnalyzer"  # Updated name


def test_cloudformation_secrets_detection():
    analyzer = ANALYZERS[0]
    
    # Test case 1: Hardcoded DB password in Resources
    content = """
    Resources:
      MyDB:
        Type: AWS::RDS::DBInstance
        Properties:
          MasterUsername: admin
          MasterUserPassword: "MySecretPassword123"
    """
    findings = analyzer.analyze(content, "template.yaml")
    
    # Verify we found the secret
    db_findings = [f for f in findings if f.rule_id == "CFN_S001" and "MasterUserPassword" in f.evidence]
    assert len(db_findings) == 1
    assert db_findings[0].severity == "CRITICAL"

def test_cloudformation_parameter_detection():
    analyzer = ANALYZERS[0]
    
    # Test case 2: Parameter defaults + missing NoEcho
    content = """
    Parameters:
      DBPassword:
        Type: String
        Default: "changeme123"
    """
    findings = analyzer.analyze(content, "params.yaml")
    
    # Expect 2 findings: 1 for default value, 1 for missing NoEcho
    assert len(findings) >= 1
    assert any("hardcoded default" in f.evidence for f in findings)
    assert any("missing NoEcho" in f.evidence for f in findings)
