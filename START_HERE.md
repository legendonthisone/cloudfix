# Start here, Ayobami

This is the working note for you, not for a judge. The judge reads `README.md`
and `docs/REPRODUCTION_GUIDE.md`.

## What CloudFix is, in one breath

It reads a Terraform plan before it is applied and says SAFE, REQUIRES HUMAN
REVIEW, or DO NOT APPLY, with the exact line of the plan that proves each reason.

## The one sentence that wins the comparison

checkov and tfsec are security scanners. They read configuration. Neither of them
asks what the plan is about to destroy. So a plan that replaces the production
database and skips the final snapshot, with everything else configured perfectly,
comes back clean from both, and clean reads as ship it. That is case
`c07_prod_db_replace_clean`, and it is your demo moment.

## What you need to run, in order

Open PowerShell in this folder.

**Step 1. Install the client. Once.**

```
pip install -r requirements.txt
pip install "anthropic[bedrock]==1.2.0"
```

**Step 2. Prove the deterministic half works. Free, no credentials, 2 seconds.**

```
python run.py test
python run.py eval --system scanner
```

190 tests should pass and the scanner should score 62 percent. If that happens,
everything that does not need a model is already working.

**Step 3. Point it at Bedrock and prove the credentials work. Costs about a
tenth of a cent.**

```
$env:AWS_PROFILE = "LegendAdmin"
$env:AWS_REGION  = "us-east-1"
$env:CLOUDFIX_PROVIDER = "bedrock"
python run.py check
```

You want to see `reply: ready`. If Bedrock complains about a use case form, the
error message tells you exactly which console page to open. That is not a bug in
the code.

**Step 4. The full ladder. This is the run that produces every number in the
submission. Expect roughly 5 to 8 minutes and about 2 to 3 dollars.**

```
python run.py eval --system ladder --mode auto
```

Every response is recorded to `data/model_cache`, so this is the only time it
costs anything. After this, `--mode replay` reproduces the same numbers forever,
free, with no credentials, which is what protects the reproducibility gate.

**Step 5. The consistency study. Another 2 dollars or so.**

```
python run.py eval --system both --samples 3
```

This reviews every plan three times to show whether the answer moves between
runs. Sample 1 is already recorded, so only samples 2 and 3 cost anything.

**Step 6. Tell me it is done.** I read the results files and write the README,
the improvement changelog and the reproduction guide from the real numbers. I
will not write a single figure that did not come out of a command in this repo.

## If something breaks

Copy the error to me exactly. Do not fix it by hand, because the reproduction
guide has to describe what actually happened.

## The demo, when we get there

```
python run.py scan   --plan data/plans/c07_prod_db_replace_clean.json
python run.py review --plan data/plans/c07_prod_db_replace_clean.json --mode replay
```

The first is how the job is done today: no findings, verdict SAFE. The second is
CloudFix: DO NOT APPLY, with the skipped final snapshot quoted from the plan.
Run those two back to back on camera and the whole project explains itself.
