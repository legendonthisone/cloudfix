# CloudFix

An agent that reads a Terraform plan before it is applied and says **SAFE**,
**REQUIRES HUMAN REVIEW** or **DO NOT APPLY**, with the exact line of the plan
that proves every reason it gives.

**The thesis in one line: code finds the facts, the model does the judging, and
code then checks the judging against the facts.**

CloudFix never applies anything. It holds no credential that could change
infrastructure. It reads a file and writes a recommendation, and a human decides.

| Verdict accuracy over 16 hand labelled Terraform plans | |
|---|---|
| A deterministic scanner baseline, the shape of the workflow teams run today | **10/16** |
| One prompt with the full policy and the whole plan, no tools | **14/16** |
| CloudFix | **16/16** |

0/16 dangerous misses, 0/16 over blocks, and 0 of 30 cited evidence pointers
that fail to resolve in the plan they came from. Every number on this page came out of
`results/`, and a judge with no AWS account reproduces all of them offline.

**What this measures, stated before the numbers rather than after.** These are
sixteen cases against a policy published in this repository. The result is
conformance to that written policy, not proof that CloudFix makes the decision
every cloud engineer would make. The policy was written before any code and
every label cites a numbered rule, which is what makes the labels arguable
instead of arbitrary, but the policy and the cases are mine. Sixteen is a small
number and it is printed as a fraction everywhere for that reason.

Two of the sixteen labels are genuinely arguable, and reviewers argued with both.
[**How much of this depends on labels you might reject**](#how-much-of-this-depends-on-labels-you-might-reject)
publishes what the result becomes if you take their side: accept both counter
arguments and the unaided prompt beats CloudFix 16/16 to 14/16. The comparison
against the scanner does not move, and CloudFix records 0/16 dangerous misses
under every labelling. Read that section before quoting the 16/16 above,
including if you are quoting it back at me.

---

## Who has this problem

DevOps engineers, cloud engineers and solutions architects. The person who has to
approve an infrastructure change before it goes live.

This is my own lane. I hold the AWS Solutions Architect Associate certification,
I have built and deployed an agent on AWS AgentCore with the Strands SDK, and I
am in the BeSA agentic AI cohort. The reviewer in this story is me.

---

## What bottleneck makes it worth solving

A Terraform plan is the preview of what a change will actually do: what gets
created, updated, replaced or destroyed. A real one spans IAM, networking,
databases, compute and storage in a single wall of text. Working out what matters
is slow, and it is inconsistent in a way nobody notices, because a review that
missed something produces exactly the same artefact as a review that did not: the
word approved.

There are three ways this is handled today. Each fails differently, and this
project measures all three.

### By eye

Slower at 6pm on a Friday than at 10am on a Tuesday, and nothing in the process
records which one you got.

### With a deterministic scanner: 10/16, and four dangerous misses

The second baseline is a deterministic scanner plus the severity gate a CI
pipeline usually wraps around one. It is not checkov, and this project does not
claim to beat checkov. It is the *shape* of that workflow: run policy checks over
the change, map the severities to a pass or fail, and let the build decide.

It is deliberately strengthened. It was given CloudFix's own action aware checks
rather than a text scan, so it reads the after state, and it was given a
configuration policy for deletion protection because checkov ships one. The
question it is there to answer is not "is checkov good", it is **are
deterministic findings on their own enough to decide whether a change should
ship**.

Take this plan:

```
# aws_db_instance.orders must be replaced
-/+ resource "aws_db_instance" "orders" {
      ~ engine_version       = "14.9" -> "15.4"     # forces replacement
      ~ deletion_protection  = true  -> false
      ~ skip_final_snapshot  = false -> true
        storage_encrypted    = true                 # encrypted, correct
        publicly_accessible  = false                # private, correct
    }
```

A real scanner is not blind here, and an earlier draft of this README said it
was. checkov ships
[`RDSDeletionProtection.py`](https://github.com/bridgecrewio/checkov/blob/main/checkov/terraform/checks/resource/aws/RDSDeletionProtection.py),
a configuration policy for exactly the flag this plan turns off, so it flags one
line. The scanner rung in this project was given the same check, because a
baseline weaker than the real tool proves nothing. It reports two medium findings
on this plan and asks for a human.

The ground truth is DO NOT APPLY, and the gap between those two answers is the
whole project. What a configuration policy reports is that a checkbox is off.
What it does not compose is the sentence that decides the deploy: this plan
**replaces** the production orders database, and the final snapshot is skipped,
so the data stops existing and there is nothing to restore. A finding and a
consequence are not the same thing, and only one of them is a decision.

Three other cases are further out of reach, because nothing in them is configured
badly at all. `c08` replaces a production NAT gateway that two routes depend on,
`c09` replaces the production API server, `c14` replaces the production load
balancer. No check fires on any of them, so no severity gate, however strict, can
return anything but SAFE. All three are wrong, and
`tests/test_scanner_and_scoring.py` asserts it.

**Two things worth saying rather than hiding**, because a judge who knows these
tools will know them:

- checkov can scan plan JSON, and it exposes `__change_actions__` to *custom*
  policies, so a team could hand write destructive action rules. That is
  precisely the work this project is doing, and the honest framing is not "the
  category cannot do this" but "the category does not ship it, and composing
  findings into a deployment verdict is a different job from listing them".
- On a plan that only deletes resources, checkov currently runs no checks at all
  ([open issue #5587](https://github.com/bridgecrewio/checkov/issues/5587)).

The scanner baseline scores **10/16**, with **four dangerous misses**. The answer
to the question it was built to ask is no: deterministic findings alone do not
decide a deploy, because the decision depends on what the change does, where it
does it, and whether anyone meant it.

### By pointing a language model at it: 14/16, and two dangerous misses

That is the obvious fix and it is the baseline here. It is deliberately generous:
the same role description, the same verdict policy in full, the same required
output shape and the whole plan JSON. The only thing it does not get is a tool.

It is good. It correctly blocks the database replacement that the scanner waves
through, and every citation it gave resolved in the plan. It also failed twice,
both times in the same direction, and both times on judgement rather than on
facts:

- `c12_dev_static_website`, a public bucket that is meant to be public. It said
  SAFE. The correct answer is a human decision, because the plan alone cannot
  confirm that a public bucket is intentional.
- `c15_preexisting_open_port`, a tag change on a host that has had SSH open to
  the world for years. It said SAFE. The exposure is real and standing, and
  saying safe about it is how a risk stays open for another two years.

On the five hard cases it scores **3/5**. CloudFix scores **5/5**.

---

## Why solving it is valuable

Not because a model can read Terraform. It can. Because of what happens either
side of that.

**The failures that remain are the expensive ones.** Both baselines fail toward
safe. The scanner calls three production resource replacements SAFE and downgrades
a database destruction to a review; the unaided model calls a standing internet
exposure SAFE. In this measurement CloudFix has zero dangerous misses out of
sixteen.

**Over blocking is the other half, and it is the half that gets tools deleted.**
The scanner blocks two plans it should not have, including a deploy that only
adds tags. A tool that blocks a tag edit teaches a team to bypass it, and once
they bypass it the real finding goes past too. CloudFix over blocks nothing.

**Every claim is checkable by the person who has to sign.** Each reason names a
pointer into the plan, and code resolved that pointer before the reviewer saw it.
Across 30 cited pointers, zero failed to resolve. "Trust me" is not in the output.

**It costs 13% more than the unaided prompt.** $0.01079 a review against
$0.00954, about a tenth of a cent, for two more correct verdicts out of sixteen
and both dangerous misses removed. The whole recorded ladder, 81 model calls
across the five rungs that use a model, cost **86 cents**. The three sample
repeat study added 64 calls on top.

---

## What the agent does

One agent, six steps, and only two of them use a model.

| Step | Kind | What happens |
|---|---|---|
| 1. Parse | tool | Read the plan JSON into resources and, crucially, into actions: create, update, replace, destroy |
| 2. Check | tool | Seven deterministic check functions covering sixteen finding types, each returning a pointer to the line that proves it |
| 3. Blast radius | tool | What is destroyed, whether it holds data, whether it is production, what else depends on it |
| 4. Assess | model | Which facts matter here, whether an exposure looks deliberate, and the verdict, with a citation for every claim |
| 5. Verify | tool | Resolve every citation against the plan itself. Five rules, no model involved |
| 6. Repair | model | Only when verification failed, and only against a numbered list of what did not hold up |

Step 3 is computed on every run and deliberately **not** put in the model's
prompt. That is not an accident, it is a measured result, and it is the most
interesting thing this project found. See the ladder below.

### The verifier

A language model asked "is your answer right?" says yes. So nothing in the
verifier asks it anything. It resolves each cited pointer against the plan JSON
and throws away any claim that cannot be proved.

| Rule | What it enforces |
|---|---|
| V1 | Every reason must cite a pointer that resolves, to the value it claims |
| V2 | A SAFE verdict may not walk past a critical finding or a severe blast radius. Dismiss it in writing, or the verdict is not SAFE |
| V3 | A DO NOT APPLY verdict must give at least one reason |
| V4 | You may not dismiss a finding that never fired |
| V5 | A risk this change did not introduce may not be dismissed into SAFE. It goes to a human |

When a rule fails, the decision goes back to the model with a numbered list of
exactly what is wrong. The model is allowed to be wrong. It is not allowed to be
wrong and unchallenged.

V5 was written after watching the loop fail. That story is in
`IMPROVEMENT_CHANGELOG.md` and it is the best evidence in this repository.

### What CloudFix is not

It is not a replacement for a security scanner, and building one would have been
a waste of a weekend. Scanners are good at what they do and CloudFix uses that
work rather than competing with it: the deterministic checks in this repository
are the same category of thing, and step 2 is where they run.

What sits on top of them is the part that did not exist. A scanner produces a
list of findings. Somebody then has to read that list next to the change it came
from and answer a different question: given everything this plan is about to do,
should it ship, and can I show why. That interpretation is the job being
automated here, and the ladder below measures whether an agent does it better
than a severity gate or an unaided prompt.

### Is this an agent, or a pipeline with a model call in it

A fair question, and the answer is that the distinction only matters if it
changes what you can build. Three of the six steps are deterministic code, and I
would rather be accused of having too little model in the loop than too much.

What makes it more than a pipeline is that step 4 is not a transformation, it is
a decision that can go several ways on the same inputs, and steps 5 and 6 are a
loop: the output is checked, and when the check fails the model is sent back with
the specific defect and has to produce a different answer. The ladder measures
that loop directly. Rung 4 to rung 5 is the difference between a pipeline that
emits whatever the model said and a system that argues with it.

### Why the security checks are code and not prompt

Deterministic means the same input gives the same output every time, like a
calculator. The checks in `src/cloudfix/checks.py` are ordinary Python
functions, which is what makes the primary metric objective and the result
reproducible.

It also fixes a failure pure scanning has. Two rules every check follows:

1. **Read the after state, not the file.** A plan that removes an open SSH rule
   still contains `0.0.0.0/0` in its text, and a tool that greps flags it. The
   after state is what will exist once the change is applied, so a rule being
   closed produces no finding. That is `c11_closing_ssh_rule`, ground truth SAFE.
2. **Say whether this change introduced the problem.** A risk that was already
   there is still a risk, but it is not this deploy's fault, and blocking a tag
   edit does not close a port that has been open for two years. Those findings
   are reported one severity lower and carry `introduced_by_change: false`. That
   is `c15_preexisting_open_port`, and it is where V5 earns its place.

---

## What the output actually looks like

Verbatim from `results/reviews/agent/c07_prod_db_replace_clean.md`, the review of
the plan the scanner baseline sends to a human. Reproduce it with
`python run.py review --plan data/plans/c07_prod_db_replace_clean.json --mode replay`.

```markdown
## Verdict: DO NOT APPLY

DO NOT APPLY. Applying this as written causes harm that is hard or impossible to undo.

This plan replaces the production orders database, which destroys all data in it. The change also disables deletion protection and skips the final snapshot, removing both guards that would normally prevent data loss during a replacement.

Policy rules that fired: D4

## What is changing

0 to create, 1 to update, 2 to replace, 0 to destroy. Worst blast radius: **severe**.

- `aws_db_instance.orders` will be **replaced** (aws_db_instance, production). aws_db_instance holds data. A replace destroys the data that is in it today. skip_final_snapshot is true, so Terraform will not take a last backup on the way out. Once this runs the data is gone with nothing to restore. This resource is tagged or named as production. 2 other resources in this plan reference it, so the effect does not stop at this resource: aws_ecs_task_definition.orders_api, aws_ssm_parameter.orders_endpoint. deletion_protection is being turned off. That guard exists to stop exactly the kind of deletion this change makes possible.

## Why

1. the production database orders-prod is being replaced, which destroys the data in it _(rule D4)_
   - evidence: `resource_changes[0].change.actions` = `["delete", "create"]`  [verified against the plan]
2. deletion protection is being turned off on this production database _(rule D4)_
   - evidence: `resource_changes[0].change.after.deletion_protection` = `false`  [verified against the plan]
3. skip_final_snapshot is being set to true, preventing a backup on destroy _(rule D4)_
   - evidence: `resource_changes[0].change.after.skip_final_snapshot` = `true`  [verified against the plan]

## Raw findings from the deterministic checks

- **MEDIUM** `DELETION_PROTECTION_DISABLED` on `aws_db_instance.orders` (replace)
  - `resource_changes[0].change.after.deletion_protection` = `false`
- **MEDIUM** `FINAL_SNAPSHOT_SKIPPED` on `aws_db_instance.orders` (replace)
  - `resource_changes[0].change.after.skip_final_snapshot` = `true`

## Human approval checkpoint

CloudFix never applies anything. It reads a plan and recommends. Applying the change, or refusing to, is the human's decision and always happens outside this tool.
```

Read the last two sections against each other. The deterministic checks found two
medium findings: a flag off, a snapshot skipped. The verdict is DO NOT APPLY, and
the reason is a sentence neither finding contains: the database is being
**replaced**, so the data those two flags were protecting stops existing. The
findings are the input. The decision is the product.

Every review for every system is in `results/reviews/`.

---

## How it was measured

Sixteen synthetic Terraform plans in `data/plans/`, each labelled by hand before
any system ran against it, and each label tied to a numbered rule in
`docs/VERDICT_POLICY.md`. That document is the same text the agent is given, the
same text the baseline is given, and the same text used to write the labels. A
test asserts the published copy and the copy in the code are identical, so they
cannot drift.

If you think a label here is wrong, the argument is with a numbered rule, not
with somebody's feel for infrastructure. An evaluation whose labels come from
taste is not an evaluation.

The labels are tested like code: every plan loads, every rule a case names exists
in the policy, every case naming a critical resource names one really in its
plan, DO NOT APPLY cases cite only D rules and REQUIRES HUMAN REVIEW cases cite
only R rules.

Five of the sixteen are deliberately hard, and on three of them the obvious
answer is wrong:

| Case | Why it is hard |
|---|---|
| `c07_prod_db_replace_clean` | Perfect security configuration, destroys the production database |
| `c11_closing_ssh_rule` | The plan text contains an open SSH rule, and the change is removing it |
| `c12_dev_static_website` | A public bucket that is supposed to be public |
| `c13_scoped_service_wildcard` | `s3:*` on two named bucket ARNs. Broad, but bounded |
| `c15_preexisting_open_port` | A real problem that this deploy did not cause |

**Primary metric: verdict accuracy.** The share of plans where the verdict
matched ground truth. No partial marks.

**Secondary metrics**, because verdict accuracy alone hides the difference
between the two ways of being wrong:

- **dangerous miss**: judged a plan safer than it is. The failure that costs a
  company its data.
- **over block**: said DO NOT APPLY to a plan that did not deserve it. The
  failure that gets the tool switched off.
- **critical resource named**: did the review name the resource that mattered.
- **citations that do not resolve**: how much of the reasoning is invented.
  Computed by the scorer for every rung, including those that never ran a
  verification pass, so the number is comparable across the whole ladder.

---

## Results

Sixteen cases, same plans and same scorer for every system.
`python run.py eval --system both --mode replay`

| Metric | One prompt, no tools | Scanner baseline | CloudFix |
|---|---|---|---|
| Verdict accuracy (primary) | 14/16 | 10/16 | **16/16** |
| Dangerous misses | 2/16 | 4/16 | **0/16** |
| Over blocked | 0/16 | 2/16 | **0/16** |
| The 5 hard cases | 3/5 | 2/5 | **5/5** |
| Citations that do not resolve | 0/27 | 0/18 | **0/30** |
| Model seconds per review | 5.7 | 0.0 | 5.7 |
| Cost per review (USD) | 0.00954 | 0.00000 | 0.01079 |

One diagnostic, kept out of the table above because its first implementation was
wrong and the changelog says so: **named the resource that mattered**, over the
13 cases that name one. Baseline 11/13, scanner 10/13, CloudFix 13/13. It is a
useful smell test for whether a review found the right thing, and it is not one
of the four metrics that map to the user's problem.

Per case, with wrong verdicts in bold:

| Case | Difficulty | Ground truth | baseline | scanner | CloudFix |
|---|---|---|---|---|---|
| `c01_safe_tagging` | easy | SAFE | SAFE | SAFE | SAFE |
| `c02_public_s3_bucket` | easy | BLOCK | BLOCK | BLOCK | BLOCK |
| `c03_open_ssh_sg` | easy | BLOCK | BLOCK | BLOCK | BLOCK |
| `c04_iam_wildcard_admin` | easy | BLOCK | BLOCK | BLOCK | BLOCK |
| `c05_public_database` | easy | BLOCK | BLOCK | BLOCK | BLOCK |
| `c06_encryption_removed` | medium | BLOCK | BLOCK | BLOCK | BLOCK |
| `c07_prod_db_replace_clean` | hard | BLOCK | BLOCK | **REVIEW** | BLOCK |
| `c08_nat_gateway_replace` | medium | REVIEW | REVIEW | **SAFE** | REVIEW |
| `c09_prod_ec2_replace` | medium | REVIEW | REVIEW | **SAFE** | REVIEW |
| `c10_k8s_privileged` | medium | BLOCK | BLOCK | BLOCK | BLOCK |
| `c11_closing_ssh_rule` | hard | SAFE | SAFE | SAFE | SAFE |
| `c12_dev_static_website` | hard | REVIEW | **SAFE** | **BLOCK** | REVIEW |
| `c13_scoped_service_wildcard` | hard | REVIEW | REVIEW | REVIEW | REVIEW |
| `c14_mixed_prod_change` | medium | REVIEW | REVIEW | **SAFE** | REVIEW |
| `c15_preexisting_open_port` | hard | REVIEW | **SAFE** | **BLOCK** | REVIEW |
| `c16_noop_only` | easy | SAFE | SAFE | SAFE | SAFE |

### Does the same plan get the same answer twice

Every plan reviewed three times over.
`python run.py eval --system both --samples 3`

| System | Verdict accuracy per run | Same verdict every run |
|---|---|---|
| One prompt, no tools | 14/16, 14/16, 14/16 | 16/16 |
| CloudFix | 16/16, 16/16, 16/16 | 16/16 |

Both are stable, which is the expected result at temperature 0 against a pinned
model, and it is worth reporting rather than quietly dropping because the study
did not produce a gap.

The finding underneath it is not comforting. **The unaided prompt is not
unreliable. It is reliably wrong**, on `c12` and `c15`, in the same direction,
every time. That is worse than instability, not better: a wrong answer that
wobbles gets caught the second time somebody runs it. A wrong answer that is
perfectly repeatable never does.

---

## How much of this depends on labels you might reject

The deepest fair criticism of this evaluation is that the cases are mine, the
policy is mine and the scorer is mine, so 16/16 measures conformance to my own
judgement. Adding more of my own cases would not answer that. Publishing what
happens when you refuse my two most arguable labels does.

Both of these were argued against by reviewers reading this repository before
submission, and both arguments are good:

- **`c15_preexisting_open_port`** is labelled REQUIRES HUMAN REVIEW under rule
  R5. The counter argument: a tag only deploy introduces nothing, so the deploy
  is SAFE and the standing SSH exposure is a separate ticket. That is how a lot
  of platform teams actually work.
- **`c12_dev_static_website`** is labelled REQUIRES HUMAN REVIEW under rule R2.
  The counter argument: a bucket tagged development, tagged public and carrying a
  website configuration has already declared its intent, so SAFE needs no human.

Re-scoring the verdicts that were actually produced, against all four labellings.
`python run.py sensitivity`

| Ground truth used | One prompt, no tools | Scanner baseline | CloudFix |
|---|---|---|---|
| As published | 14/16 | 10/16 | **16/16** |
| c15 as SAFE | 15/16 | 10/16 | 15/16 |
| c12 as SAFE | 15/16 | 10/16 | 15/16 |
| Both as SAFE | **16/16** | 10/16 | 14/16 |

Dangerous misses under the same four labellings:

| Ground truth used | One prompt, no tools | Scanner baseline | CloudFix |
|---|---|---|---|
| As published | 2/16 | 4/16 | **0/16** |
| c15 as SAFE | 1/16 | 4/16 | **0/16** |
| c12 as SAFE | 1/16 | 4/16 | **0/16** |
| Both as SAFE | 0/16 | 4/16 | **0/16** |

**Read the bottom left corner of the first table.** Accept both counter arguments
and the unaided prompt beats CloudFix, 16 to 14. That is the honest state of this
result and it is printed here rather than left for a judge to derive.

Three things follow, and they are the claims worth making:

1. **The scanner comparison does not move.** 10/16 and four dangerous misses in
   every labelling, because neither contested case is one the scanner gets right
   either way. The finding that deterministic findings alone do not decide a
   deploy is robust to the argument.
2. **The accuracy gap over the unaided prompt is not robust.** It rests entirely
   on two contextual judgements where reasonable engineers disagree. Anyone
   quoting 16/16 versus 14/16 as the headline of this project, including me,
   should quote this table beside it.
3. **The direction of the errors is robust.** CloudFix records 0/16 dangerous
   misses under every labelling tested. When it is wrong it is wrong toward
   caution, and it never once told a reviewer that something dangerous was fine.
   That property survives the disagreement, and for a tool that sits in front of
   a deploy it is worth more than the accuracy number that does not.

---

## The ladder: which design choice did the work

Each rung changes exactly one thing from the rung above, so the difference
between two rows is attributable to that change and nothing else.
`python run.py eval --system ladder --mode replay`

| What is in the system | Verdict accuracy | Change | Dangerous misses |
|---|---|---|---|
| One prompt, policy in the prompt, no tools | 14/16 | starting point | 2/16 |
| Deterministic checks plus a fixed severity gate, no model | 10/16 | -25 pts | 4/16 |
| Model judges the deterministic checks | **16/16** | **+38 pts** | 0/16 |
| Plus the blast radius summary in the prompt | 15/16 | **-6 pts** | 1/16 |
| Plus the verification pass | 16/16 | +6 pts | 0/16 |
| SHIPPED: checks plus verification, blast radius out of the prompt | **16/16** | +0 pts | 0/16 |

To be unambiguous about which row the single repair belongs to, because a
reviewer reading this misattributed it: the repair happened on **rung 5**,
`agent-checks-blast-verify`, where verification undid the damage the blast radius
summary had caused. The **shipped** system, rung 6, ran all sixteen cases with
**zero repairs**. `results/agent_results.json` carries `"repairs_total": 0`.

Two rows deserve attention, and neither is the row I expected to be writing about.

**Row four went down.** I built the blast radius analysis, believed in it, and it
made the system worse. On `c15` the blast report said "routine, nothing
destructive", which is correct, and the model latched onto that summary, dismissed
a standing SSH exposure in writing, and returned SAFE. Handing a model a
confident summary made it reason about the summary instead of about the plan.

**Row five got it back.** Verification rule V5 fired, handed the model one
numbered defect, and the model changed its verdict to REQUIRES HUMAN REVIEW. One
repair, one case. The whole exchange is in
`trajectories/agent-checks-blast-verify/c15_preexisting_open_port.json`.

So the shipped system is row three plus verification: the blast radius is
computed on every run and printed for the human, and kept out of the model's
prompt. Right analysis, wrong reader.

Full detail, including the mistakes that flattered this project, is in
[`IMPROVEMENT_CHANGELOG.md`](IMPROVEMENT_CHANGELOG.md).

---

## Main failure mode

**The verifier can prove a claim is true. It cannot prove a conclusion follows.**

On `c15` the model's evidence was completely correct. The SSH rule really was
open, it really was open before this change, and every pointer it cited resolved.
V1 passed it. V2 passed it, because a dismissal existed. The verdict was still
wrong.

V5 catches that shape now, and V5 exists only because I watched it happen. Every
rule that catches a wrong conclusion has to be written by hand, one shape at a
time, after seeing the shape. There is no general version of it, and anyone who
tells you their verification layer catches unsound reasoning in general has not
looked hard enough at what their layer actually checks.

Three smaller limits, said plainly:

- **The checks bound what can be found.** Seven check functions over common AWS
  and Kubernetes resources, producing sixteen finding types. A risk that is neither in a check nor visible in the plan
  actions is invisible to CloudFix.
- **The set does not test over blocking hard enough.** `c11` is a change that
  looks dangerous in the text and is safe. There is no case that is genuinely
  *destructive* and still correctly SAFE, for example a replacement with
  `create_before_destroy` and a final snapshot on a resource nobody depends on.
  A reviewer named this gap before submission and it is real: the 0/16 over block
  figure is measured on a set that never sets that particular trap. It is the
  first case I would add next.
- **Sixteen synthetic plans is not production.** They are hand written, they are
  deliberately clean, and a real plan is longer and messier. The right next step
  is real plans from real repositories, and until that is done the accuracy
  figure belongs to this case set and not to the world.
- **One recorded run per rung, plus a repeat study.** All three samples agreed,
  which at temperature 0 against a pinned model is expected and is not evidence
  of robustness. It rules out coin flipping. It does not rule out being
  consistently wrong about something nobody thought to test.

---

## Hot take

**Verification is not an accuracy technique. It is a safety constraint, and its
value only shows up on the day you make a design mistake.**

Be precise about what the numbers say, because the tempting version of this claim
is not the true one. Verification did **not** raise the final score. On the path
that shipped it changed nothing at all: zero repairs, 16/16 with it and 16/16
without it. Measuring only that, the honest conclusion would have been that it is
dead weight, and I would have cut it.

Its value showed up exactly one rung over, on the path where my own good idea had
made the model worse. There it caught a specific failure in the reasoning loop,
stopped an unsupported decision surviving to the final verdict, and was worth six
points and a dangerous miss.

**And here is how often the verifier actually fired, which is the number that
keeps this claim honest.** Across 32 reviews that ran a verification pass:

| Rule | What it catches | Times it fired |
|---|---|---|
| V1 | a cited pointer that does not resolve, or resolves to something else | **0** |
| V2 | a SAFE verdict walking past a critical finding or a severe blast radius | 0 |
| V3 | a DO NOT APPLY verdict with no reason | 0 |
| V4 | a dismissal of a check that never fired | 0 |
| V5 | a risk this change did not introduce, dismissed into SAFE | **1** |

Fifty six evidence pointers were resolved against their plans and **every single
one held**. The model did not invent a citation once. So V1, the rule this whole
design is named after, is a guard that has never had to do anything, and I am
reporting that rather than implying it earned its place. One rule fired, once,
and it fired on a policy mis-application rather than a hallucination.

That is a thin base for a general claim and it should be read as one. What it
supports is narrow and still worth saying: on this evidence the failure mode that
needed catching was not the model making things up, it was the model reasoning
correctly from a summary I should not have given it.

That is what a verification layer is for. Not a component you add on top of a
working system to make it more accurate, but the thing that catches you when you
give an agent more context, more tools or more structure and quietly make it
lazier. Every one of those additions feels like an improvement while you are
making it. The blast radius analysis was correct, well tested and useful to a
human, and putting it in the prompt still cost a verdict.

So the lesson I am taking into the next build: **measure every component you add
by removing it, and keep a check the model cannot argue with, because the
component that hurts you will be the one you were proudest of.**

---

## Running it

```
git clone https://github.com/legendonthisone/cloudfix.git
cd cloudfix
python run.py test                                  # 190 tests, no credentials, no internet
python run.py eval --system scanner                 # the scanner baseline, no model, free
pip install -r requirements.txt
python run.py eval --system both --mode replay      # the headline table above
python run.py eval --system ladder --mode replay    # the ladder table above
```

`--mode replay` reads the model responses recorded in `data/model_cache`. A judge
with no AWS account, no API key and no internet reproduces every number on this
page. Full detail, including the live path, is in
[`docs/REPRODUCTION_GUIDE.md`](docs/REPRODUCTION_GUIDE.md).

On your own infrastructure:

```
terraform plan -out=tfplan
terraform show -json tfplan > plan.json
python run.py review --plan plan.json
```

Exit code 0 for SAFE, 1 for REQUIRES HUMAN REVIEW, 2 for DO NOT APPLY, so it
drops into a pipeline as a gate. It still only recommends.

---

## Repository map

| Path | What it is |
|---|---|
| `src/cloudfix/plan.py` | Reads `terraform show -json`. Actions, environments, dependency references |
| `src/cloudfix/checks.py` | The deterministic security checks: 7 functions, 16 finding types |
| `src/cloudfix/blast.py` | Blast radius. What is destroyed and how far it reaches |
| `src/cloudfix/agent.py` | The agent: parse, check, blast, assess, verify, repair |
| `src/cloudfix/verify.py` | The verification pass. Five rules, no model |
| `src/cloudfix/baseline.py` | Rung 1: one prompt, no tools |
| `src/cloudfix/scanner.py` | Rung 2: the existing way, deterministic gate, no model |
| `src/cloudfix/prompts.py` | Every instruction any model is ever given, in one file |
| `src/cloudfix/policy.py` | The verdict policy, in code |
| `docs/VERDICT_POLICY.md` | The verdict policy, published. Identical text, asserted by a test |
| `data/plans/` | The sixteen synthetic Terraform plans |
| `data/cases.json` | Ground truth, with the reasoning behind every label |
| `data/model_cache/` | Recorded model responses, so the run replays with no credentials |
| `results/` | Every metric, every per case score, every review produced |
| `trajectories/` | Every step of every run. See `trajectories/README.md` |
| `tools/build_report.py` | Generates the tables above from `results/`, so no figure is typed by hand |
| `tools/audit.py` | The pre-submission audit. 42 mechanical checks against the brief: every deliverable present, every cited path real, every documented command implemented, no credential or personal detail anywhere, trajectories complete |
| `tests/test_claims.py` | Asserts every number in this README against the results file it came from. If a rerun moves a figure, the test suite fails until the writeup is corrected |

---

## Disclosures

**Licence.** MIT, in `LICENSE`. The only third party dependency is Anthropic's
`anthropic` client, used under its own terms through AWS Bedrock. Everything else
is the Python standard library.

**Coding agent.** CloudFix was built with Claude, running in Cowork with direct
access to the project files. Using a coding agent is required by the hackathon
and this is the disclosure.

**External review.** Before submission the writeup and the evaluation were put in
front of three other AI assistants as adversarial reviewers: Amazon Quick,
ChatGPT and Meta AI. They were used to attack the work, not to write it. The
changes their criticism produced are listed in `IMPROVEMENT_CHANGELOG.md`
alongside the code that implements each one, and the two contested labels
re-scored by `python run.py sensitivity` came directly from that round. One
suggestion was refused. Rewriting `c07` so that checkov genuinely could not see
it would have been changing the evidence to fit the claim, so the scanner rung
was instead given the same deletion protection and final snapshot checks that
checkov ships, which makes the comparison harder for CloudFix rather than easier.

**What existed before.** Nothing here predates the competition. Two files,
`src/cloudfix/model.py` and `src/cloudfix/providers.py`, were carried over from
my own earlier project in the same hackathon window
(`github.com/legendonthisone/lgnd-proposal-agent`) and adapted. They are the
model adapter and the recorded response cache. Everything else was written for
CloudFix.

**Data.** Every Terraform plan here is synthetic and hand written. No real
account, no real infrastructure, no customer data. The only AWS account number
that appears is `111122223333`, which is the number Amazon uses in its own
documentation, and a test asserts no other account number appears.

**Credentials.** None are in the repository. The live path reads an AWS profile
or an API key from the environment. The offline path needs neither. A test scans
the tracked source for credential shaped strings.

**Model.** The recorded run used `us.anthropic.claude-sonnet-4-5-20250929-v1:0`
through AWS Bedrock in `us-east-1`, at temperature 0, on Windows 11 with Python
3.14.3. The manifest in `data/model_cache/manifest.json` records it, and replay
reads the model name from there so a judge does not have to know it.

**Human control.** CloudFix produces a recommendation and a checklist. It has no
write path to any cloud provider, so the rule that consequential actions stay
behind a human is satisfied structurally rather than by policy: there is no code
in this project that could apply a change.
