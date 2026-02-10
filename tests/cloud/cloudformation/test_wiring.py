from hefesto.analyzers.cloud.cloudformation import ANALYZERS


def test_cloudformation_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "CloudFormationNoopAnalyzer"


def test_cloudformation_analyzer_execution():
    analyzer = ANALYZERS[0]
    findings = analyzer.analyze("Resources:\n  test: test", "test.yaml")
    assert isinstance(findings, list)
    assert len(findings) == 0
