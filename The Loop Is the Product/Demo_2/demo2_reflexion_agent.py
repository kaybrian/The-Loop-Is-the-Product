"""
DevFest Demo 2: An agent that critiques itself and tries again.

The loop:  ACT (write code) -> FEEDBACK (run real tests) ->
           REFLECT (write a lesson about the failure) -> RETRY with lessons in memory.

No model weights change. The improvement lives in the memory of lessons.
The reward is objective: tests pass or they don't.

Run:   pip install anthropic
       export ANTHROPIC_API_KEY=...
       python demo2_reflexion_agent.py

Offline rehearsal (no API key, scripted model):  python demo2_reflexion_agent.py --mock
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import textwrap

MODEL = os.environ.get("DEMO_MODEL", "claude-sonnet-5-5")
MAX_ATTEMPTS = 4

TASK = textwrap.dedent("""
    Write a Python function `parse_amount(text: str) -> int` that turns a
    payment amount written by a person into an integer number of currency units.
    Return only the code in a single ```python block.
""").strip()

# The tests are the reward signal. The model never sees them; it only
# sees which ones failed. Deliberately full of real-world messiness.
TESTS = textwrap.dedent("""
    from solution import parse_amount
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
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(model=MODEL, max_tokens=1500,
                                 messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in msg.content if b.type == "text")


MOCK_SCRIPT = iter([
    # attempt 1: naive
    "```python\ndef parse_amount(text):\n    return int(''.join(c for c in text if c.isdigit()))\n```",
    "Suffixes like k and m multiply the number, and decimals were destroyed.",
    # attempt 2: handles suffixes, still breaks '3.000'
    "```python\nimport re\ndef parse_amount(text):\n    t = text.lower().replace(',', '').replace(' ', '')\n"
    "    t = re.sub(r'[a-z]+$', lambda m: m.group() if m.group() in ('k','m') else '', t)\n"
    "    t = re.sub(r'^[a-z]+', '', t)\n    mult = 1\n"
    "    if t.endswith('k'): mult, t = 1000, t[:-1]\n"
    "    elif t.endswith('m'): mult, t = 1000000, t[:-1]\n"
    "    return int(float(t) * mult)\n```",
    "A dot followed by exactly three digits with no suffix is a thousands separator, not a decimal.",
    # attempt 3: correct
    "```python\nimport re\ndef parse_amount(text):\n    t = text.lower().replace(',', '').replace(' ', '')\n"
    "    t = re.sub(r'^[a-z]+', '', t)\n    mult = 1\n"
    "    if t.endswith('k'): mult, t = 1000, t[:-1]\n"
    "    elif t.endswith('m'): mult, t = 1000000, t[:-1]\n"
    "    else: t = re.sub(r'[a-z]+$', '', t)\n"
    "    if mult == 1 and re.fullmatch(r'\\d{1,3}(\\.\\d{3})+', t):\n        t = t.replace('.', '')\n"
    "    return int(round(float(t) * mult))\n```",
])


def mock_llm(prompt: str) -> str:
    return next(MOCK_SCRIPT)


# ---------------------------------------------------------------- environment
def extract_code(reply: str) -> str:
    m = re.search(r"```python\s*(.*?)```", reply, re.S)
    return m.group(1) if m else reply


def run_tests(code: str) -> tuple[bool, str]:
    """The environment. Runs the agent's code against hidden tests in a temp dir."""
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "solution.py"), "w").write(code)
        open(os.path.join(d, "test_solution.py"), "w").write(TESTS)
        try:
            r = subprocess.run([sys.executable, "test_solution.py"], cwd=d,
                               capture_output=True, text=True, timeout=10)
            out = (r.stdout + r.stderr).strip()
        except subprocess.TimeoutExpired:
            out = "FAIL: code timed out"
    passed = out.startswith("PASSED") and "FAIL" not in out
    return passed, out


# ---------------------------------------------------------------- the loop
def main(llm):
    lessons: list[str] = []          # the agent's memory: this is what "improves"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        memory = "\n".join(f"- {l}" for l in lessons) or "(none yet)"
        prompt = f"{TASK}\n\nLessons from your previous attempts:\n{memory}"

        code = extract_code(llm(prompt))                    # ACT
        passed, feedback = run_tests(code)                  # FEEDBACK
        score = feedback.splitlines()[0] if feedback else "?"
        print(f"\n=== Attempt {attempt}: {score} ===")

        if passed:
            print("All tests pass. Final solution:\n")
            print(code)
            return

        print("\n".join(feedback.splitlines()[1:]))
        lesson = llm(                                        # REFLECT
            "You wrote this code:\n```python\n" + code + "\n```\n"
            "It failed these tests:\n" + feedback + "\n\n"
            "In one or two sentences, state the general lesson you should remember "
            "next time. Do not write code."
        ).strip()
        lessons.append(lesson)
        print(f"\nLesson stored: {lesson}")

    print("\nOut of attempts. Lessons learned:", *lessons, sep="\n- ")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="scripted model, no API key needed")
    args = ap.parse_args()
    main(mock_llm if args.mock else call_llm)