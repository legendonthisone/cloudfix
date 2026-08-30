"""
Where the model actually comes from.

Two backends, one interface. Both expose the same .messages.create call, so
nothing above this file cares which one is in use.

  bedrock    your own AWS account, using the credentials the AWS CLI already has
  anthropic  an Anthropic API key in ANTHROPIC_API_KEY

Pick with CLOUDFIX_PROVIDER, or the --provider flag. This choice does not affect
reproducibility at all: every response is recorded to data/model_cache, and a
judge replays those recordings with no key and no AWS account.
"""

import os

DEFAULT_PROVIDER = os.environ.get("CLOUDFIX_PROVIDER", "bedrock").strip().lower()
DEFAULT_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Sensible default model per backend. Bedrock uses its own id format.
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-5",
    "bedrock": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
}


class ProviderError(RuntimeError):
    pass


def default_model(provider: str) -> str:
    explicit = os.environ.get("CLOUDFIX_MODEL", "").strip()
    if explicit:
        return explicit
    return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["bedrock"])


def build_client(provider: str = None, region: str = None):
    """Return an SDK client exposing .messages.create, or explain what is missing."""
    provider = (provider or DEFAULT_PROVIDER).strip().lower()

    if provider not in ("anthropic", "bedrock"):
        raise ProviderError("Unknown provider %r. Use bedrock or anthropic." % provider)

    try:
        import anthropic  # noqa: F401
    except ImportError as exc:
        raise ProviderError(
            "The anthropic package is not installed. Run: pip install -r requirements.txt"
        ) from exc

    if provider == "bedrock":
        try:
            from anthropic import AnthropicBedrock
        except ImportError as exc:
            raise ProviderError(
                "Bedrock support is missing from the installed SDK. Run: "
                'pip install "anthropic[bedrock]"'
            ) from exc
        try:
            return AnthropicBedrock(aws_region=region or DEFAULT_REGION)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                "Could not start the Bedrock client in region %s. Check that the AWS "
                "CLI is configured and that Claude model access is enabled in that "
                "region. Original error: %s" % (region or DEFAULT_REGION, exc)
            ) from exc

    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ProviderError(
            "ANTHROPIC_API_KEY is not set in this terminal. Set it with:\n"
            '  $env:ANTHROPIC_API_KEY = "your-key-here"\n'
            "Or switch to an AWS account with --provider bedrock.\n"
            "Or run with --mode replay to use the recorded responses and no key at all."
        )
    return anthropic.Anthropic(api_key=api_key)
