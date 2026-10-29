# Demo 2: An agent that critiques itself and tries again

**File:** [`demo2_reflexion_agent.py`](demo2_reflexion_agent.py) · Part of [The Loop Is the Product](../README.md)

An LLM agent writes a parser for messy payment amounts. It fails some tests, writes itself a lesson about why, and tries again with those lessons in its prompt. No model weights change. What improves is the agent's memory of its own mistakes. This is inspired by [Reflexion](https://arxiv.org/abs/2303.11366).

## The loop

| Step | In this demo |
| --- | --- |
| **Act** | The model writes `parse_amount()` |
| **Feedback** | Hidden tests run against the code. The model only sees which cases failed |
| **Reflect** | The model writes a one- or two-sentence lesson about the failure |
| **Retry** | The next attempt gets every lesson so far in its prompt |

The agent gets up to 4 attempts (`MAX_ATTEMPTS`).

## The task

Write `parse_amount(text: str) -> int`, which turns a human-written amount into an integer. The hidden tests:

| Input | Expected |
| --- | --- |
| `"UGX 1,250,000"` | `1250000` |
| `"RWF 5000"` | `5000` |
| `"  25,000 ugx "` | `25000` |
| `"1.5m"` | `1500000` |
| `"20k"` | `20000` |
| `"KES 1 200"` | `1200` |
| `"Frw 3.000"` | `3000` |
| `"UGX 750"` | `750` |

The reward is objective: the tests pass or they don't.

## Run it offline (no API key)

```bash
python Demo_2/demo2_reflexion_agent.py --mock
```

This uses a scripted fake model, so you see the whole loop without an API key or internet. It's also the backup if the venue Wi-Fi fails.

## Run it with a real model

From the repo root, install the dependencies:

```bash
pip install -r requirements.txt
```

Copy the example env file, then put your Gemini API key in `.env` (get one free at [Google AI Studio](https://aistudio.google.com/apikey)):

```bash
cp .env.example .env
```

Load it into your shell (the script reads ordinary environment variables):

```bash
set -a && source .env && set +a
```

```bash
python Demo_2/demo2_reflexion_agent.py
```

The default model is `gemini-3.5-flash`. To use a different one, change `DEMO_MODEL` in `.env`, or set it for a single run:

```bash
DEMO_MODEL=gemini-pro-latest python Demo_2/demo2_reflexion_agent.py
```

`.env` is git-ignored, so your key stays out of the repo.

Every live run is a little different. Sometimes the agent gets there in two attempts, sometimes four, and sometimes it runs out of attempts and prints the lessons it learned.

## What you'll see (mock mode)

```
=== Attempt 1: PASSED 6/8 ===
FAIL: parse_amount('1.5m') returned 15, expected 1500000
FAIL: parse_amount('20k') returned 20, expected 20000

Lesson stored: Suffixes like k and m multiply the number, and decimals were destroyed.

=== Attempt 2: PASSED 7/8 ===
FAIL: parse_amount('Frw 3.000') returned 3, expected 3000

Lesson stored: A dot followed by exactly three digits with no suffix is a thousands separator, not a decimal.

=== Attempt 3: PASSED 8/8 ===
All tests pass. Final solution:
...
```

## Things to try

- **Swap in your own task.** Any problem where you can **check the result automatically** works: a schema validator, a business rule, a reconciliation check. Edit `TASK` and `TESTS`.
- **Weaken the tests** to two or three cases. Does the agent "pass" with code that's actually wrong? That's reward hacking in miniature.
- **Make memory persistent.** Save the `lessons` list to a file so the agent remembers across runs.
- **Drop the lessons.** Retry without them and compare how many attempts it takes.

## Safety note

> ⚠️ The demo runs model-generated code in a temporary directory with a 10-second timeout. That's fine for a demo, but use a proper sandbox (a container, for example) before running untrusted generated code anywhere that matters.
