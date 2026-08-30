# Agent trajectories

One file per system per case. Every file is the complete record of one review:
the instructions the agent was given, each tool call and what the tool answered,
the model's decision, what the verifier said about it, any repair, and the final
result.

These are not written for the submission. Every run of CloudFix produces one, so
the record is a by-product of using the tool.

## Where to look first

| File | Why |
|---|---|
| `agent/c07_prod_db_replace_clean.json` | The case the existing tools cannot see. Security checks return nothing, blast radius returns severe, and the decision comes from that |
| `agent/c11_closing_ssh_rule.json` | The false positive trap. The plan text contains 0.0.0.0/0 on port 22 and the correct answer is SAFE |
| `agent/c12_dev_static_website.json` | Public bucket that is meant to be public. The judgement the deterministic checks cannot make |
| `baseline/*.json` | The same sixteen plans reviewed by one prompt with no tools. Compare the reasons |
| `scanner/*.json` | No model at all. Two steps: run the checks, apply the severity gate |

## How to read one

```json
{
  "system": "agent",
  "case_id": "c07_prod_db_replace_clean",
  "ground_truth": { "expected_verdict": "...", "rules": ["D4"], "why": "..." },
  "steps": [ ... ],
  "final_decision": { ... },
  "score": { ... }
}
```

Each entry in `steps` carries a `kind`:

| kind | Meaning |
|---|---|
| `tool` | Deterministic code. Same input, same output, every run. No model involved |
| `model` | A call to the language model. The step carries `system_prompt` and `user_prompt`, the exact bytes that were sent, so the run reads end to end from the instructions to the verdict. The templates they were built from are in `src/cloudfix/prompts.py` |
| `skipped` | A step an ablation rung deliberately removed, recorded so the trajectory still shows the shape of the pipeline |

The `verify` steps are the interesting ones. `output.defects` is the numbered
list handed back to the model, and the `repair` step that follows shows what it
did with it. Where `defects` is empty the decision held up first time.

## Human checkpoint

Every trajectory ends with the same line, because it is true of every run:
CloudFix never applies anything. The verdict is a recommendation and a human
decides. Nothing in this project holds a credential that could change
infrastructure.

## The coding agent that built this

The tool used to build CloudFix was Claude, in Cowork, driving the files in this
repository directly. The conversation that produced it is part of the submission
material rather than part of the running system, so it is not in this folder.
