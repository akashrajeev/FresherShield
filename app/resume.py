"""Resume <-> job matching. Deterministic and explainable: no black-box score.

We extract skills from both texts with a curated taxonomy (aliases -> canonical
skill), then score how much of what the job asks for the resume already covers.
"""
from __future__ import annotations

import io
import re

# canonical skill -> aliases (lowercase). Kept deliberately practical for Indian fresher roles.
SKILLS: dict[str, list[str]] = {
    # languages
    "Python": ["python"], "Java": ["java", "core java"], "JavaScript": ["javascript", r"\bjs\b"],
    "TypeScript": ["typescript"], "C": [r"\bc programming\b", r"\bc language\b", r"(?<![\w+#])c(?=\s*(?:,|/|and)\s*c\+\+)"],
    "C++": [r"c\+\+", "cpp"], "C#": [r"c#", r"\.net", "dotnet"], "Kotlin": ["kotlin"], "Go": ["golang", r"\bgo lang\b"],
    "SQL": [r"\bsql\b", "mysql", "postgresql", "postgres", "sql server", "oracle db", "pl/sql"], "R": [r"\br programming\b", r"\bin r\b"],
    "PHP": [r"\bphp\b"], "Swift": [r"\bswift\b"], "Dart": [r"\bdart\b"], "Bash": ["bash", "shell scripting"],
    # web
    "HTML": [r"\bhtml5?\b"], "CSS": [r"\bcss3?\b", "tailwind", "bootstrap"], "React": [r"\breact(?:\.js|js)?\b"],
    "Angular": ["angular"], "Node.js": [r"node(?:\.js|js)?\b", "express"], "Django": ["django"], "Flask": ["flask"],
    "FastAPI": ["fastapi"], "Spring Boot": ["spring boot", "spring"], "REST APIs": [r"rest(?:ful)? api", r"\bapis?\b"],
    "Next.js": [r"next\.?js"],
    # mobile
    "Android": ["android"], "Flutter": ["flutter"], "React Native": ["react native"], "Jetpack Compose": ["jetpack compose"],
    # data / ml
    "Machine Learning": ["machine learning", r"\bml\b"], "Deep Learning": ["deep learning", "neural network"],
    "NLP": [r"\bnlp\b", "natural language processing"], "Computer Vision": ["computer vision", "opencv"],
    "Pandas": ["pandas"], "NumPy": ["numpy"], "scikit-learn": ["scikit", "sklearn"], "TensorFlow": ["tensorflow", "keras"],
    "PyTorch": ["pytorch"], "Power BI": ["power bi", "powerbi"], "Tableau": ["tableau"], "Excel": ["excel", "spreadsheets"],
    "Data Analysis": ["data analysis", "data analytics", "analytical skills"], "Statistics": ["statistics", "statistical"],
    "Generative AI": ["generative ai", "genai", r"\bllms?\b", "large language model", "prompt engineering"],
    # cloud / devops
    "AWS": [r"\baws\b", "amazon web services", r"\bec2\b", r"\bs3\b", "lambda"], "Azure": ["azure"], "GCP": [r"\bgcp\b", "google cloud"],
    "Docker": ["docker", "container"], "Kubernetes": ["kubernetes", r"\bk8s\b"], "Linux": ["linux", "unix"],
    "Git": [r"\bgit\b", "github", "gitlab", "version control"], "CI/CD": [r"ci/cd", "jenkins", "github actions"],
    # cs fundamentals
    "Data Structures & Algorithms": ["data structures", "algorithms", r"\bdsa\b"], "OOP": [r"\boops?\b", "object oriented", "object-oriented"],
    "DBMS": ["dbms", "database management"], "Operating Systems": ["operating systems"], "Computer Networks": ["computer networks", "networking", "tcp/ip"],
    "Testing": ["software testing", "manual testing", "selenium", "unit testing", r"\bqa\b", "test cases"],
    # non-tech fresher roles
    "Communication": ["communication skills", "communication", "verbal", "written english"],
    "Customer Support": ["customer support", "customer service", "voice process", "non-voice", "bpo", "call center", "chat support"],
    "Sales": [r"\bsales\b", "business development", "lead generation", "telecalling", "telesales"],
    "Digital Marketing": ["digital marketing", r"\bseo\b", "social media marketing", "google ads", "content marketing"],
    "Content Writing": ["content writing", "copywriting", "blog writing"], "Accounting": ["accounting", "tally", "gst", "bookkeeping"],
    "MS Office": ["ms office", "microsoft office", "word", "powerpoint"], "Figma": ["figma", "ui/ux", "ux design", "wireframe"],
    "Problem Solving": ["problem solving", "problem-solving"], "Teamwork": ["teamwork", "team player"],
}

SOFT = {"Communication", "Problem Solving", "Teamwork"}

_COMPILED = {
    skill: [re.compile(a if a.startswith(("\\", "(")) or any(ch in a for ch in "\\[]()+?") else rf"(?<![\w]){re.escape(a)}(?![\w])", re.I)
            for a in aliases]
    for skill, aliases in SKILLS.items()
}


def extract_skills(text: str) -> set[str]:
    text = text or ""
    found = set()
    for skill, pats in _COMPILED.items():
        if any(p.search(text) for p in pats):
            found.add(skill)
    # "React Native" should not also count as generic React unless React appears on its own
    if "React Native" in found and "React" in found and not re.search(r"\breact(?:\.js|js)?\b(?!\s+native)", text, re.I):
        found.discard("React")
    return found


def pdf_to_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def match(resume_text: str, job_text: str) -> dict:
    """Return a 0-100 match with matched/missing skills.

    Hard skills weigh 1.0, soft skills 0.4. If the job lists no recognizable skills
    we return score=None instead of pretending.
    """
    have = extract_skills(resume_text)
    want = extract_skills(job_text)
    if not want:
        return {"score": None, "matched": [], "missing": [], "extra": sorted(have), "note": "No recognizable skills in this posting"}

    def w(s: str) -> float:
        return 0.4 if s in SOFT else 1.0

    matched = sorted(want & have, key=lambda s: (s in SOFT, s))
    missing = sorted(want - have, key=lambda s: (s in SOFT, s))
    total = sum(w(s) for s in want)
    got = sum(w(s) for s in matched)
    score = round(100 * got / total)
    return {"score": score, "matched": matched, "missing": missing, "extra": sorted(have - want)}
