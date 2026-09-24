# Evaluation

`eval/dataset.jsonl` is a labelled set of **40 job messages**: 20 scams and 20 genuine
postings, in English (32), Hindi (4) and Hinglish (4). `eval/run_eval.py` runs the
**posting layer only** on each one (no SerpApi calls, no credits) and counts a message as
flagged when its risk level is *caution* or *high*. CI runs it on every push through
`tests/test_eval.py` and fails if recall drops below 0.95 or precision below 0.90.

```bash
python eval/run_eval.py
```

## Current result

| | Flagged | Not flagged |
|---|---:|---:|
| **Scam (20)** | 20 | 0 |
| **Genuine (20)** | 1 | 19 |

Precision **0.95**, recall **1.00**, F1 **0.98**, accuracy **0.975**
(English 31/32, Hindi 4/4, Hinglish 4/4). Raw output: `eval/results.json`.

The one false positive (`g09`) is a genuine QA posting that says interview updates will
come "on email and WhatsApp". A WhatsApp mention alone scores 35, the bottom edge of
*caution*. We left it as a miss instead of tuning the weight to this set: the web
layer (Maps listing, reviews, official site) pulls a real company back down, and a
fresher double-checking a real job costs far less than trusting a fake one.

## What the set is, and what it is not

- **Scam messages** are composites written from the patterns described in public fraud
  advisories and complaint threads: fees and "refundable" deposits, WhatsApp/Telegram
  recruiting, free-mail HR, no-interview promises, earn-per-day tasks, "job + course fee"
  institutes. No real person's message or number is included; numbers are masked.
- **Genuine postings** are written in the style of real campus-hiring and job-board
  listings, including hard cases: postings that *mention* fees to say none are charged
  (English, Hindi, Hinglish), stipends, incentives, and WhatsApp used for updates.
- The set was written by the same team that wrote the rules, so these numbers measure
  **regressions and coverage of known patterns**, not real-world accuracy. A real
  benchmark needs messages reported by actual job seekers; contributions are welcome
  (add a line to `eval/dataset.jsonl` with `id`, `label`, `lang`, `text`).
- The web layer (Google, Bing, Google Maps) is not part of this score, because its
  results change daily and each check costs credits. [EXAMPLES.md](EXAMPLES.md) shows it
  end to end.
