# Worked examples

Two end-to-end runs of the scam check, with the real output. Both were run on
24 September 2026 against live SerpApi data (4 searches each: Google complaint
search, Bing complaint search, Google reviews/legitimacy search, Google Maps). Once
cached they re-run with `FS_OFFLINE=1` at no cost. Search results change over time, so
a re-run after the cache expires can differ.

## 1. A fee-scam offer pasted from WhatsApp

The message is a composite of the patterns in real fake-offer messages sent to freshers
(a "refundable" registration fee, WhatsApp HR, a gmail address, no interview, "today
only"). **The company name "Quikhire Global Staffing" is invented** so no real business is
named, and the phone number is masked.

```text
Congratulations!! You are shortlisted for Work From Home Data Entry job at Quikhire Global Staffing.
Salary Rs 28,000/month, no experience needed, no interview, direct joining.
Pay Rs 1,999 registration fee (100% refundable) to confirm your seat. Limited slots.
Contact HR Neha on WhatsApp 98xxxxxx21 or quikhire.hr@gmail.com today only.
```

Request (what the "Check an offer I got" tab sends):

```bash
curl -s localhost:8000/api/check -H 'Content-Type: application/json' \
  -d '{"company": "Quikhire Global Staffing", "offer_text": "<message above>", "lang": "en"}'
```

Result: **HIGH risk, 100/100.** Asks for money up front. Real employers in India do not charge freshers to get hired.

| Weight | Signal | Evidence / detail |
|---:|---|---|
| +35 | Asks for money (fee / deposit / payment) | …/month, no experience needed, no interview, direct joining. Pay Rs 1,999 registration fee (100% refundable) to confirm your seat… |
| +20 | Promises a job without an interview | …bal Staffing. Salary Rs 28,000/month, no experience needed, no interview, direct joining. Pay Rs 1,999 registration fee (100% refund… |
| +18 | No Knowledge Graph, reviews, registry record, official website or Maps listing found | Brand-new or non-existent companies are a common scam pattern. Not proof on its own. |
| +15 | Recruiting over WhatsApp/Telegram instead of a company channel | …le) to confirm your seat. Limited slots. Contact HR Neha on WhatsApp 98xxxxxx21 or quikhire.hr@gmail.com today only. |
| +12 | Recruiter uses a free email address (gmail/yahoo) | …t. Limited slots. Contact HR Neha on WhatsApp 98xxxxxx21 or quikhire.hr@gmail.com today only. |
| +8 | High-pressure urgency | …99 registration fee (100% refundable) to confirm your seat. Limited slots. Contact HR Neha on WhatsApp 98xxxxxx21 or quikhire.hr@gmai… |
| +4 | No Google Maps listing under this name | Most employers with a real office have one. Remote-first startups may not, so this is weak on its own. |
| -10 | No scam or fraud complaints tied to this name on Google or Bing |  |

Engines queried: google, bing, google_maps.

- The **posting text** alone is enough for a high verdict: a fee request is a hard rule
  (the score is raised to at least 70), and WhatsApp HR, a gmail recruiter, "no
  interview" and urgency add to it.
- The **web layer** found no complaints (an invented name has none), but also no
  Knowledge Graph panel, no reviews, no registry record, no official site and **no Google
  Maps listing**. A real employer almost always has at least one of these.

"Copy as text" / "Share on WhatsApp" output:

```text
🛡️ FresherShield: Quikhire Global Staffing
Verdict: HIGH RISK (100/100)
Asks for money up front. Real employers in India do not charge freshers to get hired.

Why:
⚠️ Asks for money (fee / deposit / payment) (+35)
⚠️ Promises a job without an interview (+20)
⚠️ No Knowledge Graph, reviews, registry record, official website or Maps listing found (+18)
⚠️ Recruiting over WhatsApp/Telegram instead of a company channel (+15)
⚠️ Recruiter uses a free email address (gmail/yahoo) (+12)
⚠️ High-pressure urgency (+8)
⚠️ No Google Maps listing under this name (+4)
✅ No scam or fraud complaints tied to this name on Google or Bing (-10)

Never pay to get a job. Report fraud at cybercrime.gov.in or call 1930.
Checked with FresherShield: https://github.com/akashrajeev/FresherShield
```

The same export in Hindi (`"lang": "hi"`), for sending to family:

```text
🛡️ FresherShield: Quikhire Global Staffing
नतीजा: ज़्यादा जोखिम (100/100)
पहले पैसे माँगे जा रहे हैं। भारत में असली कंपनियाँ फ्रेशर्स से नौकरी के लिए पैसे नहीं लेतीं।

क्यों:
⚠️ पैसे माँगता है (फ़ीस / डिपॉज़िट / पेमेंट) (+35)
⚠️ बिना इंटरव्यू नौकरी का वादा (+20)
⚠️ न Knowledge Graph, न रिव्यू, न रजिस्ट्री, न वेबसाइट, न Google Maps लिस्टिंग मिली (+18)
⚠️ कंपनी के चैनल की जगह WhatsApp/Telegram पर भर्ती (+15)
⚠️ रिक्रूटर फ्री ईमेल (gmail/yahoo) इस्तेमाल करता है (+12)
⚠️ जल्दबाज़ी का दबाव (+8)
⚠️ इस नाम से Google Maps पर कोई लिस्टिंग नहीं (+4)
✅ Google + Bing पर इस नाम से जुड़ी कोई स्कैम या फ्रॉड शिकायत नहीं (-10)

नौकरी पाने के लिए कभी पैसे न दें। फ्रॉड की शिकायत cybercrime.gov.in पर करें या 1930 पर कॉल करें।
FresherShield से जाँचा गया: https://github.com/akashrajeev/FresherShield
```

## 2. A real company whose name scammers use: Infosys

```bash
curl -s localhost:8000/api/check -H 'Content-Type: application/json' -d '{"company": "Infosys"}'
```

Result: **CAUTION, 38/100.** Real company, but its name is used by impostors. Apply only via the official careers page.

| Weight | Signal | Evidence / detail |
|---:|---|---|
| +16 | 1 search result(s) link this company name to scam/fraud complaints (Google) | [Reddit: Infosys Biggest SCAM Till Date : r/it](https://www.reddit.com/r/it/comments/1sxy5n3/infosys_biggest_scam_till_date/) |
| +10 | Scammers are known to use this company's name (fake offer letters / fraud alerts) | [infosys.com: Disclaimer - Recruitment Fraud Alert](https://www.infosys.com/careers/apply/recruitment-fraud-alert.html)<br>[infosys.org: Fraud Alert / Infosys](https://www.infosys.org/infosys-foundation/fraud-alert.html)<br>[infosys.com: Infosys Complaints Management](https://www.infosys.com/services/experience-transformation/service-offerings/complaints-management.html) |
| +8 | Discussed on complaint/review forums: Reddit | [Reddit: Infosys Biggest SCAM Till Date : r/it](https://www.reddit.com/r/it/comments/1sxy5n3/infosys_biggest_scam_till_date/) |
| -6 | Has its own website (infosys.com) | [infosys.com: Disclaimer - Recruitment Fraud Alert](https://www.infosys.com/careers/apply/recruitment-fraud-alert.html) |
| -10 | On Google Maps: 20 listing(s), 8,535 reviews, top rated 4.1/5 | [Google Maps: Infosys Limited](https://www.google.com/maps/search/?api=1&query=Infosys+Limited&query_place_id=ChIJLXKxtIs1bDkR_FLn-e-4lLE)<br>[Google Maps: Infosys Development Centre](https://www.google.com/maps/search/?api=1&query=Infosys+Development+Centre&query_place_id=ChIJpd3BEA1bOToRRuauNsok42U)<br>[Google Maps: Infosys Indore](https://www.google.com/maps/search/?api=1&query=Infosys+Indore&query_place_id=ChIJcwrkCxwCYzkRz3sptFDvHVU) |

Engines queried: google, bing, google_maps.

- Google and Bing return "fraud" results for Infosys, but the ones on Infosys's own
  domains are **recruitment-fraud-alert pages**. FresherShield files those as
  *impersonation risk* (scammers use the name), not as complaints against the company.
- **Google Maps** shows many Infosys offices with thousands of reviews: strong evidence
  the company is real.
- A Reddit thread with "scam" in its title is still counted and linked so the user can
  read it and judge. That keeps the score at *caution*, and the headline tells the
  fresher what to do: apply only through the official careers page.

Plain-text export:

```text
🛡️ FresherShield: Infosys
Verdict: CAUTION (38/100)
Real company, but its name is used by impostors. Apply only via the official careers page.

Why:
⚠️ 1 search result(s) link this company name to scam/fraud complaints (Google) (+16)
⚠️ Scammers are known to use this company's name (fake offer letters / fraud alerts) (+10)
⚠️ Discussed on complaint/review forums: Reddit (+8)
✅ Has its own website (infosys.com) (-6)
✅ On Google Maps: 20 listing(s), 8,535 reviews, top rated 4.1/5 (-10)

Evidence:
- Reddit: https://www.reddit.com/r/it/comments/1sxy5n3/infosys_biggest_scam_till_date/
- infosys.com: https://www.infosys.com/careers/apply/recruitment-fraud-alert.html
- infosys.org: https://www.infosys.org/infosys-foundation/fraud-alert.html
- infosys.com: https://www.infosys.com/services/experience-transformation/service-offerings/complaints-management.html

Never pay to get a job. Report fraud at cybercrime.gov.in or call 1930.
Checked with FresherShield: https://github.com/akashrajeev/FresherShield
```
