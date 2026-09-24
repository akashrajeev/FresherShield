"""Report translations (English, Hindi, Malayalam) and a plain-text export.

Fake job offers reach freshers on WhatsApp, often in Hindi or a regional language, and
the people they ask before paying (parents, friends) may not read English. So the
verdict, headline and every signal label can be shown in Hindi or Malayalam, and the
whole report can be copied as plain text to paste into a chat.

Only fixed strings are translated. Company names, search-result titles, snippets and
links stay as they are. Signal labels are rebuilt from `Signal.params`, so the numbers
and names in them match the English report exactly.

The Hindi and Malayalam strings were drafted with an AI assistant and kept short and
plain; corrections from native speakers are welcome.
"""
from __future__ import annotations

LANGS = {"en": "English", "hi": "हिंदी", "ml": "മലയാളം"}
REPO_URL = "https://github.com/akashrajeev/FresherShield"

LEVELS = {
    "en": {"low": "Low risk", "caution": "Caution", "high": "High risk", "unknown": "Unknown"},
    "hi": {"low": "कम जोखिम", "caution": "सावधान", "high": "ज़्यादा जोखिम", "unknown": "पता नहीं"},
    "ml": {"low": "കുറഞ്ഞ അപകടസാധ്യത", "caution": "ജാഗ്രത", "high": "ഉയർന്ന അപകടസാധ്യത", "unknown": "വ്യക്തമല്ല"},
}

HEADLINES = {
    "hi": {
        "fee": "पहले पैसे माँगे जा रहे हैं। भारत में असली कंपनियाँ फ्रेशर्स से नौकरी के लिए पैसे नहीं लेतीं।",
        "high": "कई स्कैम संकेत मिले। दस्तावेज़ या पैसे देने से पहले खुद जाँच करें।",
        "caution_real": "कंपनी असली है, पर ठग इसके नाम का इस्तेमाल करते हैं। सिर्फ़ आधिकारिक करियर पेज से अप्लाई करें।",
        "caution": "कुछ चेतावनी संकेत हैं। कंपनी की आधिकारिक वेबसाइट देखें और अप्लाई करने के लिए कभी पैसे न दें।",
        "low_watch": "कुल मिलाकर जोखिम कम है, पर यह ज़रूर जाँचें: {label}",
        "low_imp": "असली लगती है। इसके नाम का कभी-कभी गलत इस्तेमाल होता है, इसलिए सिर्फ़ आधिकारिक रास्ते से अप्लाई करें।",
        "low_clean": "पोस्टिंग में या वेब पर कोई स्कैम संकेत नहीं मिला।",
        "unknown": "फ़ैसला करने के लिए पर्याप्त जानकारी नहीं है।",
    },
    "ml": {
        "fee": "മുൻകൂറായി പണം ചോദിക്കുന്നു. ഇന്ത്യയിലെ യഥാർത്ഥ കമ്പനികൾ ഫ്രഷേഴ്സിനോട് ജോലിക്ക് പണം വാങ്ങാറില്ല.",
        "high": "പല തട്ടിപ്പ് സൂചനകളും ഉണ്ട്. രേഖകളോ പണമോ നൽകുന്നതിന് മുമ്പ് സ്വയം പരിശോധിക്കുക.",
        "caution_real": "കമ്പനി യഥാർത്ഥമാണ്, പക്ഷേ തട്ടിപ്പുകാർ ഇതിന്റെ പേര് ഉപയോഗിക്കുന്നു. ഔദ്യോഗിക കരിയർ പേജ് വഴി മാത്രം അപേക്ഷിക്കുക.",
        "caution": "ചില മുന്നറിയിപ്പ് സൂചനകളുണ്ട്. കമ്പനിയുടെ ഔദ്യോഗിക വെബ്സൈറ്റ് പരിശോധിക്കുക, അപേക്ഷിക്കാൻ ഒരിക്കലും പണം നൽകരുത്.",
        "low_watch": "മൊത്തത്തിൽ അപകടസാധ്യത കുറവാണ്, പക്ഷേ ഇത് പരിശോധിക്കുക: {label}",
        "low_imp": "യഥാർത്ഥമാണെന്ന് തോന്നുന്നു. ഇതിന്റെ പേര് ചിലപ്പോൾ ദുരുപയോഗം ചെയ്യപ്പെടുന്നു, അതിനാൽ ഔദ്യോഗിക വഴികളിലൂടെ മാത്രം അപേക്ഷിക്കുക.",
        "low_clean": "പോസ്റ്റിംഗിലോ വെബിലോ തട്ടിപ്പ് സൂചനകളൊന്നും കണ്ടെത്തിയില്ല.",
        "unknown": "വിലയിരുത്താൻ ആവശ്യമായ വിവരങ്ങളില്ല.",
    },
}

# Signal labels by signal id. {placeholders} come from Signal.params.
LABELS = {
    "hi": {
        "fee": "पैसे माँगता है (फ़ीस / डिपॉज़िट / पेमेंट)",
        "chat_contact": "कंपनी के चैनल की जगह WhatsApp/Telegram पर भर्ती",
        "phone_contact": "संपर्क के लिए निजी मोबाइल नंबर दिया है",
        "generic_email": "रिक्रूटर फ्री ईमेल (gmail/yahoo) इस्तेमाल करता है",
        "no_interview": "बिना इंटरव्यू नौकरी का वादा",
        "easy_money": "आसान कमाई वाला काम (टाइपिंग, लाइक्स, फ़ोन से डेटा एंट्री)",
        "urgency": "जल्दबाज़ी का दबाव",
        "hidden_company": "कंपनी का नाम छिपाया गया है (\"Confidential\")",
        "pay": "बिना अनुभव वाली नौकरी के लिए सैलरी असामान्य रूप से ज़्यादा",
        "no_apply": "कहीं भी अप्लाई लिंक नहीं है",
        "boards": "जाने-माने जॉब बोर्ड पर लिस्टेड: {boards}",
        "unknown_apply": "अप्लाई करने का एकमात्र रास्ता एक अनजान वेबसाइट है",
        "web_scam": "{n} सर्च नतीजे इस कंपनी के नाम को स्कैम/फ्रॉड शिकायतों से जोड़ते हैं ({engines})",
        "complaint_sites": "शिकायत/रिव्यू फ़ोरम पर चर्चा: {sites}",
        "impersonation": "ठग इस कंपनी के नाम का इस्तेमाल करते हैं (नकली ऑफ़र लेटर / फ्रॉड अलर्ट)",
        "web_clean": "{engines} पर इस नाम से जुड़ी कोई स्कैम या फ्रॉड शिकायत नहीं",
        "kg": "Google पर कंपनी का Knowledge Graph पैनल है",
        "reviews": "{source} पर रिव्यू मिले {stats}",
        "registry": "कंपनी रजिस्ट्री में दर्ज (MCA डेटा, {source})",
        "official_site": "कंपनी की अपनी वेबसाइट है ({domain})",
        "institute": "सीधी नियोक्ता कंपनी नहीं, ट्रेनिंग इंस्टीट्यूट या अकादमी लगती है",
        "no_footprint": "न Knowledge Graph, न रिव्यू, न रजिस्ट्री, न वेबसाइट, न Google Maps लिस्टिंग मिली",
        "maps": "Google Maps पर {n} लिस्टिंग {stats}",
        "maps_absent": "इस नाम से Google Maps पर कोई लिस्टिंग नहीं",
        "maps_agency": "Google Maps पर यह \"{type}\" है, नियोक्ता कंपनी नहीं",
        "maps_institute": "Google Maps पर यह \"{type}\" के रूप में दर्ज है",
        "lookalike_domain": "संपर्क मिलते-जुलते डोमेन ({domains}) से है, कंपनी के असली डोमेन ({official}) से नहीं",
        "own_domain": "संपर्क कंपनी के अपने डोमेन ({official}) से है",
        "brand_free_mail": "फ्री ईमेल पते में कंपनी का नाम ({email})",
    },
    "ml": {
        "fee": "പണം ആവശ്യപ്പെടുന്നു (ഫീസ് / ഡെപ്പോസിറ്റ് / പേയ്മെന്റ്)",
        "chat_contact": "കമ്പനി ചാനലിനു പകരം WhatsApp/Telegram വഴി റിക്രൂട്ട്മെന്റ്",
        "phone_contact": "ബന്ധപ്പെടാൻ സ്വകാര്യ മൊബൈൽ നമ്പർ നൽകിയിരിക്കുന്നു",
        "generic_email": "റിക്രൂട്ടർ സൗജന്യ ഇമെയിൽ (gmail/yahoo) ഉപയോഗിക്കുന്നു",
        "no_interview": "ഇന്റർവ്യൂ ഇല്ലാതെ ജോലി വാഗ്ദാനം",
        "easy_money": "എളുപ്പത്തിൽ പണം നേടാവുന്ന ജോലി (ടൈപ്പിംഗ്, ലൈക്കുകൾ, ഫോണിൽ ഡാറ്റ എൻട്രി)",
        "urgency": "തിടുക്കം കൂട്ടാനുള്ള സമ്മർദ്ദം",
        "hidden_company": "കമ്പനിയുടെ പേര് മറച്ചുവെച്ചിരിക്കുന്നു (\"Confidential\")",
        "pay": "പരിചയമില്ലാത്തവർക്കുള്ള ജോലിക്ക് അസാധാരണമായി ഉയർന്ന ശമ്പളം",
        "no_apply": "എവിടെയും അപേക്ഷാ ലിങ്ക് ഇല്ല",
        "boards": "പ്രമുഖ ജോബ് ബോർഡുകളിൽ ലിസ്റ്റ് ചെയ്തിട്ടുണ്ട്: {boards}",
        "unknown_apply": "അപേക്ഷിക്കാനുള്ള ഏക വഴി അപരിചിതമായ ഒരു വെബ്സൈറ്റ് ആണ്",
        "web_scam": "{n} സെർച്ച് ഫലങ്ങൾ ഈ കമ്പനിയുടെ പേരിനെ തട്ടിപ്പ് പരാതികളുമായി ബന്ധിപ്പിക്കുന്നു ({engines})",
        "complaint_sites": "പരാതി/റിവ്യൂ ഫോറങ്ങളിൽ ചർച്ച: {sites}",
        "impersonation": "തട്ടിപ്പുകാർ ഈ കമ്പനിയുടെ പേര് ഉപയോഗിക്കുന്നതായി അറിയാം (വ്യാജ ഓഫർ ലെറ്ററുകൾ / ഫ്രോഡ് അലർട്ടുകൾ)",
        "web_clean": "{engines}: ഈ പേരുമായി ബന്ധപ്പെട്ട തട്ടിപ്പ് പരാതികളൊന്നുമില്ല",
        "kg": "Google-ൽ കമ്പനിയുടെ Knowledge Graph പാനൽ ഉണ്ട്",
        "reviews": "{source}: റിവ്യൂകൾ കണ്ടെത്തി {stats}",
        "registry": "കമ്പനി രജിസ്ട്രിയിൽ ഉണ്ട് (MCA ഡാറ്റ, {source})",
        "official_site": "കമ്പനിക്ക് സ്വന്തം വെബ്സൈറ്റ് ഉണ്ട് ({domain})",
        "institute": "നേരിട്ടുള്ള തൊഴിലുടമയല്ല, പരിശീലന സ്ഥാപനമോ അക്കാദമിയോ ആണെന്ന് തോന്നുന്നു",
        "no_footprint": "Knowledge Graph, റിവ്യൂകൾ, രജിസ്ട്രി, വെബ്സൈറ്റ്, Google Maps ലിസ്റ്റിംഗ് ഒന്നും കണ്ടെത്തിയില്ല",
        "maps": "Google Maps-ൽ {n} ലിസ്റ്റിംഗ് {stats}",
        "maps_absent": "ഈ പേരിൽ Google Maps-ൽ ലിസ്റ്റിംഗ് ഇല്ല",
        "maps_agency": "Google Maps-ൽ ഇത് \"{type}\" ആണ്, തൊഴിലുടമയല്ല",
        "maps_institute": "Google Maps-ൽ ഇത് \"{type}\" ആയി രേഖപ്പെടുത്തിയിരിക്കുന്നു",
        "lookalike_domain": "ബന്ധപ്പെടാനുള്ള വിലാസം സമാനമായ ഡൊമെയ്നിൽ ({domains}) നിന്നാണ്, കമ്പനിയുടെ യഥാർത്ഥ ഡൊമെയ്നിൽ ({official}) നിന്നല്ല",
        "own_domain": "ബന്ധപ്പെടാനുള്ള വിലാസം കമ്പനിയുടെ സ്വന്തം ഡൊമെയ്നിൽ ({official}) നിന്നാണ്",
        "brand_free_mail": "സൗജന്യ ഇമെയിൽ വിലാസത്തിൽ കമ്പനിയുടെ പേര് ({email})",
    },
}

# Fixed explanations. Signals whose detail is a snippet or number keep the original text.
DETAILS = {
    "hi": {
        "hidden_company": "जिस नियोक्ता का नाम ही नहीं पता, उसकी जाँच नहीं हो सकती। दस्तावेज़ भेजने से पहले कंपनी का नाम पूछें।",
        "impersonation": "यह आमतौर पर ठगों के बारे में चेतावनी होती है, कंपनी के बारे में नहीं। सिर्फ़ आधिकारिक करियर साइट से अप्लाई करें।",
        "no_footprint": "बिल्कुल नई या नकली कंपनियाँ आम स्कैम तरीका हैं। अकेले यह सबूत नहीं है।",
        "institute": "इंस्टीट्यूट के 'नौकरी + ट्रेनिंग' ऑफ़र में अक्सर कोर्स फ़ीस देनी पड़ती है। जॉइन करने से पहले पूछें कि कोई फ़ीस तो नहीं।",
        "maps_absent": "असली ऑफ़िस वाली ज़्यादातर कंपनियों की लिस्टिंग होती है। रिमोट स्टार्टअप की शायद न हो, इसलिए अकेले यह कमज़ोर संकेत है।",
        "maps_agency": "प्लेसमेंट एजेंसियाँ कभी-कभी नौकरी ढूँढने वालों से पैसे लेती हैं। असली नियोक्ता कभी नहीं लेते। पूछें कि असली नियोक्ता कौन है।",
        "maps_institute": "इंस्टीट्यूट के 'नौकरी + ट्रेनिंग' ऑफ़र में अक्सर कोर्स फ़ीस देनी पड़ती है।",
        "lookalike_domain": "असली रिक्रूटर कंपनी के अपने डोमेन से लिखते हैं। मिलता-जुलता डोमेन ठगी का पुराना तरीका है।",
        "brand_free_mail": "कंपनियाँ अपने नाम वाले gmail/yahoo खातों से भर्ती नहीं करतीं।",
    },
    "ml": {
        "hidden_company": "പേര് അറിയാത്ത തൊഴിലുടമയെ പരിശോധിക്കാൻ കഴിയില്ല. രേഖകൾ അയയ്ക്കുന്നതിന് മുമ്പ് കമ്പനിയുടെ പേര് ചോദിക്കുക.",
        "impersonation": "ഇത് സാധാരണയായി തട്ടിപ്പുകാരെക്കുറിച്ചുള്ള മുന്നറിയിപ്പാണ്, കമ്പനിയെക്കുറിച്ചല്ല. ഔദ്യോഗിക കരിയർ സൈറ്റ് വഴി മാത്രം അപേക്ഷിക്കുക.",
        "no_footprint": "പുതിയതോ നിലവിലില്ലാത്തതോ ആയ കമ്പനികൾ സാധാരണ തട്ടിപ്പ് രീതിയാണ്. ഇത് മാത്രം തെളിവല്ല.",
        "institute": "സ്ഥാപനങ്ങളുടെ 'ജോലി + പരിശീലനം' ഓഫറുകളിൽ പലപ്പോഴും കോഴ്സ് ഫീസ് നൽകേണ്ടി വരും. ചേരുന്നതിന് മുമ്പ് ഫീസ് ഉണ്ടോ എന്ന് ചോദിക്കുക.",
        "maps_absent": "യഥാർത്ഥ ഓഫീസുള്ള മിക്ക തൊഴിലുടമകൾക്കും ലിസ്റ്റിംഗ് ഉണ്ടാകും. റിമോട്ട് സ്റ്റാർട്ടപ്പുകൾക്ക് ഇല്ലാതിരിക്കാം, അതിനാൽ ഇത് മാത്രം ദുർബലമായ സൂചനയാണ്.",
        "maps_agency": "പ്ലേസ്മെന്റ് ഏജൻസികൾ ചിലപ്പോൾ ഉദ്യോഗാർത്ഥികളിൽ നിന്ന് പണം വാങ്ങാറുണ്ട്. യഥാർത്ഥ തൊഴിലുടമകൾ ഒരിക്കലും വാങ്ങില്ല. യഥാർത്ഥ തൊഴിലുടമ ആരാണെന്ന് ചോദിക്കുക.",
        "maps_institute": "സ്ഥാപനങ്ങളുടെ 'ജോലി + പരിശീലനം' ഓഫറുകളിൽ പലപ്പോഴും കോഴ്സ് ഫീസ് നൽകേണ്ടി വരും.",
        "lookalike_domain": "യഥാർത്ഥ റിക്രൂട്ടർമാർ കമ്പനിയുടെ സ്വന്തം ഡൊമെയ്നിൽ നിന്നാണ് എഴുതുക. സമാനമായ ഡൊമെയ്ൻ പതിവ് ആൾമാറാട്ട തന്ത്രമാണ്.",
        "brand_free_mail": "കമ്പനികൾ അവരുടെ പേരിലുള്ള gmail/yahoo അക്കൗണ്ടുകളിൽ നിന്ന് റിക്രൂട്ട് ചെയ്യാറില്ല.",
    },
}

UI = {
    "en": {"score": "Risk score", "why": "Why", "evidence": "Evidence", "engines": "Engines queried",
           "engines_none": "none (posting text only)", "copy": "Copy as text", "copied": "Copied",
           "whatsapp": "Share on WhatsApp", "print": "Print / Save PDF", "company": "Company", "verdict": "Verdict",
           "footer": "Never pay to get a job. Report fraud at cybercrime.gov.in or call 1930.",
           "checked": "Checked with FresherShield", "pasted": "Pasted offer"},
    "hi": {"score": "जोखिम स्कोर", "why": "क्यों", "evidence": "सबूत", "engines": "जाँचे गए सर्च इंजन",
           "engines_none": "कोई नहीं (सिर्फ़ पोस्टिंग का टेक्स्ट)", "copy": "टेक्स्ट कॉपी करें", "copied": "कॉपी हो गया",
           "whatsapp": "WhatsApp पर शेयर करें", "print": "प्रिंट / PDF सेव करें", "company": "कंपनी", "verdict": "नतीजा",
           "footer": "नौकरी पाने के लिए कभी पैसे न दें। फ्रॉड की शिकायत cybercrime.gov.in पर करें या 1930 पर कॉल करें।",
           "checked": "FresherShield से जाँचा गया", "pasted": "पेस्ट किया गया ऑफ़र"},
    "ml": {"score": "അപകടസാധ്യത സ്കോർ", "why": "എന്തുകൊണ്ട്", "evidence": "തെളിവ്", "engines": "പരിശോധിച്ച സെർച്ച് എഞ്ചിനുകൾ",
           "engines_none": "ഒന്നുമില്ല (പോസ്റ്റിംഗ് ടെക്സ്റ്റ് മാത്രം)", "copy": "ടെക്സ്റ്റ് കോപ്പി ചെയ്യുക", "copied": "കോപ്പി ചെയ്തു",
           "whatsapp": "WhatsApp-ൽ ഷെയർ ചെയ്യുക", "print": "പ്രിന്റ് / PDF സേവ് ചെയ്യുക", "company": "കമ്പനി", "verdict": "ഫലം",
           "footer": "ജോലി ലഭിക്കാൻ ഒരിക്കലും പണം നൽകരുത്. തട്ടിപ്പ് cybercrime.gov.in-ൽ റിപ്പോർട്ട് ചെയ്യുക അല്ലെങ്കിൽ 1930-ൽ വിളിക്കുക.",
           "checked": "FresherShield ഉപയോഗിച്ച് പരിശോധിച്ചത്", "pasted": "പേസ്റ്റ് ചെയ്ത ഓഫർ"},
}


def norm_lang(lang: str | None) -> str:
    lang = (lang or "en").lower()[:2]
    return lang if lang in LANGS else "en"


def _fmt(template: str, params: dict) -> str:
    try:
        return template.format(**params).replace("  ", " ").strip()
    except (KeyError, IndexError, ValueError):
        return ""


def translate_report(report: dict, lang: str) -> dict:
    """Return a copy of a Report.to_dict() with verdict, headline, labels and fixed details in `lang`.

    Adds `level_label`, `lang` and `ui` (strings for the report panel). Anything without a
    translation falls back to the English text, so a report is never blank.
    """
    lang = norm_lang(lang)
    out = dict(report)
    out["lang"] = lang
    out["level_label"] = LEVELS[lang].get(report.get("level", ""), report.get("level", ""))
    out["ui"] = UI[lang]
    if lang == "en":
        return out
    labels, details = LABELS[lang], DETAILS[lang]
    hparams = dict(report.get("headline_params") or {})
    if "signal" in hparams:
        sig = next((s for s in report.get("signals", []) if s.get("id") == hparams["signal"]), None)
        if sig and sig["id"] in labels:
            hparams["label"] = _fmt(labels[sig["id"]], sig.get("params") or {}) or hparams.get("label", "")
    head_t = HEADLINES[lang].get(report.get("headline_key", ""))
    out["headline"] = (_fmt(head_t, hparams) if head_t else "") or report.get("headline", "")
    sigs = []
    for s in report.get("signals", []):
        s = dict(s)
        if s.get("id") in labels:
            s["label"] = _fmt(labels[s["id"]], s.get("params") or {}) or s["label"]
        if s.get("id") in details and s.get("detail"):
            s["detail"] = details[s["id"]]
        sigs.append(s)
    out["signals"] = sigs
    return out


def share_text(report: dict, lang: str = "en", max_evidence: int = 4) -> str:
    """Plain-text report for WhatsApp/SMS/email: verdict, reasons, evidence links, helpline."""
    r = translate_report(report, lang) if "ui" not in report else report
    ui = r["ui"]
    lines = [f"🛡️ FresherShield: {r.get('company') or ui['pasted']}",
             f"{ui['verdict']}: {r['level_label'].upper()} ({r['risk_score']}/100)",
             r.get("headline", ""), "", f"{ui['why']}:"]
    for s in r.get("signals", []):
        mark = "⚠️" if s["weight"] > 0 else "✅" if s["weight"] < 0 else "•"
        lines.append(f"{mark} {s['label']} ({'+' if s['weight'] > 0 else ''}{s['weight']})")
    ev = []
    for s in r.get("signals", []):
        for e in s.get("evidence") or []:
            if e.get("link") and e["link"] not in (x[1] for x in ev):
                ev.append((e.get("source") or "source", e["link"]))
    if ev:
        lines += ["", f"{ui['evidence']}:"] + [f"- {src}: {link}" for src, link in ev[:max_evidence]]
    lines += ["", ui["footer"], f"{ui['checked']}: {REPO_URL}"]
    return "\n".join(lines)
