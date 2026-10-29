"""
DevFest Demo 2: An agent that critiques itself and tries again.

The loop:  ACT (write code) -> FEEDBACK (run real tests) ->
           REFLECT (write a lesson about the failure) -> RETRY with lessons in memory.

No model weights change. The improvement lives in the memory of lessons.
The reward is objective: tests pass or they don't.

Run:   pip install google-genai
       put GEMINI_API_KEY in .env at the repo root (or export it)
       python demo2_reflexion_agent.py

On-device model (no internet, via Ollama):     python demo2_reflexion_agent.py --local
Save a real run for offline replay:            python demo2_reflexion_agent.py --local --record
Replay the saved run (no model at all):        python demo2_reflexion_agent.py --mock
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import urllib.request

# Read KEY=value lines from the repo's .env, so no shell setup is needed on any OS.
# Variables already set in the environment win.
ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(ENV_FILE):
    for line in open(ENV_FILE):
        key, sep, value = line.strip().partition("=")
        if sep and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))

MODEL =os.environ.get("DEMO_MODEL", "gemini-3.5-flash")
LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "qwen2.5-coder:3b")
MOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_run.json")
MAX_ATTEMPTS = int(os.environ.get("DEMO_ATTEMPTS", 6))

TASK = textwrap.dedent("""
    Write a Python function `parse_amount(text: str) -> int` that turns a
    payment amount written by a person into an integer number of currency units.
    Return only the code in a single ```python block, with no explanation,
    no example usage and no print statements.
""").strip()

# The tests are the reward signal. The model never sees the full suite;
# it only sees the cases it failed. Deliberately full of real-world messiness.
TESTS = textwrap.dedent("""
    try:
        from solution import parse_amount
    except Exception as e:                 # e.g. a crashing example call at the bottom of the file
        print("PASSED 0/8")
        print(f"FAIL: importing your code raised {type(e).__name__}: {e}. "
              "Remove any code outside the function.")
        raise SystemExit
    cases = [
        ("UGX 1,250,000", 1250000),
        ("RWF 5000", 5000),
        ("  25,000 ugx ", 25000),
        ("1.5m", 1500000),
        ("20k", 20000),
        ("KES 1 200", 1200),
        ("Frw 3.000", 3000),
        ("UGX 750", 750),
    ]
    failed = []
    for text, expected in cases:
        try:
            got = parse_amount(text)
        except Exception as e:
            got = f"raised {type(e).__name__}: {e}"
        if got != expected:
            failed.append(f"parse_amount({text!r}) returned {got!r}, expected {expected!r}")
    print(f"PASSED {len(cases) - len(failed)}/{len(cases)}")
    for f in failed:
        print("FAIL:", f)
""").strip()


# ---------------------------------------------------------------- model calls
def call_llm(prompt: str) -> str:
    from google import genai
    from google.genai import types
    client = genai.Client(http_options=types.HttpOptions(   # reads GEMINI_API_KEY
        timeout=60_000, retry_options=types.HttpRetryOptions(attempts=3)))  # don't hang on stage
    try:
        return client.models.generate_content(model=MODEL, contents=prompt).text or ""
    except Exception as e:
        sys.exit(f"\nGemini call failed ({type(e).__name__}: {str(e)[:200]})\n"
                 "Network or model trouble. Re-run with --mock to show the loop offline.")


def local_llm(prompt: str) -> str:
    """On-device model served by Ollama on this machine. Nothing leaves the laptop."""
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps({"model": LOCAL_MODEL, "prompt": prompt, "stream": False,
                         "keep_alive": "30m",                  # stay loaded between calls
                         "options": {"temperature": 0.2, "num_predict": 600}}).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:     # CPU-only laptops are slow
            return json.load(r)["response"]
    except Exception as e:
        sys.exit(f"\nLocal model call failed ({type(e).__name__}: {e})\n"
                 f"Is Ollama running? Try: ollama serve  and  ollama pull {LOCAL_MODEL}\n"
                 "Or re-run with --mock to replay a saved run.")


def mock_llm_from_file():
    """Replays a run saved with --record, reply by reply. Same tests, so same path."""
    with open(MOCK_FILE) as f:
        saved = json.load(f)
    print(f"(replaying a recorded run of {saved['model']})")
    replies = iter(saved["replies"])
    return lambda prompt: next(replies)


def recording(llm, model):
    """Wraps a model so every reply is kept; main() saves them when the run finishes."""
    replies = []
    def wrapped(prompt):
        reply = llm(prompt)
        replies.append(reply)
        return reply
    wrapped.save = lambda: json.dump({"model": model, "replies": replies},
                                     open(MOCK_FILE, "w"), indent=2)
    return wrapped


# ---------------------------------------------------------------- environment
def extract_code(reply: str) -> str:
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", reply, re.S)
    return m.group(1) if m else reply


def run_tests(code: str) -> tuple[bool, str]:
    """The environment. Runs the agent's code against hidden tests in a temp dir.
    Not a sandbox: the code runs as you. Use a container for anything real."""
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "solution.py"), "w").write(code)
        open(os.path.join(d, "test_solution.py"), "w").write(TESTS)
        try:
            r = subprocess.run([sys.executable, "test_solution.py"], cwd=d,
                               capture_output=True, text=True, timeout=10)
            out = (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired:
            out = "FAIL: code timed out"
    report = [l for l in out.splitlines() if l.startswith(("PASSED", "FAIL"))]
    if any(l.startswith("PASSED") for l in report):
        out = "\n".join(report)              # drop anything the agent's own code printed
    passed = out.startswith("PASSED") and "FAIL" not in out
    return passed, out


# ---------------------------------------------------------------- the loop
def main(llm):
    lessons: list[str] = []          # long-term memory: this is what "improves"
    last = ""                        # short-term memory: the previous attempt and its failures
    for attempt in range(1, MAX_ATTEMPTS + 1):
        memory = "\n".join(f"- {l}" for l in lessons) or "(none yet)"
        prompt = f"{TASK}\n\nLessons from your previous attempts:\n{memory}{last}"

        code = extract_code(llm(prompt))                    # ACT
        passed, feedback = run_tests(code)                  # FEEDBACK
        score = feedback.splitlines()[0] if feedback else "?"
        print(f"\n=== Attempt {attempt}: {score} ===")

        if passed:
            print("All tests pass. Final solution:\n")
            print(code)
            return

        print("\n".join(feedback.splitlines()[1:]))
        if attempt == MAX_ATTEMPTS:
            break                                            # no retry left to use a lesson
        reflection = llm(                                    # REFLECT
            "You wrote this code:\n```python\n" + code + "\n```\n"
            "It failed these tests:\n" + feedback + "\n\n"
            "First, take one failing input and trace what your code does to it, line by line, "
            "to find where it goes wrong. Then, on a final line starting with 'Lesson:', "
            "state in one or two sentences the rule for handling the failing inputs correctly. "
            "Do not write code."
        )
        parts = re.split(r"\**lesson\**\s*:\**", reflection, flags=re.I)  # keep the lesson, drop the trace
        lesson = (parts[-1] if len(parts) > 1 else reflection.strip().splitlines()[-1]).strip(" *\n")
        lessons.append(lesson)
        last = (f"\n\nYour last attempt:\n```python\n{code}\n```\n"
                f"It failed these cases:\n{feedback}\nFix every failing case.")
        print(f"\nLesson stored: {lesson}")

    print("\nOut of attempts. Lessons learned:", *lessons, sep="\n- ")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="replay the saved run in mock_run.json, no model needed")
    ap.add_argument("--local", action="store_true", help="use an on-device model via Ollama instead of Gemini")
    ap.add_argument("--record", action="store_true", help="save this run to mock_run.json for --mock")
    args = ap.parse_args()

    if args.mock:
        llm = mock_llm_from_file()
    else:
        llm, model = (local_llm, LOCAL_MODEL) if args.local else (call_llm, MODEL)
        print(f"(model: {model})")
        if args.record:
            llm = recording(llm, model)
    main(llm)
    if args.record and not args.mock:
        llm.save()
        print(f"\nSaved this run to {MOCK_FILE}. Replay it with --mock.")