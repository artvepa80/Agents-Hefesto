from hefesto.analyzers.cloud.helm import ANALYZERS


def test_helm_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "HelmNoopAnalyzer"


def test_helm_analyzer_execution():
    analyzer = ANALYZERS[0]
    findings = analyzer.analyze("apiVersion: v1", "Chart.yaml")
    assert isinstance(findings, list)
    assert len(findings) == 0
