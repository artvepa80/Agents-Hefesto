from hefesto.analyzers.cloud.arm import ANALYZERS


def test_arm_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "ArmNoopAnalyzer"


def test_arm_analyzer_execution():
    analyzer = ANALYZERS[0]
    findings = analyzer.analyze("{}", "template.json")
    assert isinstance(findings, list)
    assert len(findings) == 0
