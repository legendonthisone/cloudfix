"""
The CloudFix agent.

One agent, several purposeful tools. Not six agents. The architecture was kept
deliberately simple so that the evaluation could decide whether anything more was
justified, rather than the other way round.

Six steps, and only two of them use a model:

  1. Parse        tool     read the plan JSON into resources and actions
  2. Check        tool     the deterministic security checks, with evidence
  3. Blast        tool     what is destroyed and how far it reaches
  4. Assess       model    which facts matter here, and the verdict, with citations
  5. Verify       tool     resolve every citation against the plan itself
  6. Repair       model    only when verification failed, and only against a
                           numbered list of what did not hold up

The shape of the idea: code finds the facts, the model does the judging, and code
checks the judging against the facts. The model is never the last word on whether
its own answer is true.

Two flags exist for the ablation study, and nothing else changes with them:

  use_blast        put the blast radius summary in the model's prompt, or do
                   not. It is computed either way, because the human report
                   needs it. The shipped system has this off, and the changelog
                   explains why
  verify_enabled   run steps 5 and 6, or stop after step 4
"""

import json
import time
from typing import List

from . import blast as blast_module
from . import checks
from .decision import ReviewResult
from .model import ModelClient
from .parsing import ParseError, parse_decision
from .prompts import AGENT_SYSTEM, AGENT_USER, BLAST_BLOCK
from .verify import verify as verify_decision

MAX_REPAIRS = 2


def _findings_block(findings) -> str:
    if not findings:
        return (
            "No security check fired on this plan.\n"
            "Remember that this is not the same as the plan being safe."
        )
    return checks.findings_report(findings)


def review(
    plan,
    client: ModelClient,
    use_blast: bool = False,
    verify_enabled: bool = True,
    max_repairs: int = MAX_REPAIRS,
) -> ReviewResult:
    started = time.time()
    steps: List[dict] = []
    tokens_in = tokens_out = calls = 0
    model_seconds = 0.0
    cached = True

    def account(response):
        nonlocal tokens_in, tokens_out, calls, model_seconds, cached
        tokens_in += response.input_tokens
        tokens_out += response.output_tokens
        model_seconds += response.latency_seconds
        calls += 1
        if not response.from_cache:
            cached = False

    # Step 1. Parse. Deterministic.
    acting = plan.acting_changes()
    steps.append(
        {
            "step": 1,
            "name": "parse",
            "kind": "tool",
            "tool": "plan.load_plan",
            "output": {
                "terraform_version": plan.terraform_version,
                "resource_changes": len(plan.changes),
                "acting_changes": [c.summary() for c in acting],
            },
        }
    )

    # Step 2. Deterministic security checks.
    findings = checks.run_all(plan)
    steps.append(
        {
            "step": 2,
            "name": "security_checks",
            "kind": "tool",
            "tool": "checks.run_all",
            "output": {
                "finding_count": len(findings),
                "findings": [f.to_dict() for f in findings],
            },
        }
    )

    # Step 3. Blast radius. Deterministic, and always computed, because the
    # human report needs it. The flag controls only one thing: whether the
    # summary is put in front of the model.
    #
    # It ships off. The evaluation showed that handing the model a confident
    # summary made it reason about the summary instead of about the plan, and
    # cost a verdict. Right analysis, wrong reader. See IMPROVEMENT_CHANGELOG.md.
    blast_report = blast_module.analyse(plan)
    steps.append(
        {
            "step": 3,
            "name": "blast_radius",
            "kind": "tool",
            "tool": "blast.analyse",
            "given_to_model": use_blast,
            "output": blast_report.to_dict(),
        }
    )

    plan_text = json.dumps(plan.raw, indent=2, ensure_ascii=False)
    blast_text = BLAST_BLOCK % blast_report.render() if use_blast else ""
    user = AGENT_USER % (
        plan_text,
        plan.to_summary_text(),
        _findings_block(findings),
        blast_text,
    )

    # Step 4. Assess. The only place judgement happens.
    decision = None
    last_error = None
    raw_text = ""
    for attempt in (1, 2):
        prompt = user if attempt == 1 else (
            user
            + "\n\nYour previous reply could not be read: %s\nReturn ONLY the JSON object."
            % last_error
        )
        response = client.complete(
            system=AGENT_SYSTEM, user=prompt, max_tokens=2000, temperature=0.0
        )
        account(response)
        raw_text = response.text
        try:
            decision = parse_decision(response.text)
        except ParseError as exc:
            last_error = str(exc)
            steps.append(
                {
                    "step": len(steps) + 1,
                    "name": "assess",
                    "kind": "model",
                    "attempt": attempt,
                    "system_prompt": AGENT_SYSTEM,
                    "user_prompt": prompt,
                    "ok": False,
                    "error": last_error,
                    "raw_reply": response.text[:600],
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                }
            )
            continue
        steps.append(
            {
                "step": len(steps) + 1,
                "name": "assess",
                "kind": "model",
                "attempt": attempt,
                "system_prompt": AGENT_SYSTEM,
                "user_prompt": prompt,
                "ok": True,
                "output": decision.to_dict(),
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            }
        )
        break

    if decision is None:
        return ReviewResult(
            decision=None,
            findings=findings,
            blast=blast_report,
            steps=steps,
            seconds=time.time() - started,
            model_seconds=model_seconds,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            model_calls=calls,
            from_cache=cached,
            error="could not read a decision out of the reply: %s" % last_error,
            raw_text=raw_text,
        )

    if not verify_enabled:
        steps.append(
            {
                "step": len(steps) + 1,
                "name": "verify",
                "kind": "skipped",
                "detail": "ablation: verification disabled",
            }
        )
        return ReviewResult(
            decision=decision,
            findings=findings,
            blast=blast_report,
            steps=steps,
            seconds=time.time() - started,
            model_seconds=model_seconds,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            model_calls=calls,
            from_cache=cached,
            raw_text=raw_text,
        )

    # Steps 5 and 6. Verify, then repair, until it holds up or we run out of tries.
    repairs = 0
    verdict = verify_decision(decision, plan.raw, findings, blast_report)
    steps.append(
        {
            "step": len(steps) + 1,
            "name": "verify",
            "kind": "tool",
            "tool": "verify.verify",
            "output": verdict.to_dict(),
        }
    )

    while not verdict.passed and repairs < max_repairs:
        repairs += 1
        repair_user = (
            user
            + "\n\n--- YOUR PREVIOUS DECISION ---\n"
            + json.dumps(decision.to_dict(), indent=2, ensure_ascii=False)
            + "\n--- END ---\n\n"
            + verdict.repair_instruction()
        )
        response = client.complete(
            system=AGENT_SYSTEM, user=repair_user, max_tokens=2000, temperature=0.0
        )
        account(response)
        raw_text = response.text
        try:
            repaired = parse_decision(response.text)
        except ParseError as exc:
            steps.append(
                {
                    "step": len(steps) + 1,
                    "name": "repair",
                    "kind": "model",
                    "attempt": repairs,
                    "system_prompt": AGENT_SYSTEM,
                    "user_prompt": repair_user,
                    "ok": False,
                    "error": str(exc),
                    "raw_reply": response.text[:600],
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                }
            )
            break
        decision = repaired
        steps.append(
            {
                "step": len(steps) + 1,
                "name": "repair",
                "kind": "model",
                "attempt": repairs,
                "system_prompt": AGENT_SYSTEM,
                "user_prompt": repair_user,
                "ok": True,
                "defects_given": verdict.defects,
                "output": decision.to_dict(),
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            }
        )
        verdict = verify_decision(decision, plan.raw, findings, blast_report)
        steps.append(
            {
                "step": len(steps) + 1,
                "name": "verify",
                "kind": "tool",
                "tool": "verify.verify",
                "attempt": repairs + 1,
                "output": verdict.to_dict(),
            }
        )

    return ReviewResult(
        decision=decision,
        findings=findings,
        blast=blast_report,
        steps=steps,
        seconds=time.time() - started,
        model_seconds=model_seconds,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        model_calls=calls,
        from_cache=cached,
        repairs=repairs,
        raw_text=raw_text,
        error=None
        if verdict.passed
        else "verification still failing: %s" % "; ".join(verdict.defects),
    )
