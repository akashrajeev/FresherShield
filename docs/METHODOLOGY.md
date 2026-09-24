# Scam-signal methodology

FresherShield gives every listing a **risk score from 0 to 100** and a level:
**low** (under 35), **caution** (35-59) or **high** (60+). The score starts at a
baseline of 20, and each signal adds or subtracts its weight. Every signal is shown
in the UI with its weight and, where it came from the web, the exact search result
that triggered it. Nothing is hidden behind a model.

This is a triage aid for a first-time job seeker, not a verdict about a company.

## Why these signals

Fake job offers aimed at freshers in India follow a small number of patterns that
show up again and again in police advisories and complaint forums: asking for a
registration/training/"refundable" deposit, recruiting only over WhatsApp or Telegram,
recruiters using gmail addresses, "no interview, direct joining" promises, and
typing/data-entry/"like and earn" work paying per day. Many also use the name of a
real, large employer on fake offer letters.

So we look in two places: **what the posting says**, and **what the rest of the web
says about the company**.

## Layer 1: the posting (free, no API calls)

Checked against the Google Jobs posting text, highlights and apply links (or the text
you paste in the "Check an offer I got" tab).

| Signal | Weight | Trigger |
|---|---:|---|
| Asks for money | +35 | registration/training/security/joining fee, deposit, "refundable", "pay Rs X" |
| Chat-app recruiting | +15 | WhatsApp or Telegram |
| Personal mobile as contact | +6 | a bare Indian mobile number in the posting |
| Hidden company | +12 | company listed as "Confidential" (web checks are skipped: nothing to search) |
| Free-email recruiter | +12 | gmail / yahoo / outlook / rediffmail address |
| No-interview promise | +20 | "no interview", "direct joining", "100% job guarantee" |
| Easy-money pattern | +20 | typing / data entry / copy-paste / likes + earn per day/week |
| Unrealistic pay | +15 | per-day or per-week income pitches, or pay at or above ~₹18 LPA / ₹1.5 L a month for a fresher role |
| Urgency | +8 | "limited seats", "apply today only" |
| No apply link | +10 | Google Jobs shows no apply option at all |
| Only an unfamiliar apply site | +8 | no known job board among the apply options |
| Listed on established boards | -5 | LinkedIn, Naukri, Indeed, foundit, Internshala, ... |

**Hard rule:** if the posting asks for money, the score is raised to at least 70
(high) whatever else is found. Legitimate employers do not charge candidates to be
hired.

## Layer 2: the web footprint (3 SerpApi searches per company, cached)

1. **Google complaint search** (`engine=google`, `gl=in`):
   `"<company>" scam OR fraud OR fake OR complaint`
2. **Bing complaint search** (`engine=bing`, `cc=IN`): the same query on a second,
   independent index. Scam reports are often thin; seeing the same complaint pages on
   two engines is stronger evidence than one engine alone.
3. **Google legitimacy search** (`engine=google`):
   `"<company>" company reviews employees` - used for the Knowledge Graph panel,
   employee-review rich snippets (AmbitionBox, Glassdoor, Indeed) and an official site.

A search result only counts as a complaint when its title or snippet **mentions the
company name** and **contains a scam word** (scam, fraud, fake, cheated, complaint,
beware...).

| Signal | Weight | Trigger |
|---|---:|---|
| Scam results found | +10 + 6 per unique result (max +40) | complaint results on Google and/or Bing |
| Confirmed on both engines | +10 | the same page shows up on Google and Bing |
| On complaint forums | +8 | ConsumerComplaints.in, Voxya, MouthShut, Reddit, Quora, Trustpilot... |
| Impersonation warnings | +10 | "fake offer letters in the name of X", "fraud alert", "beware of fake recruiters" |
| Nothing found | -10 | engines ran and returned no scam-linked results |
| Knowledge Graph entry | -12 | Google shows a company panel |
| Employee reviews | -12 (50+ reviews) / -6 / +8 if rating < 3.0 | review-site rich snippet |
| Official website | -6 | a result whose domain matches the company name |
| No footprint at all | +18 | no Knowledge Graph, no reviews and no official site |

### Impersonation is not a scam verdict

Large employers such as TCS, Infosys or Amazon return plenty of "fraud" results,
because scammers use their names. Those results are almost always the company's own
fraud-alert pages or news about impostors. FresherShield puts them in a separate
**impersonation risk** signal and tells the user to apply only through the official
careers page. It does not treat them as evidence against the company.

## Known limits

- **Name collisions.** Generic names ("Global Solutions") can match unrelated
  complaints. Evidence links are always shown so the user can judge.
- **New companies.** A real startup can have no footprint yet. "No footprint" is a
  warning, not proof, and it is weighted below a direct fee request.
- **English-only patterns.** Red-flag phrases are English; Hinglish/regional-language
  offers may slip through.
- **Search results change.** Results are cached locally (7 days by default) to save
  credits; a re-check after the TTL can differ.
- **Weights are hand-tuned**, not learned from a labelled dataset. They are
  deliberately simple so they can be read, argued with and changed in
  `app/scam.py`.

If you've been targeted: report at <https://cybercrime.gov.in> or call **1930**
(National Cyber Crime Helpline).
