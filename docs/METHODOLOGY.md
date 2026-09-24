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
| Unrealistic pay | +15 | per-day or per-week income pitches, or pay at or above ~₹18 LPA / ₹1.5 L a month for a fresher role whose type we can't tell |
| Pay far above the role's fresher range | +20 | stated pay is more than twice the top of the usual fresher range for that kind of role (see table below) |
| Urgency | +8 | "limited seats", "apply today only" |
| No apply link | +10 | Google Jobs shows no apply option at all |
| Only an unfamiliar apply site | +8 | no known job board among the apply options |
| Listed on established boards | -5 | LinkedIn, Naukri, Indeed, foundit, Internshala, ... |

Every rule also has a Hindi and Hinglish version ("registration fees jama karo",
"रजिस्ट्रेशन फीस जमा करें", "bina interview joining", "घर बैठे रोज़ ₹1500 कमाएं"), because
fake offers are forwarded on WhatsApp in these forms. A fee mention that is negated in
the same clause ("No registration fee is charged", "कोई फीस नहीं") is not counted.

**Hard rule:** if the posting asks for money, the score is raised to at least 70
(high) whatever else is found. Legitimate employers do not charge candidates to be
hired.

## Layer 2: the web footprint (5 SerpApi searches per company, cached)

1. **Google complaint search** (`engine=google`, `gl=in`):
   `"<company>" scam OR fraud OR fake OR complaint`
2. **Bing complaint search** (`engine=bing`, `cc=IN`): the same query on a second,
   independent index. Scam reports are often thin; seeing the same complaint pages on
   two engines is stronger evidence than one engine alone.
3. **Google legitimacy search** (`engine=google`): `"<company>" reviews` - used for
   the Knowledge Graph panel and review rich snippets (AmbitionBox, Glassdoor, Indeed,
   Justdial).
4. **Google Maps search** (`engine=google_maps`, `type=search`, whole-India map view):
   the company's short name. Real employers usually have offices on Maps with
   reviews; fee-scam "companies" usually have none. Only places whose name matches the
   company count. The place category is also read: an "Employment agency" or
   "Training institute" is not the employer the offer claims to be.

5. **Google News search** (`engine=google_news`, `gl=in`):
   `"<company>" fake job OR scam OR fraud OR arrested`. A news report of a busted fake-job
   racket is much stronger evidence than a forum post. Only headlines that mention the
   company, a fraud word (fake, racket, duped, arrested...) **and** a jobs word (job,
   recruitment, offer letter, aspirants...) count, so "shares fall after fraud
   allegations" does not. Headlines about fake offers "in the name of" a company are
   impersonation warnings. If the company is clearly established (Knowledge Graph entry,
   employee reviews, a busy Maps listing) or its name is already known to be misused, all
   job-fraud news is treated as impersonation (+6): a live run showed "held for fake job
   offer in Infosys" style headlines are about scams run in a big brand's name, not by it.

Legal suffixes ("Private Limited", "Pvt Ltd", "LLP") are stripped before searching:
long legal names make engines drop the quotes and return unrelated pages. The
legitimacy footprint (official site, reviews, registry record, Knowledge Graph) is
read from **all** results of the three web searches plus the Maps listing, and an apply link on the company's
own domain also counts as an official site.

### What is *not* counted as a complaint

Early live runs showed three kinds of false positive, so these are filtered out:

- **Job-board and aggregator pages** (Shine, Naukri, Jooble, Jobrapido...). Their
  menus carry a "Fraud Alert" link, which says nothing about the employer.
- **"Fraud" as a job function or product** - "Fraud Analyst", "fraud detection",
  "fraud risk strategy".
- **The company's own site**, unless it is a fraud-alert page (that becomes an
  impersonation signal). For YouTube/Instagram only the title is read, because their
  snippets mix in other videos.

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
| Official website | -6 | a result (or apply link) whose domain matches the company name |
| Registry record | -6, or +10 if incorporated under a year ago | MCA company data on Zaubacorp / Tofler etc.; the incorporation date is read from the snippet |
| Training institute | +12 | results describe the "employer" as an institute/academy/classes - "job + training" offers often mean course fees |
| On Google Maps | -10 (20+ reviews in total) / -4, or +6 if rated under 3.0 with 10+ reviews | Maps listings whose name matches the company |
| Job-fraud news | +12 + 6 per report (max +30) | Google News headlines tying the name to a fake-job racket, arrests, duped aspirants |
| Impostor news | +6 | news warning of fake offers using the company's name |
| No Maps listing | +4 | Maps returned no place with this name (weak: remote-first startups may have none) |
| Maps says placement agency | +6 | category like "Employment agency", "Placement consultant", "Manpower" |
| Maps says training institute | +10 | category like "Training institute", "Computer training school", "Academy". If the web results already say institute, the two merge into one +15 signal instead of adding up to +22 |
| No footprint at all | +18 | no Knowledge Graph, reviews, registry record, official site or Maps listing |

### Contact domains (free, runs after the web layer)

Once the company's real domain is known (official site, Knowledge Graph website or an
apply link on its own domain), every email address and link in the offer is compared
with it:

| Signal | Weight | Trigger |
|---|---:|---|
| Look-alike domain | +25 | a domain containing the brand (`infosys-careers.in`) or 1-2 letters off it (`wipr0.com`) that isn't the real one |
| Brand in a free-mail address | +12 | `infosys.recruit.hr@gmail.com` |
| Company's own domain | -6 | contact address on the real domain |

Unknown domains with no brand resemblance are left alone: a small company may simply
use a domain we couldn't verify.

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
- **Languages.** Red-flag phrases cover English, Hindi (Devanagari) and Hinglish
  (romanised Hindi). Other regional languages (Tamil, Telugu, Malayalam...) can still
  slip through.
- **Search results change.** Results are cached locally (7 days by default) to save
  credits; a re-check after the TTL can differ.
- **Weights are hand-tuned**, not learned from a labelled dataset. They are
  deliberately simple so they can be read, argued with and changed in
  `app/scam.py`.

If you've been targeted: report at <https://cybercrime.gov.in> or call **1930**
(National Cyber Crime Helpline).

### Salary reality check

The posting's pay is turned into annual CTC (monthly figures x12; sums under ₹50,000 are
ignored so fees don't count as pay). If the title matches a known role family, the pay is
compared to that family's usual fresher range. It gets flagged only above **twice** the top
of that range, so a well-paid genuine offer passes. The source link is shown with the flag.

| Role family | Usual fresher range | Flag above | Source |
|---|---|---|---|
| Data entry / typing / form filling | ₹1.2-2.4 LPA (₹10-20k a month) | ₹4.8 LPA | [salaryctc.com](https://salaryctc.com/data-entry-operator-salary/) |
| Customer support / BPO / telecalling | ₹1.7-3.5 LPA | ₹7 LPA | [hyring.com](https://hyring.com/jobseeker-toolkit/salary/customer-support-executive-salary-in-india) |
| Digital marketing | ₹3-6.5 LPA | ₹13 LPA | [growai.in](https://growai.in/digital-marketing-fresher-salary-india-2026/) |
| Software / engineering / data | ₹3.5-15 LPA (services to top product firms) | ₹30 LPA | [simpliaxis.com](https://www.simpliaxis.com/resources/software-engineer-salary-in-india) |

These are rough ranges from public salary guides, not official data.
