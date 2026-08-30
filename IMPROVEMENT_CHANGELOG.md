# Improvement Changelog

Every number in this document was produced by a command in this repository.
Reproduce any of them with

```
python run.py eval --system ladder --mode replay
```

which needs no AWS account, no API key and no internet.

**Primary metric: verdict accuracy**, the share of plans where the system
returned the verdict the ground truth says the plan deserves. Sixteen synthetic
Terraform plans, the same cases and the same scorer for every system, every
ground truth label tied to a numbered rule in `docs/VERDICT_POLICY.md`.

Two secondary metrics matter as much, because verdict accuracy alone hides the
difference between the two ways of being wrong:

- **dangerous miss**: the system judged a plan safer than it is. The failure that
  costs a company its data.
- **over block**: the system said DO NOT APPLY to a plan that did not deserve it.
  The failure that gets a tool switched off within a month.

Three parts. Part 1 is what happened, in order. Part 2 is the ablation ladder,
run afterwards to find out which single design choice did the work. Part 3 is
what was tried and removed.

---

# Part 1: How the solution evolved

| Stage | What was done and why | Evidence | Decision and learning |
|---|---|---|---|
| **0. Cut six agents down to one** | The design handed over at the start had an orchestrator, an infrastructure analyst, a security agent, a blast radius agent, a verification agent and a decision agent. Six agents is an org chart, not a one day build, and the rubric rewards purposeful components rather than a count of them | `src/cloudfix/agent.py` is one agent with five tools | Kept. The architecture stayed simple so the evaluation could decide whether more was justified. It never was, and Part 2 shows one addition actively hurting |
| **1. Write the verdict policy down before writing any code** | The whole evaluation rests on labels, and a label that comes from somebody's feel for infrastructure cannot be defended to a judge | `docs/VERDICT_POLICY.md`, eleven numbered rules | Kept, and it turned out to be the most important file here. It is given verbatim to the baseline and the agent, so no system has a better view of the target than another. It also supplied rule R5, hours before stage 11 turned out to need it |
| **2. Read the plan JSON, not the Terraform source** | Half the risks that matter are about the ACTION, not the configuration. Destroying a database does not appear in the source at all | `src/cloudfix/plan.py` | Kept. It is what lets a check ask what is being destroyed rather than only what is configured, and it is the difference the whole ladder measures |
| **3. Security checks as deterministic code, not model judgement** | Same plan in, same findings out, every time. That is what makes the primary metric objective | `src/cloudfix/checks.py`, 7 functions and 16 finding types, `tests/test_checks.py::Determinism` | Kept |
| **4. Ground truth before any system was run** | Sixteen cases, each labelled by hand, each label tied to a rule | `data/cases.json`, `tests/test_cases.py` | Kept. Labels are tested like code: every plan loads, every rule exists in the policy, every named critical resource is really in its plan, DO NOT APPLY cases cite only D rules |
| **5. A fair baseline, not a strawman** | Same role, same policy in full, same output shape, whole plan JSON. The only thing missing is a tool | `src/cloudfix/baseline.py`, `tests/test_docs.py` | Kept. The claim under test is not "a model cannot read Terraform". It is "a model reading Terraform unaided produces a verdict you cannot bank on". At 14/16 it is a genuinely strong opponent and the writeup says so |
| **6. A second baseline: a deterministic scanner and a gate** | Comparing only against a bare prompt would dodge the obvious question, which is why not just run the scanner a team already has. The rung is not checkov, it is the shape of that workflow: policy checks, a severity gate, a build that passes or fails | `src/cloudfix/scanner.py` | Kept. No model, free to run, 10/16. The question it answers is whether deterministic findings alone are enough to decide a deploy, and the answer is no |
| **7. Gave the scanner rung CloudFix's own checks** | A grep for `0.0.0.0/0` would have been an easy win. Giving the scanner the action aware checks, and later a deletion protection policy because checkov ships one, keeps it at least as strong as the real thing | `tests/test_scanner_and_scoring.py::TheExistingWay` | Kept, deliberately. If an agent beats a scanner handed the best available checks, the comparison is honest. Tests pin the scanner's exact behaviour on `c07` and on the three cases where nothing fires at all, so a future change cannot quietly make the README untrue |
| **8. Verification as code, never as a second opinion** | A model asked "is your answer right?" says yes. So nothing in the verifier asks it anything | `src/cloudfix/verify.py` | Kept. Every citation is resolved against the plan JSON and an unprovable claim is thrown away |
| **9. Fixed environment inference reading preprod as production** | "prod" is a substring of "preprod", so every pre-production environment read as production, which turns warnings into blocked deploys | `tests/test_plan.py::test_preprod_is_not_read_as_prod` | Fixed by testing the narrower words first |
| **10. Fixed blast radius calling a load balancer replacement severe** | The first version bumped any destructive production change one tier, so replacing a load balancer looked like losing a database. Everything in production came back severe, and a tool that says severe about everything says nothing | `tests/test_blast.py::Tiers` | Fixed. Severe is now reserved for data that will not exist afterwards. Dependents widen the effect but never make it irreversible |
| **11. Watched the verification loop fail, then added rule V5** | On `c15` the agent dismissed a standing SSH exposure in writing, correctly observing that the change did not cause it, and returned SAFE. V2 accepted it because V2 only asked whether a dismissal existed, never whether the dismissal was allowed to reach that verdict | `trajectories/agent-checks-blast/c15_preexisting_open_port.json` shows the failure, `trajectories/agent-checks-blast-verify/c15_preexisting_open_port.json` shows V5 catching it | Fixed. Policy rule R5 had been written at stage 1, before any of this ran. The verifier simply was not enforcing a rule the policy already contained. Worth +6 points, see Part 2 |
| **12. Caught the scanner citing evidence that failed its own check** | Python renders `True` as `"True"` and the plan file says `true`, so every scanner citation scored as unsupported. Left alone it would have made the existing way look like it hallucinates evidence, which it does not | the `quote()` call in `src/cloudfix/scanner.py` | Fixed. This one flattered CloudFix, which is exactly why it is listed |
| **13. Caught the critical resource metric measuring prose style** | "Did the review name the resource that mattered" was matched against the text. A review citing `resource_changes[0].change.actions` names its resource by position, and was scored as having missed it. The baseline was being reported at 2 of 13 when the real figure is 11 of 13 | `_cited_by_pointer` in `src/cloudfix/scoring.py` | Fixed by resolving the index to an address. This one flattered CloudFix too |
| **14. Repeat study, three samples per system** | The tool's promise is consistency as much as accuracy, and a single run cannot demonstrate either. A sample nonce lets repeat runs be recorded separately without invalidating the first | `results/consistency.json` | Kept, and it did not show what I expected. Both systems gave an identical verdict on every run, which is the honest result at temperature 0 against a pinned model. The finding underneath is that the unaided prompt is not unreliable, it is reliably wrong on the same two cases every time, which is worse: a wrong answer that wobbles gets caught on the second run, a repeatable one never does |
| **15. Caught the README claiming nine checks** | The writeup said nine deterministic checks. Nobody would have caught it by reading, and it is exactly the kind of number a judge does check | `tests/test_checks.py::TheDocumentedCounts` | Fixed, and a test now counts the functions and the finding ids, so the claim in the README cannot quietly stop being true |
| **16. Fact checked the checkov claim and found the comparison overstated** | The README said a security scanner comes back completely clean on `c07`. Checking it against checkov's own source rather than from memory, that is false: checkov ships `RDSDeletionProtection.py`, a policy for exactly the flag that plan turns off. The strongest baseline in this project was therefore weaker than the real tool on the one case used as the headline | checkov [`RDSDeletionProtection.py`](https://github.com/bridgecrewio/checkov/blob/main/checkov/terraform/checks/resource/aws/RDSDeletionProtection.py), and its [plan scanning docs](https://www.checkov.io/7.Scan%20Examples/Terraform%20Plan%20Scanning.html) | Fixed in code, not in wording. `check_data_guards` was added, the scanner rung now reports two medium findings on `c07` and returns REQUIRES HUMAN REVIEW instead of SAFE, and it is still wrong because the ground truth is DO NOT APPLY. The comparison got weaker and more true at the same time, and the three cases where no configuration policy fires at all (`c08`, `c09`, `c14`) are now the ones carrying the argument |
| **17. Published a sensitivity analysis instead of defending the labels** | Two external reviewers argued that `c15` and `c12` should be SAFE, and both arguments are good. The accusation underneath is the one that matters: that the conservative label was chosen because it makes the baseline wrong and CloudFix right | `src/cloudfix/sensitivity.py`, `python run.py sensitivity` | Kept the labels and published what happens if you reject them. Accept both counter arguments and the unaided prompt wins 16/16 to 14/16. That is in the README with the table. The scanner comparison does not move at all, and CloudFix records 0/16 dangerous misses under every labelling, so those two claims are robust and the accuracy gap over the prompt baseline is not. Better said by me than derived by a judge |
| **18. Counted how often the verifier actually fired** | The hot take rested on one incident, which is a thin base for a general claim, so the honest move was to publish the firing rate rather than the anecdote | `trajectories/*/*.json`, table in `README.md` | Across 32 verified reviews, 56 evidence pointers resolved and every one held. V1 through V4 never fired. V5 fired once. The model never invented a citation, so the rule this design is named after has never had to do anything, and the README says so |
| **19. An error message that named the wrong cause** | A missing AWS profile raises `ProfileNotFound`, whose class name contains `NotFound`, so the model name branch caught it and told the user their model was wrong. It cost real time during the recorded run | the credential branches in `src/cloudfix/model.py` | Fixed. An error message that names the wrong cause is worse than no message |

Stages 12, 13, 15, 16 and 19 are all cases where something was wrong in a direction that
made this project look better than it was. They are listed on purpose.

---

# Part 2: Which change did the work

Each rung changes exactly one thing from the rung above, so the difference
between two rows is attributable to that change and nothing else. All rungs see
the same sixteen plans and are scored by the same scorer.

| # | What is in the system | Verdict accuracy | Change | Dangerous misses | Over blocked |
|---|---|---|---|---|---|
| 1 | One prompt, policy in the prompt, no tools | 14/16 | starting point | 2/16 | 0/16 |
| 2 | Deterministic checks plus a fixed severity gate, no model | 10/16 | -25 pts | 4/16 | 2/16 |
| 3 | Model judges the deterministic checks | **16/16** | **+38 pts** | 0/16 | 0/16 |
| 4 | Plus the blast radius summary in the prompt | 15/16 | **-6 pts** | 1/16 | 0/16 |
| 5 | Plus the verification pass | 16/16 | **+6 pts** | 0/16 | 0/16 |
| 6 | SHIPPED: rung 3 plus verification, blast radius out of the prompt | **16/16** | +0 pts | 0/16 | 0/16 |

Row 2 is not a step down from row 1 in development order. It is the other
baseline, the way the job is done today, placed on the same ladder so the two
comparisons sit side by side.

## Rung 3, the change that did the work: +38 points

Deterministic checks plus a model to judge them took the scanner baseline from
10/16 to 16/16, and the unaided prompt from 14/16 to 16/16. Nothing else in this
project comes close.

Worth being precise about what moved, because the two gains are different gains.

Against the scanner, what the model adds is judgement over the same facts. The
scanner has a fixed severity map, so it blocks a public website bucket that is
meant to be public (`c12`) and blocks a tag edit for a problem the tag edit did
not cause (`c15`). And on `c08`, `c09` and `c14` no check fires at all, because
nothing in those plans is configured badly, so no gate setting reaches them. The
facts were never the missing piece. The interpretation was.

Against the unaided prompt the gain is smaller and lands entirely on the hard
cases, 3/5 to 5/5, on exactly the two contextual judgements the model got wrong
alone.

## Rung 4, the change I was proudest of, which made it worse: -6 points

The blast radius analysis is correct. It is well tested, it powers the "What is
changing" section of every review, and a human reading it learns something a
security scanner would never tell them.

Putting it in the model's prompt cost a verdict.

On `c15_preexisting_open_port`, a plan that adds two tags to a security group
that has had SSH open to the world for years, the blast report said "routine,
nothing destructive". That is accurate. The model then wrote:

> "This change only adds cost tracking tags to a security group. The SSH exposure
> to 0.0.0.0/0 was already present before this change and is not introduced by
> it. No resources are being created, destroyed, or having their security posture
> weakened."

and returned SAFE. Every sentence in that summary is true. The verdict is wrong,
because policy rule R5 says a standing risk goes to a human.

Without the blast summary, on the identical plan, the same model returned
REQUIRES HUMAN REVIEW and cited the before state as its evidence. The summary is
the only thing that changed.

**What it taught me:** a confident summary is not neutral context. Handing the
model a tidy verdict shaped conclusion, even a true one, made it reason about the
summary instead of about the plan.

## Rung 5, verification: +6 points, and only where it was needed

Rule V5 fired on `c15`, handed the model exactly one numbered defect, and the
model changed its verdict. One repair, one case, and the trajectory carries the
whole exchange:

> "You returned SAFE and dismissed SG_ADMIN_PORT_OPEN on
> aws_security_group.legacy_ftp because this change did not introduce it. The
> observation is right and the verdict is not. Policy rule R5 covers exactly this:
> a risk that was already true is still a risk, it just is not this deploy's
> fault, so it goes to a human. The verdict is REQUIRES HUMAN REVIEW."

Note what verification recovered: not a hallucination, not a bad citation, but
damage caused by the previous rung's own good idea.

## Rung 6, what ships

Rung 3 plus verification. The blast radius is computed on every run and printed
for the human, and kept out of the model's prompt.

On this path verification is worth **zero points**. Zero repairs across sixteen
cases, 16/16 with it and 16/16 without it. It ships anyway, and the reasoning is in
the hot take: the rung where it was worth six points is the rung where a design
change had quietly made the model worse, and the next design change has not been
made yet.

---

# Part 3: What was tried and removed

**The blast radius summary in the prompt. Removed.** Right analysis, wrong
reader. It cost six points and a dangerous miss, and the whole story is in rung 4
above. It stays in the codebase and in every review, because it is genuinely
useful to a person. The flag that puts it in the prompt is off by default, and
`tests/test_agent.py::ShippedConfiguration` holds both halves of that in place.

**Naming the policy rule inside a finding. Removed before it was measured.** The
first version of the pre-existing finding label ended with "Policy rule R5 covers
it." That is a deterministic check doing the model's judging, which is the one
thing the split between code and model exists to prevent. The check now states
the fact and stops: `introduced_by_change: false`. Mapping a fact to a rule is
the model's job, and V5 checks that mapping afterwards.

**A generic production bump in the blast radius. Removed at stage 10.** Any
destructive change in production went up a tier, so a load balancer replacement
came back the same colour as losing a database. Everything in production was
severe, and a tool that says severe about everything says nothing.

**Giving the scanner rung blast radius. Considered and rejected.** It would have
made rung 2 stronger, but rung 2 exists to represent what a team has today, and
what a team has today is a security scanner. Adding blast radius to it would have
been measuring a tool nobody runs, and it would have blurred the one thing the
ladder is there to separate.

**Six agents. Removed before a line was written.** See stage 0.

---

# Main failure mode

**The verifier can prove a claim is true. It cannot prove a conclusion follows.**

On `c15` the model's evidence was completely correct. The SSH rule really was
open, it really was open before this change, and every pointer it cited resolved
against the plan. V1 passed it. V2 passed it, because a dismissal existed. The
verdict was still wrong.

V5 catches that shape now, and V5 exists only because the failure was watched
happening. Every rule that catches a wrong conclusion has to be written by hand,
one shape at a time, after seeing the shape. There is no general version of it.

Three smaller limits:

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
- **Sixteen synthetic plans is not production.** Hand written, deliberately
  clean, and a real plan is longer and messier. The accuracy figure belongs to
  this case set, not to the world.
- **One recorded run per rung, plus a three sample repeat study.** All three
  samples agreed, which at temperature 0 against a pinned model is expected and
  is not evidence of robustness. It rules out coin flipping. It does not rule out
  being consistently wrong about something nobody thought to test.

---

# Hot take

**Verification is not an accuracy technique. It is a safety constraint, and its
value only shows up on the day you make a design mistake.**

Be precise, because the tempting version of this claim is not the true one.
Verification did **not** raise the final score. On the path that shipped it
changed nothing: zero repairs, 16/16 with it and 16/16 without it. Measuring only
that, the honest conclusion would have been that it is dead weight, and I would
have cut it.

Its value showed up one rung over, on the path where my own good idea had made
the model worse. There it was worth six points and a dangerous miss.

That reframes what a verification layer is for. It is not an accuracy technique
bolted onto a working system. It is the thing that catches you when you give an
agent more context, more tools or more structure and quietly make it lazier.
Every one of those additions feels like an improvement while you are making it.
The blast radius analysis was correct, well tested, and useful to a human, and
putting it in the prompt still cost a verdict.

So the lesson going into the next build: **measure every component by removing
it, and keep one check the model cannot argue with, because the component that
hurts you will be the one you were proudest of.**
