import unittest
from unittest.mock import MagicMock, patch

from hefesto.analyzers.cloud.drift.aws_sg import AwsSgDriftDetector
from hefesto.analyzers.cloud.drift.base import DriftContext


class TestAwsSgDrift(unittest.TestCase):

    def setUp(self):
        self.detector = AwsSgDriftDetector()
        self.context = DriftContext(
            region="us-east-1",
            template_path="test_template.yaml",
            resource_map={"TestSG": "sg-12345"},
            credentials=MagicMock(),
        )

    def test_drift_skipped_no_creds(self):
        # Case: No creds -> DRIFT_AWS_AUTH_SKIPPED
        context = DriftContext(
            region="us-east-1",
            template_path="t.yaml",
            resource_map={"TestSG": "sg-1"},
            credentials=None,
        )
        template = {"Resources": {"TestSG": {"Type": "AWS::EC2::SecurityGroup"}}}

        findings = self.detector.detect_drift(template, context)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "DRIFT_AWS_AUTH_SKIPPED")
        self.assertEqual(findings[0].location.path, "t.yaml")

    def test_drift_skipped_no_map(self):
        # Case: No resource map -> DRIFT_AWS_MAP_SKIPPED
        context = DriftContext(
            region="us-east-1", template_path="t.yaml", resource_map={}, credentials=MagicMock()
        )
        template = {
            "Resources": {
                "TestSG": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {
                        "SecurityGroupIngress": [
                            {
                                "IpProtocol": "tcp",
                                "FromPort": 80,
                                "ToPort": 80,
                                "CidrIp": "10.0.0.0/8",
                            }
                        ]
                    },
                }
            }
        }

        findings = self.detector.detect_drift(template, context)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "DRIFT_AWS_MAP_SKIPPED")
        self.assertEqual(findings[0].location.path, "t.yaml")

    @patch("hefesto.analyzers.cloud.drift.aws_sg.AwsClient")
    def test_drift_identical(self, mock_client_cls):
        # Case 1: Identical - No drift
        mock_instance = mock_client_cls.return_value

        template = {
            "Resources": {
                "TestSG": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {
                        "SecurityGroupIngress": [
                            {
                                "IpProtocol": "tcp",
                                "FromPort": 80,
                                "ToPort": 80,
                                "CidrIp": "10.0.0.0/8",
                            }
                        ]
                    },
                }
            }
        }

        mock_instance.get_security_groups.return_value = [
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

        findings = self.detector.detect_drift(template, self.context)
        self.assertEqual(len(findings), 0)

    @patch("hefesto.analyzers.cloud.drift.aws_sg.AwsClient")
    def test_drift_missing_rule(self, mock_client_cls):
        # Case 2: Missing rule in Cloud
        mock_instance = mock_client_cls.return_value

        template = {
            "Resources": {
                "TestSG": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {
                        "SecurityGroupIngress": [
                            {
                                "IpProtocol": "tcp",
                                "FromPort": 22,
                                "ToPort": 22,
                                "CidrIp": "10.0.0.0/8",
                            }
                        ]
                    },
                }
            }
        }

        mock_instance.get_security_groups.return_value = [
            {"GroupId": "sg-12345", "IpPermissions": []}
        ]

        findings = self.detector.detect_drift(template, self.context)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "DRIFT_AWS_SG_MISSING")
        self.assertEqual(findings[0].format, "cloud_drift")
        self.assertEqual(findings[0].location.path, "test_template.yaml")

    @patch("hefesto.analyzers.cloud.drift.aws_sg.AwsClient")
    def test_drift_unexpected_critical(self, mock_client_cls):
        # Case 3: Unexpected Public Rule -> CRITICAL
        mock_instance = mock_client_cls.return_value

        template = {
            "Resources": {
                "TestSG": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {"SecurityGroupIngress": []},
                }
            }
        }

        # Actual: Open port 22 to 0.0.0.0/0
        mock_instance.get_security_groups.return_value = [
            {
                "GroupId": "sg-12345",
                "IpPermissions": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    }
                ],
            }
        ]

        findings = self.detector.detect_drift(template, self.context)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "DRIFT_AWS_SG_UNEXPECTED")
        self.assertEqual(findings[0].severity, "CRITICAL")

    @patch("hefesto.analyzers.cloud.drift.aws_sg.AwsClient")
    def test_drift_unexpected_high(self, mock_client_cls):
        # Case 4: Unexpected Internal Rule -> HIGH
        mock_instance = mock_client_cls.return_value

        template = {
            "Resources": {
                "TestSG": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {"SecurityGroupIngress": []},
                }
            }
        }

        # Actual: Port 80 to 10.0.0.0/8
        mock_instance.get_security_groups.return_value = [
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

        findings = self.detector.detect_drift(template, self.context)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule_id, "DRIFT_AWS_SG_UNEXPECTED")
        self.assertEqual(findings[0].severity, "HIGH")

    def test_drift_partial_intrinsic(self):
        # Case 5: Intrinsic function -> PARTIAL
        context = DriftContext(
            region="us-east-1",
            template_path="intrinsic.yaml",
            resource_map={"TestSG": "sg-1"},
            credentials=MagicMock(),
        )
        template = {
            "Resources": {
                "TestSG": {
                    "Type": "AWS::EC2::SecurityGroup",
                    "Properties": {
                        "SecurityGroupIngress": [
                            {
                                "IpProtocol": "tcp",
                                "FromPort": 80,
                                "ToPort": 80,
                                "CidrIp": {"Ref": "MyParam"},
                            }
                        ]
                    },
                }
            }
        }

        findings = self.detector.detect_drift(template, context)

        ids = [f.rule_id for f in findings]
        self.assertIn("DRIFT_AWS_SG_PARTIAL", ids)
        self.assertEqual(findings[0].location.path, "intrinsic.yaml")
