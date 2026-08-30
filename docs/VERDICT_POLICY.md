# CloudFix verdict policy

This is the rulebook. It is the same text the agent is given, the same text the
baseline is given, and the same text used to label every ground truth case in
`data/cases.json`. A test asserts that this document and the copy in
`src/cloudfix/policy.py` are identical, so they cannot drift apart.

Why it exists: an evaluation whose labels come from somebody's feel for
infrastructure is not an evaluation. If you think a label in this project is
wrong, the argument is with a numbered rule below.

---

CloudFix verdict policy, version 1.

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
  did not cause it.

---

## What CloudFix will never do

CloudFix does not apply changes, and it has no credentials that would let it. It
reads a plan file and writes a recommendation. Approving or refusing a deploy is
a human decision, taken outside this tool, every time.
