# Reproduction guide

Written for someone who has never seen this project, starting from an empty
folder. There are two paths.

**Path A, the offline path.** No AWS account, no API key, no internet after the
clone. Reproduces every headline number exactly. This is the path a judge should
take, and it is the one this project is built around.

**Path B, the live path.** Re-records the model responses against your own AWS
Bedrock account or your own Anthropic key. Only needed if you want to prove the
recordings were not hand written.

---

## What you need

| Item | Value |
|---|---|
| Operating system | Any. Built and evaluated on Windows 11, tested on Linux |
| Python | 3.9 or newer. Built on 3.14.3, also run on 3.11 |
| Disk | Under 5 MB |
| Internet | Path A: only to clone. Path B: yes |
| Credentials | Path A: none. Path B: an AWS profile with Bedrock model access, or an Anthropic API key |

Everything except the model call uses the Python standard library only. That
includes the plan reader, all the security checks, the blast radius analysis, the
verifier, the scanner rung, the scorer and all 190 tests.

---

## Path A, offline, no credentials

### 1. Get the code

```
git clone https://github.com/legendonthisone/cloudfix.git
cd cloudfix
```

### 2. Run the tests

```
python run.py test
```

Expected: `Ran 190 tests`, `OK`. Takes about three seconds. No network, no
credentials, nothing installed. If this passes, the deterministic half of the
project is verified on your machine.

Eighteen of those tests are in `tests/test_claims.py`, and they do something
worth knowing about: they read `results/*.json` and assert that every figure
printed in `README.md` is the figure those files actually contain. If a rerun
moves a number, the suite fails until the writeup is corrected. It is the link
between the claims and the evidence, made mechanical rather than promised.

### 3. Run the existing way, the scanner rung

```
python run.py eval --system scanner
```

Expected: a line per case and `verdict accuracy: 62%`. This rung uses no model at
all, so it costs nothing and needs nothing installed. It is the checkov and tfsec
style comparison, and it is deliberately given CloudFix's own action aware checks
rather than a text scan, which makes it a stronger opponent than the real thing.

### 4. Reproduce the headline comparison

```
pip install -r requirements.txt
python run.py eval --system both --mode replay
```

`--mode replay` reads the recorded model responses in `data/model_cache` and
never calls an API. `pip install` is needed only because the code imports the
client library before it discovers it does not have to call it.

Expected: the baseline, scanner and CloudFix columns of the table in
`README.md`, reproduced exactly.

### 5. Reproduce the full ablation ladder

```
python run.py eval --system ladder --mode replay
```

Expected: the six rung table in `IMPROVEMENT_CHANGELOG.md`, reproduced exactly.

### 6. Re-score the result against labels you do not accept

```
python run.py sensitivity
```

The evaluation's ground truth is hand written, so the fair question is how much
of the result depends on two labels a reviewer might reject. This re-scores the
verdicts that were actually produced against four different labellings and prints
the table in `README.md`. It calls no model and re-runs nothing.

### 7. Review a single plan, which is what the tool is for

```
python run.py scan   --plan data/plans/c07_prod_db_replace_clean.json
python run.py review --plan data/plans/c07_prod_db_replace_clean.json --mode replay
```

The first is how this is done today. The second is CloudFix. Run them back to
back, and the difference between the two outputs is the whole project.

---

## Path B, live, with your own credentials

Recording the run again costs a few dollars and about eight minutes. Nothing in
Path A depends on it.

### Using AWS Bedrock

```
pip install -r requirements.txt
pip install "anthropic[bedrock]==1.2.0"

# PowerShell
$env:AWS_PROFILE = "your-profile"
$env:AWS_REGION  = "us-east-1"
$env:CLOUDFIX_PROVIDER = "bedrock"

# bash
export AWS_PROFILE=your-profile
export AWS_REGION=us-east-1
export CLOUDFIX_PROVIDER=bedrock

python run.py check
```

`check` makes one tiny call and prints `reply: ready`. Your AWS account needs
Anthropic model access enabled in the Bedrock console. If it is not, the error
message names the console page to open.

### Using an Anthropic API key instead

```
pip install -r requirements.txt

# PowerShell
$env:ANTHROPIC_API_KEY = "your-key"
$env:CLOUDFIX_PROVIDER = "anthropic"

python run.py check
```

### Then record the run

```
python run.py eval --system ladder --mode live
```

This overwrites nothing. Responses are keyed by a hash of the exact prompt, so a
new recording lands beside the old one and `--mode replay` keeps working.

---

## What each command writes

| Path | What is in it |
|---|---|
| `results/<system>_results.json` | Every metric and every per case score for that rung |
| `results/reviews/<system>/<case>.md` | The review a user would actually read |
| `results/consistency.json` | The repeat run study |
| `trajectories/<system>/<case>.json` | Every step: tool calls, tool responses, the model's decision, the verification verdict, retries, repairs |
| `data/model_cache/*.json` | One recorded model response each, keyed by prompt hash |

Each trajectory carries, in order: the ground truth, the deterministic tool calls
and what they returned, the **exact system prompt and user prompt** sent to the
model, its decision, the verifier's numbered feedback, any repair, the final
verdict and the human checkpoint. It reads end to end without opening any other
file.

---

## Runtime and cost

| Command | Time | Cost |
|---|---|---|
| `run.py test` | about 3 seconds | free |
| `run.py eval --system scanner` | under 1 second | free, no model |
| `run.py eval --system both --mode replay` | a few seconds | free, no model call |
| `run.py eval --system ladder --mode replay` | a few seconds | free, no model call |
| `run.py sensitivity` | instant | free, no model |
| `tools/audit.py` | instant | free, 42 checks against the brief |
| `run.py eval --system ladder --mode live` | about 8 minutes | 86 cents for the recorded run, 81 model calls across five systems |

---

## Turning your own Terraform into an input

CloudFix takes the JSON form of a plan, which is Terraform's own output format.

```
terraform plan -out=tfplan
terraform show -json tfplan > plan.json
python run.py review --plan plan.json
```

The exit code is 0 for SAFE, 1 for REQUIRES HUMAN REVIEW and 2 for DO NOT APPLY,
so it drops into a pipeline as a gate. It still only recommends. Applying the
change stays a human decision.

---

## If something does not work

| Symptom | Cause and fix |
|---|---|
| `No recorded response for this prompt ... and mode is replay` | The prompt changed, so the recording no longer matches. Run that case with `--mode live`, or check out the commit the recordings were made from |
| Bedrock mentions a use case details form | Amazon requires that form per AWS account before it serves Anthropic models. The error prints the console URL. Nothing in the code needs changing |
| `The API rejected the model name` | Set `CLOUDFIX_MODEL` to a model your account can reach |
| `ANTHROPIC_API_KEY is not set` | Set the key, or use `--provider bedrock`, or use `--mode replay` and skip credentials entirely |
