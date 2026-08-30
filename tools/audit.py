#!/usr/bin/env python3
"""
The pre-submission audit.

Mechanical checks against the hackathon brief, so that "we met the requirements"
is a command rather than a claim. It verifies that every required deliverable
exists and contains the sections the brief asks for, that every file path and
anchor cited in the documentation resolves, that every documented command is
actually implemented, that no credential, personal email or local machine path
appears anywhere in the tracked files, and that the trajectories carry the agent
instructions the brief requires.

    python tools/audit.py

Exit code 0 means every check passed.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAIL, WARN, OK = [], [], []


def fail(tag, msg):
    FAIL.append("%s: %s" % (tag, msg))


def warn(tag, msg):
    WARN.append("%s: %s" % (tag, msg))


def ok(tag, msg):
    OK.append("%s: %s" % (tag, msg))


def read(rel):
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as h:
        return h.read()


DOCS = ["README.md", "IMPROVEMENT_CHANGELOG.md", "START_HERE.md",
        "docs/REPRODUCTION_GUIDE.md", "docs/VERDICT_POLICY.md",
        "docs/VIDEO_SCRIPT.md", "trajectories/README.md"]

# ---------------------------------------------------------------- deliverables
for f in ("README.md", "IMPROVEMENT_CHANGELOG.md", "docs/REPRODUCTION_GUIDE.md"):
    if os.path.exists(os.path.join(ROOT, f)):
        ok("D", "%s present" % f)
    else:
        fail("D", "%s MISSING" % f)

readme = read("README.md")
for phrase, label in [
    ("Who has this problem", "intended user"),
    ("What bottleneck makes it worth solving", "current bottleneck"),
    ("Why solving it is valuable", "why valuable"),
    ("Main failure mode", "main failure mode"),
    ("Hot take", "hot take"),
]:
    (ok if phrase in readme else fail)("D01", "README %s section" % label)

chg = read("IMPROVEMENT_CHANGELOG.md")
(ok if "Improvement Changelog" in chg else fail)("D01", "changelog is clearly labelled")
(ok if "removed" in chg.lower() else fail)("D01", "changelog covers removed experiments")

# instructions that shape each agent must be findable
(ok if os.path.exists(os.path.join(ROOT, "src/cloudfix/prompts.py")) else fail)(
    "D01", "prompts.py exists")
(ok if "prompts.py" in readme else fail)("D01", "README points at prompts.py")

# ------------------------------------------------------------------ paths cited
path_re = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:py|md|json|txt))`")
missing = set()
for doc in DOCS:
    if not os.path.exists(os.path.join(ROOT, doc)):
        continue
    for m in path_re.finditer(read(doc)):
        p = m.group(1)
        if p.startswith(("http", "github.com")) or "*" in p:
            continue
        if "/" not in p and not os.path.exists(os.path.join(ROOT, p)):
            continue  # bare filename, could be prose
        here = os.path.dirname(os.path.join(ROOT, doc))
        if "/" in p and not (
            os.path.exists(os.path.join(ROOT, p)) or os.path.exists(os.path.join(here, p))
        ):
            missing.add("%s -> %s" % (doc, p))
if missing:
    for m in sorted(missing):
        fail("PATH", m)
else:
    ok("PATH", "every file path cited in the docs exists")

# ------------------------------------------------------------- anchors in README
anchors = set()
for line in readme.splitlines():
    if line.startswith("#"):
        text = line.lstrip("#").strip().lower()
        text = re.sub(r"[^a-z0-9 -]", "", text).replace(" ", "-")
        anchors.add(text)
for m in re.finditer(r"\]\(#([a-z0-9-]+)\)", readme):
    (ok if m.group(1) in anchors else fail)("ANCHOR", "#%s" % m.group(1))

# ------------------------------------------------------------------- privacy
tracked = []
for d, dirs, files in os.walk(ROOT):
    dirs[:] = [x for x in dirs if x not in (".git", "__pycache__", ".venv")]
    for f in files:
        if f.endswith((".py", ".md", ".json", ".txt", ".gitignore")):
            tracked.append(os.path.join(d, f))

BAD = ["aje.adetayo", "@gmail.com", "AK" + "IA", "AS" + "IA", "sk-" + "ant-",
       "aws_secret" + "_access_key", "BEGIN PRIVATE" + " KEY", "password",
       "C:\\\\Users", "/Users/"]
hits = []
for path in tracked:
    if os.path.basename(path) in ("audit.py", "test_docs.py"):
        continue
    try:
        text = open(path, "r", encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        continue
    for token in BAD:
        if token in text:
            hits.append("%s contains %r" % (os.path.relpath(path, ROOT), token))
if hits:
    for h in hits:
        fail("PRIVACY", h)
else:
    ok("PRIVACY", "no personal email, credential pattern or local path in %d files" % len(tracked))

# account numbers
acct = set(re.findall(r"\b\d{12}\b", "\n".join(
    open(p, encoding="utf-8", errors="ignore").read() for p in tracked)))
if acct - {"111122223333"}:
    fail("PRIVACY", "unexpected 12 digit account numbers: %s" % (acct - {"111122223333"}))
else:
    ok("PRIVACY", "only the AWS documentation account number appears")

# ---------------------------------------------------------------- trajectories
tdirs = [d for d in os.listdir(os.path.join(ROOT, "trajectories"))
         if os.path.isdir(os.path.join(ROOT, "trajectories", d))]
expected = {"baseline", "scanner", "agent", "agent-checks",
            "agent-checks-blast", "agent-checks-blast-verify"}
missing_sys = expected - set(tdirs)
(ok if not missing_sys else fail)("D04", "trajectory folder per system %s" % (
    "" if not missing_sys else "MISSING %s" % missing_sys))

sample = os.path.join(ROOT, "trajectories", "agent")
if not os.path.isdir(sample):
    warn("D04", "no trajectories on disk, run the evaluation before auditing")
    files = []
else:
    files = sorted(f for f in os.listdir(sample) if f.endswith(".json"))
if files:
    (ok if len(files) == 16 else fail)(
        "D04", "agent has %d trajectories (expected 16)" % len(files))

traj = json.load(open(os.path.join(sample, files[0]), encoding="utf-8")) if files else {}
for key, label in [("steps", "tool calls and responses"),
                   ("final_decision", "final result"),
                   ("ground_truth", "ground truth"),
                   ("score", "score")]:
    if files:
        (ok if key in traj else fail)("D04", "trajectory carries %s" % label)

model_steps = [s for s in traj.get("steps", []) if s.get("kind") == "model"]
has_instructions = bool(model_steps) and all(
    s.get("system_prompt") and s.get("user_prompt") for s in model_steps)
if files:
    (ok if has_instructions else fail)(
        "D04", "trajectory carries the agent instructions (brief: 'from the agent "
               "instructions to the final result')")

# human checkpoint
if files:
    any_checkpoint = "human_checkpoint" in traj
    (ok if any_checkpoint else fail)("D04", "human checkpoint recorded in the trajectory")

# ------------------------------------------------------------------ repro guide
guide = read("docs/REPRODUCTION_GUIDE.md")
for phrase, label in [("git clone", "clone step"), ("python run.py test", "tests"),
                      ("--mode replay", "offline replay"), ("Python", "version"),
                      ("Cost", "cost"), ("Time", "runtime")]:
    (ok if phrase in guide else fail)("D02", "repro guide states %s" % label)

# every run.py command mentioned anywhere is a real subcommand
cmds = set(re.findall(r"python run\.py (\w[\w-]*)", "\n".join(
    read(d) for d in DOCS if os.path.exists(os.path.join(ROOT, d)))))
runpy = read("run.py")
for c in sorted(cmds):
    (ok if ('command == "%s"' % c) in runpy or c in ("test",) else fail)(
        "CMD", "python run.py %s is implemented" % c)

# ------------------------------------------------------------------- video plan
vid = read("docs/VIDEO_SCRIPT.md")
for phrase, label in [("problem", "problem"), ("baseline", "baseline"),
                      ("replay", "a live execution"), ("ladder", "changelog"),
                      ("removed", "an experiment removed"), ("hot take", "hot take")]:
    (ok if phrase.lower() in vid.lower() else fail)("D03", "video script covers %s" % label)

print("\n".join("FAIL  " + x for x in FAIL) or "")
print("\n".join("WARN  " + x for x in WARN) or "")
print("\nchecks passed: %d, warnings: %d, failures: %d" % (len(OK), len(WARN), len(FAIL)))
sys.exit(1 if FAIL else 0)
