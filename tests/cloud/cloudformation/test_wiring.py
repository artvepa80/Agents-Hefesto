from hefesto.analyzers.cloud.cloudformation import ANALYZERS


def test_cloudformation_analyzer_registration():
    assert len(ANALYZERS) > 0
    analyzer = ANALYZERS[0]
    assert analyzer.name == "CloudFormationAnalyzer"


def test_cloudformation_secrets_detection():
    analyzer = ANALYZERS[0]

    # Test case 1: Hardcoded DB password in nested property
    content = """
    Resources:
      MyFunction:
        Type: AWS::Lambda::Function
        Properties:
          Environment:
            Variables:
              DB_PASSWORD: "MySecretPassword123"
    """
    findings = analyzer.analyze(content, "template.yaml")

    # Verify we found the secret
    db_findings = [f for f in findings if f.rule_id == "CFN_S001" and "DB_PASSWORD" in f.evidence]
    assert len(db_findings) >= 1
    assert db_findings[0].severity == "CRITICAL"
    assert db_findings[0].format == "cloudformation"


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


def test_cloudformation_insecure_defaults():
    analyzer = ANALYZERS[0]

    content = """
    Resources:
      BadSG:
        Type: AWS::EC2::SecurityGroup
        Properties:
          SecurityGroupIngress:
            - IpProtocol: tcp
              FromPort: 22
              ToPort: 22
              CidrIp: 0.0.0.0/0
      BadBucket:
        Type: AWS::S3::Bucket
        Properties:
          BucketName: public-bucket
      BadRole:
        Type: AWS::IAM::Policy
        Properties:
          PolicyDocument:
            Statement:
              - Effect: Allow
                Action: "*"
                Resource: "*"
    """
    findings = analyzer.analyze(content, "insecure.yaml")

    # Filter by Rule ID first to avoid noise
    cfn_i001 = [f for f in findings if f.rule_id == "CFN_I001"]

    sg_findings = [f for f in cfn_i001 if "Public SG ingress" in f.evidence]
    s3_findings = [f for f in cfn_i001 if "PublicAccessBlockConfiguration" in f.evidence]
    iam_findings = [f for f in cfn_i001 if "IAM policy" in f.evidence]

    assert len(sg_findings) == 1
    assert sg_findings[0].severity == "CRITICAL"

    assert len(s3_findings) == 1
    assert s3_findings[0].severity == "HIGH"

    assert len(iam_findings) == 1
    assert iam_findings[0].severity == "CRITICAL"
