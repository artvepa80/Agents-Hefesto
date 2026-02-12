from typing import Any, Dict, List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = None  # type: ignore


class AwsClient:
    """
    Wrapper for AWS SDK (boto3) to facilitate mocking and unified error handling.
    """

    def __init__(self, region: str, credentials: Optional[Any] = None):
        self.region = region
        self.credentials = credentials
        self._ec2 = None

    def _get_session(self):
        if self.credentials:
            return self.credentials
        if boto3:
            return boto3.Session(region_name=self.region)
        return None

    def get_security_groups(
        self,
        group_ids: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch Security Groups by ID or Filters.
        """
        if not boto3:
            return []

        session = self._get_session()
        if not session:
            return []

        try:
            ec2 = session.client("ec2")
            if group_ids:
                return list(ec2.describe_security_groups(GroupIds=group_ids).get("SecurityGroups", []))
            elif filters:
                return list(ec2.describe_security_groups(Filters=filters).get("SecurityGroups", []))
            else:
                return []
        except ClientError:
            # TODO: In production, integrate with hefesto.core.logger
            # logging.getLogger(__name__).warning("AWS ClientError: %s", e)
            return []
        except Exception:
            # logging.getLogger(__name__).error("Unexpected error fetching SGs")
            return []
