"""
CloudFix: read a Terraform plan before it is applied, and say whether it is safe.

Deterministic code finds the facts. A model does the judging. Code then checks
the judging against the facts. CloudFix never applies anything.
"""

__version__ = "1.0.0"
