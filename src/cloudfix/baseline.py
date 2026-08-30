"""
The baseline: one prompt, no tools.

This is the reasonable basic way a competent engineer would handle the task today
with a language model. It is deliberately not a strawman. It gets:

  the same role description
  the same verdict policy, in full
  the same required output shape
  the whole plan JSON

The only thing it does not get is a tool. That is the claim under test: not "a
model cannot read Terraform", but "a model reading Terraform unaided produces a
verdict you cannot bank on".
"""

import json
import time

from .decision import ReviewResult
from .model import ModelClient
from .parsing import ParseError, parse_decision
from .prompts import BASELINE_SYSTEM, BASELINE_USER


def review(plan, client: ModelClient) -> ReviewResult:
    started = time.time()
    steps = []
    plan_text = json.dumps(plan.raw, indent=2, ensure_ascii=False)
    user = BASELINE_USER % plan_text

    tokens_in = tokens_out = calls = 0
    model_seconds = 0.0
    cached = True
    last_error = None
    text = ""

    for attempt in (1, 2):
        prompt = user if attempt == 1 else (
            user
            + "\n\nYour previous reply could not be read: %s\nReturn ONLY the JSON object."
            % last_error
        )
        response = client.complete(
            system=BASELINE_SYSTEM, user=prompt, max_tokens=2000, temperature=0.0
        )
        tokens_in += response.input_tokens
        tokens_out += response.output_tokens
        model_seconds += response.latency_seconds
        calls += 1
        if not response.from_cache:
            cached = False
        text = response.text

        try:
            decision = parse_decision(response.text)
        except ParseError as exc:
            last_error = str(exc)
            steps.append(
                {
                    "step": len(steps) + 1,
                    "name": "review",
                    "kind": "model",
                    "attempt": attempt,
                    "system_prompt": BASELINE_SYSTEM,
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
                "name": "review",
                "kind": "model",
                "attempt": attempt,
                "system_prompt": BASELINE_SYSTEM,
                "user_prompt": prompt,
                "ok": True,
                "output": decision.to_dict(),
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
            }
        )
        return ReviewResult(
            decision=decision,
            steps=steps,
            seconds=time.time() - started,
            model_seconds=model_seconds,
            input_tokens=tokens_in,
            output_tokens=tokens_out,
            model_calls=calls,
            from_cache=cached,
            raw_text=text,
        )

    return ReviewResult(
        decision=None,
        steps=steps,
        seconds=time.time() - started,
        model_seconds=model_seconds,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        model_calls=calls,
        from_cache=cached,
        error="could not read a decision out of the reply: %s" % last_error,
        raw_text=text,
    )
