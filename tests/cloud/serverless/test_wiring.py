from hefesto.analyzers.cloud.serverless import ANALYZERS


def test_serverless_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "ServerlessNoopAnalyzer"


def test_serverless_analyzer_execution():
    analyzer = ANALYZERS[0]
    findings = analyzer.analyze("service: test", "serverless.yml")
    assert isinstance(findings, list)
    assert len(findings) == 0
