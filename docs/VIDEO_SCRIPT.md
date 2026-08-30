# Solution video script

Five minutes maximum. Screen recording with voice over, Clipchamp. Terminal on
screen almost the whole time. Two still frames for the tables, nothing else.

Every number below is real and comes out of `results/`. Do a silent dry run of
each command before recording.

---

## 0:00 to 0:35, the problem, as a person not a product

> "Before any infrastructure change goes live, somebody has to read a Terraform
> plan and decide yes or no. That plan can be hundreds of lines across IAM,
> networking, databases and compute. Working out what actually matters is slow,
> and it is inconsistent, because a review that missed something looks exactly
> like a review that did not. Both of them say approved."

On screen: scroll `data/plans/c07_prod_db_replace_clean.json` slowly.

> "I am a cloud engineer. This is my own job I am automating."

---

## 0:35 to 1:25, the existing way, and where it breaks

> "The tools a team already has are checkov and tfsec. They are good, and they
> are security scanners: they read configuration and answer, is this configured
> badly. So I built that as my first baseline, and I gave it my own checks, which
> makes it stronger than the real thing."

Run on camera:

```
python run.py scan --plan data/plans/c07_prod_db_replace_clean.json
```

Let it land. Point at the output: two medium findings, verdict REQUIRES HUMAN
REVIEW.

> "It sees something. Deletion protection is going off, and there will be no
> final snapshot. checkov ships a policy for exactly that, so I gave the scanner
> the same check. It reports two findings and asks for a human."

Cut back to the plan and highlight the third line: `engine_version` forces
replacement.

> "Here is what it did not say. This plan REPLACES the production orders
> database. The data stops existing, and with the final snapshot skipped there is
> nothing to restore. A checkbox being off and the data being gone are not the
> same finding, and only one of them is a decision. The correct answer is do not
> apply. The scanner said ask a human."

Then run the case that is further out of reach:

```
python run.py scan --plan data/plans/c09_prod_ec2_replace.json
```

> "And this one it cannot see at all. Replacing the production API server.
> Encrypted, private, monitored, nothing configured badly, zero findings, verdict
> safe. There are three cases like that in my set, and no severity gate however
> strict changes any of them, because there is nothing to gate on. Across
> sixteen cases the scanner scores 62 percent with four dangerous misses."

---

## 1:25 to 2:35, one realistic execution, end to end

```
python run.py review --plan data/plans/c07_prod_db_replace_clean.json --mode replay
```

Talk over it:

> "CloudFix parses the plan into actions, runs its deterministic security checks,
> and runs a blast radius analysis. Then the model does the one thing code cannot
> do here, which is judge. And then code checks the judging."

Walk the output top to bottom on screen:

- Verdict DO NOT APPLY, policy rule D4
- What is changing, worst blast radius severe, and the two resources that depend
  on the database
- The three reasons, each with a pointer such as
  `resource_changes[0].change.after.skip_final_snapshot`, each marked verified
  against the plan
- Scroll to the bottom: raw findings from the deterministic checks, the same two mediums the scanner found
- The human approval checkpoint

> "Same two findings the scanner had. Different verdict. The scanner reported
> what is configured wrong. CloudFix reported what is about to happen, and those
> are not the same job.
>
> Every claim carries a pointer into the plan, and code resolved that pointer
> before I saw it. A claim it cannot prove gets thrown away. And CloudFix never
> applies anything. It recommends. I decide."

---

## 2:35 to 3:05, the false positive nobody talks about

```
python run.py review --plan data/plans/c11_closing_ssh_rule.json --mode replay
```

> "This plan has SSH open to the whole internet sitting in its text. A tool that
> greps flags it. But read the after state: the change is removing that rule.
> Verdict, safe. Blocking this deploy would be worse than useless. It would teach
> the team to bypass the tool, and then the real finding goes past too."

---

## 3:05 to 3:50, the measured comparison

Still frame, the headline table:

| | Scanner | One prompt | CloudFix |
|---|---|---|---|
| Verdict accuracy | 10/16 | 14/16 | **16/16** |
| Dangerous misses | 4/16 | 2/16 | **0/16** |
| Over blocked | 2/16 | 0/16 | **0/16** |
| The 5 hard cases | 2/5 | 3/5 | **5/5** |

> "Sixteen synthetic plans, labelled by hand before anything ran, every label tied
> to a numbered rule in a published policy. Same cases, same scorer, every system.
>
> The scanner gets ten out of sixteen. A single prompt with the full policy and
> the whole plan, no tools, gets fourteen, and it is a strong opponent, I did not
> cripple it. CloudFix gets sixteen.
>
> But the number I care about more than accuracy is dangerous misses: the times a
> system called something safer than it is. Four, two, zero. That is the one that
> costs a company its data."

---

## 3:50 to 4:35, the changelog, and the experiment I removed

Still frame, the ladder:

| What is in the system | Accuracy | Change |
|---|---|---|
| One prompt, no tools | 14/16 | |
| Scanner, no model | 10/16 | -25 pts |
| Model judges the deterministic checks | 16/16 | **+38 pts** |
| Plus blast radius in the prompt | 15/16 | **-6 pts** |
| Plus the verification pass | 16/16 | **+6 pts** |

> "Each row changes exactly one thing. The checks plus a model to judge them did
> the work: plus 38 points.
>
> Now the row I did not want to write. I built the blast radius analysis, I was
> proud of it, and putting it in the model's prompt made the system worse. On the
> case where a plan just adds tags to a host that has had SSH open for years, the
> blast report said routine, nothing destructive, which is true. The model latched
> onto that summary, dismissed a standing exposure in writing, and said safe.
> Handing a model a confident summary made it reason about the summary instead of
> about the plan.
>
> The verification pass caught exactly that. One rule fired, handed the model one
> numbered defect, and it changed its verdict. So the blast radius stays computed
> and printed for the human, and stays out of the model's prompt. Right analysis,
> wrong reader."


---

## 4:35 to 4:55, the number I do not trust, said out loud

```
python run.py sensitivity
```

> "One more thing, because sixteen out of sixteen deserves suspicion. I wrote
> these cases and I wrote the policy. Two of my labels are genuinely arguable, and
> reviewers argued with both. So I re-scored every verdict against their labels
> instead of mine.
>
> Take both of their arguments and the plain prompt beats me, sixteen to fourteen.
> That table is in the README, above my own headline number.
>
> Two things survive it. The scanner comparison does not move at all. And CloudFix
> never records a dangerous miss under any labelling, because when it is wrong it
> is wrong toward caution. That is the claim I will actually defend."

---

## 4:55 to 5:00, the sign off

> "So, the hot take. Verification is not an accuracy technique. On the path that
> shipped it changed nothing at all. Its value showed up on the path where my own
> good idea had made the model lazier. It is what stops a design mistake from
> becoming a wrong answer, and the component that hurts you will be the one you
> were proudest of.
>
> All of this reproduces from a clean clone, no AWS account, no API key, because
> every model response is recorded in the repository."

---

## Recording notes

- Terminal font large enough to read on a phone.
- Use `--mode replay` on camera. Instant, free, and the same path a judge takes.
- The two tables are still frames, not scrolled markdown. Everything else is the
  live terminal.
- Do not read the README aloud. Show the terminal, say the point.
- If you fluff a line, keep rolling and say it again. Cut in Clipchamp.
