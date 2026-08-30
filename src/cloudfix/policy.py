"""
The verdict policy.

Three verdicts, and a written rule for each one. This file exists so that no
label anywhere in this project is a matter of taste. The same text is shown to
the model, used to label the evaluation cases, and published in
docs/VERDICT_POLICY.md for a judge to argue with.

If you disagree with a ground truth label, the argument is with a numbered rule
below, not with somebody's feel for infrastructure. That is deliberate. A metric
built on unwritten judgement is not a metric.
"""

SAFE = "SAFE"
REVIEW = "REQUIRES HUMAN REVIEW"
BLOCK = "DO NOT APPLY"

VERDICTS = (SAFE, REVIEW, BLOCK)

# Ordered worst first, so "at least as severe as" is a comparison.
SEVERITY_RANK = {BLOCK: 0, REVIEW: 1, SAFE: 2}


POLICY_TEXT = """CloudFix verdict policy, version 1.

A plan gets exactly one verdict. Work down the list and stop at the first match,
so DO NOT APPLY beats REQUIRES HUMAN REVIEW, which beats SAFE.

DO NOT APPLY. The change, if applied as written, does one of these:
  D1  Makes data or an administrative interface reachable from the public
      internet without authentication. This covers public object access on a
      bucket holding data, a database with a public endpoint, and a remote
      administration or database port open to 0.0.0.0/0. A bucket that is
      configured as a static website is not this rule, it is R2.
  D2  Grants unbounded privilege, meaning every action on every resource.
  D3  Removes encryption from data that is encrypted today, or provisions
      unencrypted storage in production.
  D4  Destroys or replaces a production resource that holds data, or removes a
      guard that protects one, such as turning off deletion protection or
      skipping the final snapshot.
  D5  Grants a container workload host level privilege in production.

REQUIRES HUMAN REVIEW. None of the above, and one of these:
  R1  A permission that is broad but bounded, such as every action in one
      service restricted to named resources.
  R2  Public exposure that may well be intended, such as a static website bucket
      or a load balancer on 80 and 443, where the plan alone cannot confirm the
      intent.
  R3  Destroys or replaces a production resource that holds no data, so the cost
      is downtime rather than data loss.
  R4  Destroys or replaces a resource that holds data outside production.
  R5  A security finding that was already true before this change and is not
      introduced by it.
  R6  A production networking change that other resources in the plan depend on.

SAFE. None of the above applies. The change adds no public exposure, grants no
new privilege, weakens no encryption, and destroys nothing that matters.

Two notes that decide most of the hard cases:

  The action matters as much as the configuration. A plan that REMOVES an open
  SSH rule contains the text 0.0.0.0/0 and is safe. Read what will exist after
  the change, not what appears in the file.

  A risk that was already there is still a risk, but it is not this deploy's
  fault. Say so, and let the human decide, rather than blocking a change that
  did not cause it."""


HUMAN_CHECKPOINT_TEXT = (
    "CloudFix never applies anything. It reads a plan and recommends. "
    "Applying the change, or refusing to, is the human's decision and always "
    "happens outside this tool."
)


def normalise(verdict: str) -> str:
    """Map whatever came back onto one of the three verdicts, or return ''."""
    if not verdict:
        return ""
    text = str(verdict).strip().upper().replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    if text in ("SAFE", "OK", "NO ISSUES"):
        return SAFE
    if text in ("DO NOT APPLY", "DONT APPLY", "DO NOT DEPLOY", "BLOCK", "BLOCKED"):
        return BLOCK
    if text in (
        "REQUIRES HUMAN REVIEW",
        "REQUIRE HUMAN REVIEW",
        "HUMAN REVIEW",
        "NEEDS HUMAN REVIEW",
        "REVIEW",
        "REQUIRES REVIEW",
    ):
        return REVIEW
    # Be generous about wrapping words, strict about which verdict it is.
    if "DO NOT" in text:
        return BLOCK
    if "REVIEW" in text:
        return REVIEW
    if "SAFE" in text:
        return SAFE
    return ""


def at_least_as_severe(verdict: str, floor: str) -> bool:
    return SEVERITY_RANK.get(verdict, 9) <= SEVERITY_RANK.get(floor, 9)
