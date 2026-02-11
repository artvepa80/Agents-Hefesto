from hefesto.analyzers.cloud.helm import ANALYZERS


def test_helm_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "HelmAnalyzer"


def test_helm_secrets_detection():
    analyzer = ANALYZERS[0]

    # Test case: values.yaml with secrets (recursive list, deep dict)
    content = """
    database:
      - name: main
        credentials:
          password: "mysecretpassword"

    apiKey: "AIzaSyFakeKeyWithMoreThan30CharactersHere123456"
    nonSecret: "{{ .Values.stuff }}"
    """
    findings = analyzer.analyze(content, "values.yaml")

    # Expect:
    # 1. password -> HIGH or CRITICAL? "mysecretpassword" is not critical pattern,
    #    but key is suspicious. -> HIGH
    # 2. apiKey -> AIzaSy... matches critical pattern -> CRITICAL

    passwords = [f for f in findings if "password" in f.evidence]
    apikeys = [f for f in findings if "Google API Key" in f.evidence]

    assert len(passwords) >= 1
    assert passwords[0].severity == "HIGH"  # suspicious key + hardcoded value
    assert passwords[0].format == "helm"

    assert len(apikeys) >= 1
    assert apikeys[0].severity == "CRITICAL"  # critical pattern match


def test_helm_deduplication():
    # Test deduplication: Critical pattern + Suspicious key should yield ONLY Critical
    analyzer = ANALYZERS[0]
    content = """
    aws_secret_key: "AKIA1234567890ABCDEF"
    """
    findings = analyzer.analyze(content, "values.yaml")

    assert len(findings) == 1
    assert findings[0].severity == "CRITICAL"
    assert "Critical secret pattern" in findings[0].evidence


def test_helm_ignore_non_values():
    analyzer = ANALYZERS[0]
    content = "apiVersion: v1"
    findings = analyzer.analyze(content, "Chart.yaml")
    assert len(findings) == 0


def test_helm_accept_yml():
    analyzer = ANALYZERS[0]
    content = "password: secret"
    findings = analyzer.analyze(content, "values.yml")
    assert len(findings) > 0
    findings = analyzer.analyze(content, "values.yml")
    assert len(findings) > 0


def test_helm_insecure_defaults():
    analyzer = ANALYZERS[0]

    content = """
    # Security Context
    securityContext:
      privileged: true
      runAsUser: 0

    # Host Namespaces
    hostPID: true

    # LoadBalancer
    service:
      type: LoadBalancer
      loadBalancerSourceRanges:
        - "0.0.0.0/0"
    """
    findings = analyzer.analyze(content, "values.yaml")

    priv_findings = [f for f in findings if "privileged: true" in f.evidence]
    root_findings = [f for f in findings if "runAsUser: 0" in f.evidence]
    host_findings = [f for f in findings if "hostPID: true" in f.evidence]
    lb_findings = [f for f in findings if "LoadBalancer allows public access" in f.evidence]

    assert len(priv_findings) == 1
    assert priv_findings[0].severity == "CRITICAL"

    assert len(root_findings) == 1
    assert root_findings[0].severity == "HIGH"

    assert len(host_findings) == 1
    assert host_findings[0].severity == "HIGH"

    assert len(lb_findings) == 1
    assert lb_findings[0].severity == "HIGH"
