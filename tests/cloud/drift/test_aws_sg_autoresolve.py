from unittest.mock import MagicMock, patch

from hefesto.analyzers.cloud.drift.aws_sg import AwsSgDriftDetector
from hefesto.analyzers.cloud.drift.base import DriftContext


def test_drift_autoresolve_populates_resource_map_and_runs():
    detector = AwsSgDriftDetector()

    template = {
        "Resources": {
            "TestSG": {
                "Type": "AWS::EC2::SecurityGroup",
                "Properties": {
                    "SecurityGroupIngress": [
                        {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "CidrIp": "10.0.0.0/8"}
                    ]
                },
            }
        }
    }

    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = type(
        "RR", (), {"resource_map": {"TestSG": "sg-12345"}, "evidence": ["ok"]}
    )()

    ctx = DriftContext(
        region="us-east-1",
        template_path="t.yaml",
        credentials=MagicMock(),
        resource_map=None,
        resolver=fake_resolver,
    )

    with patch("hefesto.analyzers.cloud.drift.aws_sg.AwsClient") as MockClient:
        MockClient.return_value.get_security_groups.return_value = [
            {
                "GroupId": "sg-12345",
                "IpPermissions": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 80,
                        "ToPort": 80,
                        "IpRanges": [{"CidrIp": "10.0.0.0/8"}],
                    }
                ],
            }
        ]

        findings = detector.detect_drift(template, ctx)
        assert findings == []  # identical, no drift
        assert ctx.resource_map == {"TestSG": "sg-12345"}  # populated
