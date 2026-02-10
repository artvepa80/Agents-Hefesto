from hefesto.analyzers.cloud.helm import ANALYZERS


def test_helm_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "HelmAnalyzer"


def test_helm_secrets_detection():
    analyzer = ANALYZERS[0]
    
    # Test case: values.yaml with secrets
    content = """
    database:
      password: "mysecretpassword"
      host: "db.example.com"
      
    apiKey: "AIzaSy..."
    """
    findings = analyzer.analyze(content, "values.yaml")
    
    assert len(findings) >= 2
    assert any("password" in f.evidence for f in findings)
    assert any("apiKey" in f.evidence for f in findings)

def test_helm_ignore_non_values():
    analyzer = ANALYZERS[0]
    content = "apiVersion: v1"
    # Should ignore Chart.yaml or templates (for now)
    findings = analyzer.analyze(content, "Chart.yaml")
    assert len(findings) == 0
