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
    functions:
      hello:
        handler: handler.hello
        environment:
          SLACK_TOKEN: "xoxb-1234567890-1234567890-1234567890"
    """
    findings = analyzer.analyze(content, "serverless.yml")

    assert len(findings) >= 2

    # Check formats
    assert all(f.format == "serverless" for f in findings)

    # Check rules
    assert all(f.rule_id == "SLS_S001" for f in findings)


def test_serverless_deduplication():
    analyzer = ANALYZERS[0]
    content = """
    provider:
      environment:
        AWS_SECRET_KEY: "AKIA1234567890ABCDEF"
    """
    findings = analyzer.analyze(content, "serverless.yaml")

    # Expect 1 CRITICAL finding, not HIGH+CRITICAL
    assert len(findings) == 1
    assert findings[0].severity == "CRITICAL"


def test_serverless_insecure_defaults():
    analyzer = ANALYZERS[0]

    content = """
    provider:
      name: aws
      iam:
        role:
          statements:
            - Effect: Allow
              Action: "*"
              Resource: "*"

    functions:
      myFunc:
        handler: index.handler
        iamRoleStatements:
          - Effect: Allow
            Action:
              - "*"
            Resource: "*"
    """
    findings = analyzer.analyze(content, "serverless.yml")

    iam_findings = [f for f in findings if "IAM Statement" in f.evidence]

    # Should catch 2: one in provider, one in function
    assert len(iam_findings) == 2
    assert all(f.severity == "CRITICAL" for f in iam_findings)
