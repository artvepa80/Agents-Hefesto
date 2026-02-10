from .arm import ANALYZERS as ARM_ANALYZERS
from .cloudformation import ANALYZERS as CLOUDFORMATION_ANALYZERS
from .finding_schema import CloudFinding, CloudLocation
from .helm import ANALYZERS as HELM_ANALYZERS
from .serverless import ANALYZERS as SERVERLESS_ANALYZERS

# List of all available cloud analyzers
ALL_CLOUD_ANALYZERS = (
    CLOUDFORMATION_ANALYZERS + HELM_ANALYZERS + ARM_ANALYZERS + SERVERLESS_ANALYZERS
)

__all__ = ["ALL_CLOUD_ANALYZERS", "CloudFinding", "CloudLocation"]
