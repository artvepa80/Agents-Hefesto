from hefesto.analyzers.cloud.serverless import ANALYZERS


def test_serverless_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "ServerlessAnalyzer"


def test_serverless_secrets_detection():
    analyzer = ANALYZERS[0]
    
    # Test case: Hardcoded environment variables
    content = """
    service: my-service
    provider:
      name: aws
      environment:
        DB_PASSWORD: "supersecretpassword"
        API_KEY: "12345678"
    functions:
      hello:
        handler: handler.hello
        environment:
          SLACK_TOKEN: "xoxb-1234567890-1234567890-1234567890"
    """
    findings = analyzer.analyze(content, "serverless.yml")
    
    assert len(findings) >= 3
    assert any("DB_PASSWORD" in f.evidence for f in findings)
    assert any("SLACK_TOKEN" in f.evidence for f in findings)
