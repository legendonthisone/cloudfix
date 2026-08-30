"""
One tiny model call, to prove the credentials work before anything expensive runs.

  python run.py check
  python run.py check --provider bedrock --region us-east-1
"""

import argparse

from .model import ModelClient, ModelError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check that the model backend answers")
    parser.add_argument("--provider", choices=("bedrock", "anthropic"), default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--region", default=None)
    args = parser.parse_args(argv)

    client = ModelClient(
        model=args.model, mode="live", provider=args.provider, region=args.region
    )
    print("provider: %s" % client.provider)
    print("model:    %s" % client.model)
    try:
        response = client.complete(
            system="Answer with one word.",
            user="Reply with the single word: ready",
            max_tokens=16,
        )
    except ModelError as exc:
        print("\nNot working yet.\n")
        print(exc)
        return 1
    print("reply:    %s" % response.text.strip())
    print("tokens:   %d in, %d out" % (response.input_tokens, response.output_tokens))
    print("\nGood. The evaluation can run live.")
    return 0
