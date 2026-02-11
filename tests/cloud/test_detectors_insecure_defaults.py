from hefesto.analyzers.cloud.detectors_insecure_defaults import InsecureDefaultsDetector


def test_classify_sg_unexpected_severity_critical():
    # Public + Sensitive = CRITICAL
    # SSH (22) + 0.0.0.0/0
    severity = InsecureDefaultsDetector.classify_sg_unexpected_severity(
        proto="tcp", from_port=22, to_port=22, cidr4="0.0.0.0/0", cidr6=None
    )
    assert severity == "CRITICAL"

    # All traffic (-1) + 0.0.0.0/0 = CRITICAL
    severity = InsecureDefaultsDetector.classify_sg_unexpected_severity(
        proto="-1", from_port=-1, to_port=-1, cidr4="0.0.0.0/0", cidr6=None
    )
    assert severity == "CRITICAL"


def test_classify_sg_unexpected_severity_high():
    # Public but NOT Sensitive = HIGH
    # HTTP (80) + 0.0.0.0/0
    severity = InsecureDefaultsDetector.classify_sg_unexpected_severity(
        proto="tcp", from_port=80, to_port=80, cidr4="0.0.0.0/0", cidr6=None
    )
    assert severity == "HIGH"

    # Sensitive but NOT Public = HIGH
    # SSH (22) + 10.0.0.0/8
    severity = InsecureDefaultsDetector.classify_sg_unexpected_severity(
        proto="tcp", from_port=22, to_port=22, cidr4="10.0.0.0/8", cidr6=None
    )
    assert severity == "HIGH"
