# Demo 2: An agent that critiques itself and tries again

**File:** [`demo2_reflexion_agent.py`](demo2_reflexion_agent.py) · Part of [The Loop Is the Product](../README.md)

An LLM agent writes a parser for messy payment amounts. It fails some tests, writes itself a lesson about why, and tries again with those lessons in its prompt. No model weights change. What improves is the agent's memory of its own mistakes. This is inspired by [Reflexion](https://arxiv.org/abs/2303.11366).

## The loop

| Step | In this demo |
| --- | --- |
| **Act** | The model writes `parse_amount()` |
| **Feedback** | Hidden tests run against the code. The model only sees which cases failed |
| **Reflect** | The model traces a failing input through its code, then writes a one- or two-sentence lesson |
| **Retry** | The next attempt gets every lesson so far, plus its last code and the cases that failed |

The agent gets up to 6 attempts. You can change this with `DEMO_ATTEMPTS` (see [Settings](#settings)).

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

## Before you start

You need **Python 3.9 or newer**. What else you need depends on which mode you run:

| Mode | Command | Needs | Good for |
| --- | --- | --- | --- |
| **Offline** | `--mock` | Nothing else | A first look, and the backup if the venue Wi-Fi fails |
| **Gemini** | *(no flag)* | `google-genai` and a free API key | The best results. Usually passes all 8 tests |
| **On-device** | `--local` | Ollama and a 1.9 GB model | No key and no internet. Nothing leaves your laptop |

Run every command from the repo's top folder.

## Mode 1: Offline

1. Run it:
   ```bash
   python Demo_2/demo2_reflexion_agent.py --mock
   ```

This replays a real model run saved in [`mock_run.json`](mock_run.json), reply by reply. You see the whole loop with genuine model output, and no model is involved. The tests are the same every time, so the replay follows exactly the path the real model took.

## Mode 2: Gemini

1. **Install the Gemini SDK**, if you haven't run `pip install -r requirements.txt` already:
   ```bash
   pip install google-genai
   ```
2. **Get a free API key** from [Google AI Studio](https://aistudio.google.com/apikey).
3. **Create your settings file:**
   ```bash
   cp .env.example .env
   ```
   On Windows, use `copy .env.example .env`.
4. **Add your key.** Open `.env` and replace `your_key_here` with it. `.env` is git-ignored, so your key stays out of the repo. The script reads `.env` by itself, so there's nothing to export.
5. **Run it:**
   ```bash
   python Demo_2/demo2_reflexion_agent.py
   ```

The default model is `gemini-3.5-flash`. To use another one, change `DEMO_MODEL` in `.env`, or set it for a single run:

```bash
DEMO_MODEL=gemini-pro-latest python Demo_2/demo2_reflexion_agent.py
```

Every live run is a little different. Sometimes the agent gets there in two attempts, sometimes more, and sometimes it runs out of attempts and prints the lessons it learned. If Gemini is busy, the script gives up after a few tries and suggests `--mock`, so it never hangs on stage.

## Mode 3: On-device

The agent runs on a small open model on your own laptop, through [Ollama](https://ollama.com). The default is **Qwen2.5-Coder 3B**, a small model trained for code.

1. **Install Ollama** from [ollama.com/download](https://ollama.com/download) and open the app. On Linux, run `ollama serve` in its own terminal instead.
2. **Check that it's running:**
   ```bash
   ollama --version
   ```
3. **Download the model** (about 1.9 GB, one time):
   ```bash
   ollama pull qwen2.5-coder:3b
   ```
4. **Run it:**
   ```bash
   python Demo_2/demo2_reflexion_agent.py --local
   ```

To try another model, pull it and set `LOCAL_MODEL`, for example `LOCAL_MODEL=gemma3:1b`. Small models are slower and less reliable than Gemini, especially on a laptop without a GPU. On an 8 GB Intel Mac, a full run with the 3B model takes 3 to 8 minutes and usually reaches 6/8 or 7/8 rather than 8/8. Models of 1.5B and smaller rarely get past 6/8 on this task.

## Record your own offline run

Add `--record` to any real run. When the run finishes, it overwrites `mock_run.json`, and `--mock` replays it from then on:

```bash
python Demo_2/demo2_reflexion_agent.py --local --record
```

This is the safest way to show a real run on stage: record a good one before the talk, then replay it with `--mock`.

## Settings

Set these in `.env`, or in your shell for a single run:

| Setting | Default | What it does |
| --- | --- | --- |
| `GEMINI_API_KEY` | *(none)* | Your Gemini key, needed for Gemini mode |
| `DEMO_MODEL` | `gemini-3.5-flash` | Which Gemini model to use |
| `LOCAL_MODEL` | `qwen2.5-coder:3b` | Which Ollama model `--local` uses |
| `DEMO_ATTEMPTS` | `6` | How many attempts the agent gets |

## What you'll see (mock mode)

```
(replaying a recorded run of qwen2.5-coder:3b)

=== Attempt 1: PASSED 6/8 ===
FAIL: parse_amount('1.5m') returned 15, expected 1500000
FAIL: parse_amount('20k') returned 20, expected 20000

Lesson stored: The code should check for the presence of 'm' or 'k' suffixes and multiply the result by 1,000,000 or 1,000 respectively before converting it to an integer.

=== Attempt 2: PASSED 7/8 ===
FAIL: parse_amount('1.5m') returned 15000000, expected 1500000
...
=== Attempt 6: PASSED 7/8 ===
Out of attempts. Lessons learned:
...
```

This is a real run of a 3B model on a CPU-only laptop. The lesson from attempt 1 fixes `20k`. Then the model gets stuck on `1.5m`: it keeps writing lessons about the decimal point but can't turn them into working code. That's a useful talking point. The loop makes a small model better, but the model's ability still sets the ceiling. Run the same loop with Gemini and it usually reaches 8/8.

## Things to try

- **Swap in your own task.** Any problem where you can **check the result automatically** works: a schema validator, a business rule, a reconciliation check. Edit `TASK` and `TESTS`.
- **Weaken the tests** to two or three cases. Does the agent "pass" with code that's actually wrong? That's reward hacking in miniature.
- **Make memory persistent.** Save the `lessons` list to a file so the agent remembers across runs.
- **Drop the lessons.** Retry without them and compare how many attempts it takes.

## Safety note

> **Warning:** the demo runs model-generated code in a temporary directory with a 10-second timeout. That's fine for a demo, but use a proper sandbox (a container, for example) before running untrusted generated code anywhere that matters.
