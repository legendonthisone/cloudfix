"""
Writing a trajectory to disk.

The hackathon asks for representative trajectories: the instructions, the tool
calls, what the tools answered, the feedback that shaped the next step, retries,
human checkpoints and the final result. Every run of CloudFix produces one, so
the record is a by-product of using the tool rather than something assembled
afterwards for a submission.
"""

import json
import os

from . import policy


def trajectory_dict(result, plan_path: str, model: str = "", system: str = "agent") -> dict:
    return {
        "system": system,
        "plan_file": plan_path,
        "model": model,
        "steps": result.steps,
        "repairs": result.repairs,
        "model_calls": result.model_calls,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "error": result.error,
        "final_decision": result.decision.to_dict() if result.decision else None,
        "human_checkpoint": policy.HUMAN_CHECKPOINT_TEXT,
    }


def write_trajectory(path: str, result, plan_path: str, model: str = "", system: str = "agent"):
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            trajectory_dict(result, plan_path, model=model, system=system),
            handle,
            indent=2,
            ensure_ascii=False,
        )
    return path
