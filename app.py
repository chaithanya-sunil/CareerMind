from fpdf import FPDF
import streamlit as st
import requests
import json
import re
import fitz
from docx import Document
import io
import os
from datetime import date

# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

SESSION_FILE = os.path.join(os.path.expanduser("~"), "careermind_session.json")

def save_session(data):
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass

def load_session():
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {}

def safe_text(text):
    """Remove all unicode characters that crash FPDF Helvetica font."""
    replacements = {
        "\u2014": "-", "\u2013": "-", "\u2012": "-",
        "\u2019": "'", "\u2018": "'",
        "\u201c": '"', "\u201d": '"',
        "\u2022": "*", "\u2023": "*", "\u25cf": "*",
        "\u2713": "OK", "\u2717": "X", "\u2718": "X",
        "\u00e9": "e", "\u00e8": "e", "\u00ea": "e",
        "\u00e0": "a", "\u00e2": "a", "\u00fc": "u",
        "\u2026": "...", "\u00a0": " ",
    }
    for char, replacement in replacements.items():
        text = str(text).replace(char, replacement)
    # Final fallback — strip anything outside latin-1
    return text.encode('latin-1', 'replace').decode('latin-1')

def clean_markdown(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*',     r'\1', text)
    text = re.sub(r'#{1,6}\s*',     '',    text)
    text = text.replace('`', '').replace('~', '')
    return text.strip()

def read_uploaded_file(uploaded_file):
    try:
        if uploaded_file.type == "application/pdf":
            pdf_bytes = uploaded_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            return text.strip()
        elif "wordprocessingml" in uploaded_file.type:
            doc = Document(io.BytesIO(uploaded_file.read()))
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            return text.strip()
    except Exception as e:
        st.error(f"Error reading file: {e}")
    return None

# ── Fuzzy skill matching (handles synonyms) ───────────────────────────────────
SKILL_SYNONYMS = {
    "machine learning": ["ml", "machine learning", "machinelearning"],
    "deep learning":    ["dl", "deep learning", "deeplearning"],
    "natural language processing": ["nlp", "natural language processing", "text mining"],
    "power bi":         ["powerbi", "power bi", "power-bi", "microsoft power bi"],
    "tableau":          ["tableau", "tableau desktop"],
    "tensorflow":       ["tensorflow", "tf", "tensor flow"],
    "pytorch":          ["pytorch", "torch"],
    "scikit-learn":     ["scikit-learn", "sklearn", "scikit learn"],
    "data visualization": ["data visualization", "data viz", "matplotlib", "seaborn",
                           "plotly", "bokeh", "power bi", "tableau", "visualization"],
    "version control":  ["git", "github", "gitlab", "version control"],
    "rest api":         ["rest api", "restful", "api", "rest"],
    "javascript":       ["javascript", "js"],
    "typescript":       ["typescript", "ts"],
    "docker":           ["docker", "containerization", "containers"],
    "kubernetes":       ["kubernetes", "k8s"],
    "aws":              ["aws", "amazon web services", "amazon aws"],
    "azure":            ["azure", "microsoft azure"],
    "gcp":              ["gcp", "google cloud", "google cloud platform"],
    "ci/cd":            ["ci/cd", "cicd", "ci cd", "jenkins", "github actions"],
}

def skills_match(user_skill, required_skill):
    """Check if user skill matches required skill considering synonyms."""
    user_lower    = user_skill.strip().lower()
    required_lower = required_skill.strip().lower()
    if user_lower == required_lower:
        return True
    # Check synonym groups
    for canonical, synonyms in SKILL_SYNONYMS.items():
        if required_lower in synonyms or required_lower == canonical:
            if user_lower in synonyms or user_lower == canonical:
                return True
    # Partial match — user skill contains required or vice versa
    if required_lower in user_lower or user_lower in required_lower:
        return True
    return False

# ── Ollama ────────────────────────────────────────────────────────────────────
def ask_ollama(prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": "10m",
                    "options": {"temperature": 0.3, "top_p": 0.9}
                },
                timeout=180
            )
            if response.status_code == 200:
                return response.json().get("response", "")
        except requests.exceptions.ConnectionError:
            if attempt == 0:
                st.error("Ollama is not running! Open a new CMD window and run: ollama serve")
            return None
        except Exception as e:
            if attempt == max_retries - 1:
                st.error(f"AI error: {e}")
    return None

# ── Resume extraction ─────────────────────────────────────────────────────────
def extract_skills_from_resume(resume_text):
    prompt = f"""You are an expert resume parser. Read this resume carefully and extract ALL information.
Return ONLY a valid JSON object. No explanation. No markdown. No text before or after the JSON.

JSON structure to return:
{{
  "name": "full name exactly as written",
  "email": "email or empty string",
  "phone": "phone number or empty string",
  "location": "city or state or empty string",
  "objective": "career objective one line or empty string",
  "skills": ["every single skill, tool, technology, framework, language mentioned"],
  "education": [
    {{"degree": "degree name", "institution": "college/university", "year": "graduation year or ongoing", "score": "CGPA or percentage or empty"}}
  ],
  "experience": [
    {{"title": "job title or intern role", "company": "company name", "duration": "start-end or months", "description": "what they did in one line"}}
  ],
  "projects": [
    {{"name": "exact project name", "description": "what the project does", "technologies": ["tech1","tech2"]}}
  ],
  "certifications": ["full certification name with platform"],
  "languages": ["spoken languages only, not programming languages"],
  "achievements": ["any awards, ranks, or achievements"]
}}

CRITICAL RULES:
- Extract EVERY skill mentioned anywhere — in skills section, projects, experience, certifications
- Include tools like Jupyter, VS Code, Git, GitHub, Google Colab as skills
- Include soft skills if mentioned: Leadership, Communication, Teamwork
- Do NOT skip any section
- Do NOT invent anything not in the resume
- Return ONLY the JSON, nothing else

RESUME:
{resume_text}

JSON:"""

    for attempt in range(3):
        try:
            response = ask_ollama(prompt)
            if not response:
                continue
            clean = re.search(r'\{.*\}', response, re.DOTALL)
            if clean:
                data = json.loads(clean.group())
                if "name" in data and "skills" in data:
                    return data
        except:
            continue
    return None

# ── Resume Score ──────────────────────────────────────────────────────────────
def score_resume(extracted_data, resume_text):
    """Score resume out of 100 across 7 dimensions."""
    scores = {}
    feedback = {}

    # 1. Contact Info (10 pts)
    contact = 0
    contact_tips = []
    if extracted_data.get("name"):       contact += 3
    if extracted_data.get("email"):      contact += 3
    else: contact_tips.append("Add your email address")
    if extracted_data.get("phone"):      contact += 2
    else: contact_tips.append("Add your phone number")
    if extracted_data.get("location"):   contact += 2
    else: contact_tips.append("Add your city/location")
    scores["Contact Info"] = contact
    feedback["Contact Info"] = contact_tips if contact_tips else ["All contact details present"]

    # 2. Skills (20 pts)
    skills = extracted_data.get("skills", [])
    skill_score = min(20, len(skills) * 2)
    skill_tips = []
    if len(skills) < 5:  skill_tips.append("Add more technical skills — aim for at least 8-10")
    if len(skills) < 10: skill_tips.append("Include tools like Git, VS Code, Jupyter")
    scores["Skills"] = skill_score
    feedback["Skills"] = skill_tips if skill_tips else [f"Good! {len(skills)} skills found"]

    # 3. Education (15 pts)
    edu = extracted_data.get("education", [])
    edu_score = 0
    edu_tips = []
    if edu:
        edu_score += 8
        for e in edu:
            if isinstance(e, dict) and e.get("score"): edu_score += 4; break
        else: edu_tips.append("Add your CGPA or percentage")
        if any(isinstance(e, dict) and e.get("year") for e in edu): edu_score += 3
    else:
        edu_tips.append("Add your education details")
    scores["Education"] = min(15, edu_score)
    feedback["Education"] = edu_tips if edu_tips else ["Education section looks complete"]

    # 4. Experience / Internships (20 pts)
    exp = extracted_data.get("experience", [])
    exp_score = 0
    exp_tips = []
    if exp:
        exp_score = min(20, len(exp) * 10)
        for e in exp:
            if isinstance(e, dict) and not e.get("description"):
                exp_tips.append("Add descriptions to your experience entries")
                break
    else:
        exp_tips.append("Add internships or part-time work experience")
        exp_score = 0
    scores["Experience"] = exp_score
    feedback["Experience"] = exp_tips if exp_tips else ["Experience section looks good"]

    # 5. Projects (20 pts)
    projs = extracted_data.get("projects", [])
    proj_score = min(20, len(projs) * 5)
    proj_tips = []
    if len(projs) < 2: proj_tips.append("Add at least 2-3 projects")
    if len(projs) < 4: proj_tips.append("Add more projects to strengthen your profile")
    for p in projs:
        if isinstance(p, dict) and not p.get("technologies"):
            proj_tips.append("Mention technologies used in each project"); break
    scores["Projects"] = proj_score
    feedback["Projects"] = proj_tips if proj_tips else [f"{len(projs)} projects found — great!"]

    # 6. Certifications (10 pts)
    certs = extracted_data.get("certifications", [])
    cert_score = min(10, len(certs) * 3)
    cert_tips = []
    if not certs: cert_tips.append("Add certifications from Coursera, Google, IBM, etc.")
    scores["Certifications"] = cert_score
    feedback["Certifications"] = cert_tips if cert_tips else [f"{len(certs)} certifications found"]

    # 7. Objective / Summary (5 pts)
    obj_score = 5 if extracted_data.get("objective") else 0
    obj_tips  = [] if extracted_data.get("objective") else ["Add a 2-line career objective at the top"]
    scores["Objective"] = obj_score
    feedback["Objective"] = obj_tips if obj_tips else ["Career objective present"]

    total = sum(scores.values())
    return total, scores, feedback

# ══════════════════════════════════════════════════════════════════════════════
# PDF GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_pdf_report(name, target_role, match_percent, matching_skills,
                         missing_skills, roadmap, extracted_data, resume_score=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    def s(text): return safe_text(str(text))

    def section_title(title):
        pdf.set_fill_color(239, 246, 255)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(30, 58, 138)
        pdf.cell(0, 10, s(title), ln=True, fill=True)
        pdf.set_text_color(30, 30, 30)
        pdf.ln(2)

    def body(text, indent=0):
        pdf.set_font("Helvetica", "", 11)
        pdf.set_x(20 + indent)
        pdf.multi_cell(170 - indent, 7, s(text))

    # Header
    pdf.set_fill_color(30, 58, 138)
    pdf.rect(0, 0, 210, 42, 'F')
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(8)
    pdf.cell(0, 12, "CareerMind Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Offline AI Career Mentor - 100% Private", ln=True, align="C")
    pdf.ln(20)
    pdf.set_text_color(30, 30, 30)

    # Personal Details
    section_title("Personal Details")
    body(f"Name: {name.title()}")
    body(f"Target Role: {target_role}")
    body(f"Report Date: {date.today().strftime('%d %B %Y')}")
    if extracted_data:
        if extracted_data.get("email"):    body(f"Email: {extracted_data['email']}")
        if extracted_data.get("phone"):    body(f"Phone: {extracted_data['phone']}")
        if extracted_data.get("location"): body(f"Location: {extracted_data['location']}")
    pdf.ln(4)

    # Resume Score
    if resume_score is not None:
        section_title(f"Resume Score: {resume_score}/100")
        score_label = "Excellent" if resume_score >= 85 else "Good" if resume_score >= 65 else "Needs Improvement"
        body(f"Overall Rating: {score_label}")
        pdf.ln(2)

    # Education
    if extracted_data and extracted_data.get("education"):
        section_title("Education")
        for edu in extracted_data["education"]:
            if isinstance(edu, dict):
                line = f"{edu.get('degree','')} - {edu.get('institution','')} ({edu.get('year','')})"
                if edu.get("score"): line += f" | {edu['score']}"
                body(f"* {line}", indent=4)
            else:
                body(f"* {edu}", indent=4)
        pdf.ln(4)

    # Skills
    if extracted_data and extracted_data.get("skills"):
        section_title("Skills Extracted from Resume")
        skills_line = ", ".join(extracted_data["skills"])
        body(skills_line)
        pdf.ln(4)

    # Skill Gap
    section_title("Skill Gap Analysis")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Match Score: {match_percent}%", ln=True)
    pdf.ln(2)
    if matching_skills:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(22, 101, 52)
        pdf.cell(0, 7, "Matching Skills:", ln=True)
        pdf.set_text_color(30, 30, 30)
        for skill in matching_skills:
            body(f"  + {skill}", indent=4)
    pdf.ln(2)
    if missing_skills:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(185, 28, 28)
        pdf.cell(0, 7, "Skills to Learn:", ln=True)
        pdf.set_text_color(30, 30, 30)
        for skill in missing_skills:
            body(f"  - {skill}", indent=4)
    pdf.ln(4)

    # Projects
    if extracted_data and extracted_data.get("projects"):
        section_title("Projects")
        for proj in extracted_data["projects"]:
            if isinstance(proj, dict):
                body(f"* {proj.get('name','')}: {proj.get('description','')}", indent=4)
                if proj.get("technologies"):
                    body(f"  Tools: {', '.join(proj['technologies'])}", indent=8)
            else:
                body(f"* {proj}", indent=4)
        pdf.ln(4)

    # Certifications
    if extracted_data and extracted_data.get("certifications"):
        section_title("Certifications")
        for cert in extracted_data["certifications"]:
            body(f"* {cert}", indent=4)
        pdf.ln(4)

    # Roadmap
    if roadmap:
        pdf.add_page()
        section_title("Learning Roadmap")
        pdf.set_font("Helvetica", "", 10)
        for line in roadmap.split('\n'):
            if not line.strip():
                pdf.ln(2); continue
            clean = safe_text(clean_markdown(line))
            if not clean: continue
            if re.match(r'^(Week|Month|Day|Phase)\s+\d+', clean, re.IGNORECASE):
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(30, 58, 138)
                pdf.set_x(20)
                pdf.multi_cell(170, 7, clean)
                pdf.set_text_color(30, 30, 30)
                pdf.set_font("Helvetica", "", 10)
            else:
                pdf.set_x(24)
                pdf.multi_cell(166, 6, clean)

    # Footer
    pdf.ln(8)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 8, "Generated by CareerMind - 100% Offline & Private", ln=True, align="C", fill=True)

    output_path = os.path.join(os.path.expanduser("~"), "careermind_report.pdf")
    pdf.output(output_path)
    return output_path

# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="CareerMind", page_icon="🧠", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f2057 0%, #1e3a8a 50%, #2563eb 100%);
}
[data-testid="stSidebar"] * { color: white !important; }
[data-testid="stSidebar"] .stRadio label {
    background: rgba(255,255,255,0.08);
    border-radius: 8px; padding: 8px 12px;
    margin: 3px 0; display: block; transition: all 0.2s;
    border: 1px solid rgba(255,255,255,0.1);
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,255,255,0.2);
    border-color: rgba(255,255,255,0.3);
}
.main .block-container { padding-top: 1.5rem; max-width: 920px; }
.cm-card {
    background: white; border-radius: 14px; padding: 20px 24px;
    margin: 12px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.07);
    border: 1px solid #e2e8f0;
}
.cm-metric {
    border-radius: 12px; padding: 18px;
    text-align: center; color: white;
}
.cm-metric .value { font-size: 2.2rem; font-weight: 700; }
.cm-metric .label { font-size: 0.82rem; opacity: 0.88; margin-top: 4px; }
.skill-match {
    display: inline-block; background: #dcfce7; color: #166534;
    border: 1px solid #86efac; border-radius: 20px;
    padding: 4px 14px; margin: 4px; font-size: 0.84rem; font-weight: 500;
}
.skill-miss {
    display: inline-block; background: #fee2e2; color: #991b1b;
    border: 1px solid #fca5a5; border-radius: 20px;
    padding: 4px 14px; margin: 4px; font-size: 0.84rem; font-weight: 500;
}
.skill-tag {
    display: inline-block; background: #eff6ff; color: #1e40af;
    border: 1px solid #bfdbfe; border-radius: 20px;
    padding: 4px 14px; margin: 4px; font-size: 0.84rem; font-weight: 500;
}
.cm-section-title {
    font-size: 1rem; font-weight: 600; color: #1e3a8a;
    border-left: 3px solid #2563eb; padding-left: 10px;
    margin: 16px 0 8px 0;
}
.cm-progress-wrap {
    background: #e2e8f0; border-radius: 999px; height: 14px;
    overflow: hidden; margin: 8px 0;
}
.cm-progress-fill {
    height: 100%; border-radius: 999px;
    background: linear-gradient(90deg, #2563eb, #7c3aed);
    transition: width 0.6s ease;
}
.score-bar-wrap {
    background: #e2e8f0; border-radius: 999px; height: 10px;
    overflow: hidden; margin: 4px 0 8px 0;
}
.score-bar-fill {
    height: 100%; border-radius: 999px;
    transition: width 0.4s ease;
}
.stButton > button {
    background: linear-gradient(135deg, #1e3a8a, #2563eb) !important;
    color: white !important; border: none !important;
    border-radius: 8px !important; padding: 10px 28px !important;
    font-weight: 600 !important; font-size: 0.95rem !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.3) !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(37,99,235,0.4) !important;
}
[data-testid="stFileUploader"] {
    border: 2px dashed #93c5fd !important; border-radius: 12px !important;
    padding: 16px !important; background: #eff6ff !important;
}
</style>
""", unsafe_allow_html=True)

# Load session
saved = load_session()
for key, value in saved.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 CareerMind")
    st.markdown("*Offline AI Career Mentor*")
    st.markdown("---")
    page = st.radio("Navigate", [
        "🏠  Home",
        "📄  Resume Analyzer",
        "⭐  Resume Score",
        "📊  Skill Gap Analysis",
        "🗺️  Learning Roadmap",
        "📑  PDF Report",
        "💬  Career Chat"
    ], label_visibility="collapsed")

    st.markdown("---")
    st.markdown("**Session Status**")
    st.markdown("✅ Resume analyzed" if st.session_state.get("resume_analyzed") else "⬜ Resume not analyzed")
    st.markdown("✅ Resume scored"   if st.session_state.get("resume_score")    else "⬜ Resume not scored")
    st.markdown("✅ Gap analysis done" if st.session_state.get("missing_skills") is not None else "⬜ Gap not analyzed")
    st.markdown("✅ Roadmap ready"   if st.session_state.get("roadmap")         else "⬜ Roadmap not generated")

    st.markdown("")
    if st.button("🗑️ Clear Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# HOME
# ══════════════════════════════════════════════════════════════════════════════
if "Home" in page:
    st.markdown("""
    <div style='text-align:center; padding:30px 0 10px;'>
        <div style='font-size:4rem;'>🧠</div>
        <h1 style='color:#1e3a8a; margin:4px 0;'>CareerMind</h1>
        <p style='color:#64748b; font-size:1.1rem;'>Offline AI Career Mentor — 100% Private</p>
    </div>""", unsafe_allow_html=True)

    cols = st.columns(3)
    features = [
        ("📄", "Resume Analyzer",     "Extracts name, skills, education, projects from your resume"),
        ("⭐", "Resume Score",         "Scores your resume out of 100 with improvement tips"),
        ("📊", "Skill Gap Analysis",   "Shows exactly what skills you're missing for your target role"),
        ("🗺️", "Learning Roadmap",     "Week-by-week personalised study plan with free resources"),
        ("📑", "PDF Report",           "Download a professional career analysis report"),
        ("💬", "Career Chat",          "Ask any career question to your private AI mentor"),
    ]
    for i, (icon, title, desc) in enumerate(features):
        with cols[i % 3]:
            st.markdown(f"""
            <div class='cm-card' style='text-align:center; min-height:130px;'>
                <div style='font-size:2rem;'>{icon}</div>
                <div style='font-weight:600; color:#1e3a8a; margin:8px 0 4px;'>{title}</div>
                <div style='color:#64748b; font-size:0.84rem;'>{desc}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Recommended steps:**")
    for i, s in enumerate([
        "Upload your resume in Resume Analyzer",
        "Check Resume Score to improve your resume",
        "Run Skill Gap Analysis for your target role",
        "Generate your personalised Learning Roadmap",
        "Download the PDF Report",
        "Chat with AI for any career questions"
    ], 1):
        st.markdown(f"**{i}.** {s}")

# ══════════════════════════════════════════════════════════════════════════════
# RESUME ANALYZER
# ══════════════════════════════════════════════════════════════════════════════
elif "Resume Analyzer" in page:
    st.markdown("## 📄 Resume Analyzer")
    st.caption("Upload your resume — AI extracts every detail accurately")

    uploaded_file = st.file_uploader("Upload resume (PDF or DOCX)", type=["pdf", "docx"])
    resume_text = ""
    if uploaded_file:
        resume_text = read_uploaded_file(uploaded_file)
        if resume_text:
            with st.expander("📝 View raw extracted text"):
                st.text(resume_text[:2000] + ("..." if len(resume_text) > 2000 else ""))
    else:
        resume_text = st.text_area("Or paste your resume text here", height=220,
                                   placeholder="Paste your full resume here...")

    if st.button("🔍 Analyze Resume"):
        if not resume_text or len(resume_text.strip()) < 50:
            st.warning("Please upload a resume or paste at least some content.")
        else:
            with st.spinner("Analyzing resume — 15 to 30 seconds..."):
                result = extract_skills_from_resume(resume_text)

            if result:
                st.success("✅ Resume analyzed successfully!")
                st.session_state["extracted_data"]   = result
                st.session_state["extracted_skills"] = result.get("skills", [])
                st.session_state["resume_text"]      = resume_text
                st.session_state["resume_analyzed"]  = True
                saved_data = load_session()
                saved_data.update({
                    "extracted_data": result,
                    "extracted_skills": result.get("skills", []),
                    "resume_analyzed": True
                })
                save_session(saved_data)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("<div class='cm-section-title'>👤 Personal Info</div>", unsafe_allow_html=True)
                    st.markdown(f"**Name:** {result.get('name','Not found')}")
                    if result.get("email"):    st.markdown(f"**Email:** {result['email']}")
                    if result.get("phone"):    st.markdown(f"**Phone:** {result['phone']}")
                    if result.get("location"): st.markdown(f"**Location:** {result['location']}")
                    if result.get("objective"):
                        st.markdown("<div class='cm-section-title'>🎯 Objective</div>", unsafe_allow_html=True)
                        st.write(result["objective"])

                    st.markdown("<div class='cm-section-title'>🎓 Education</div>", unsafe_allow_html=True)
                    for edu in result.get("education", []):
                        if isinstance(edu, dict):
                            line = f"**{edu.get('degree','')}** — {edu.get('institution','')}"
                            if edu.get("year"):  line += f" *({edu['year']})*"
                            if edu.get("score"): line += f" | {edu['score']}"
                            st.markdown(f"• {line}")
                        else:
                            st.markdown(f"• {edu}")

                    st.markdown("<div class='cm-section-title'>💼 Experience</div>", unsafe_allow_html=True)
                    exp_list = result.get("experience", [])
                    if exp_list:
                        for exp in exp_list:
                            if isinstance(exp, dict):
                                st.markdown(f"• **{exp.get('title','')}** at {exp.get('company','')} — {exp.get('duration','')}")
                                if exp.get("description"): st.caption(f"  {exp['description']}")
                            else:
                                st.markdown(f"• {exp}")
                    else:
                        st.write("No experience found")

                with col2:
                    st.markdown("<div class='cm-section-title'>🛠️ Skills Found</div>", unsafe_allow_html=True)
                    skills = result.get("skills", [])
                    if skills:
                        tags = "".join([f"<span class='skill-tag'>{s}</span>" for s in skills])
                        st.markdown(f"<div style='margin:8px 0'>{tags}</div>", unsafe_allow_html=True)
                        st.caption(f"Total: {len(skills)} skills extracted")
                    else:
                        st.warning("No skills found — add a clear Skills section to your resume")

                    st.markdown("<div class='cm-section-title'>📁 Projects</div>", unsafe_allow_html=True)
                    for proj in result.get("projects", []):
                        if isinstance(proj, dict):
                            st.markdown(f"• **{proj.get('name','')}** — {proj.get('description','')}")
                            if proj.get("technologies"):
                                techs = "".join([f"<span class='skill-tag'>{t}</span>" for t in proj["technologies"]])
                                st.markdown(f"<div style='margin:2px 0 6px 12px'>{techs}</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"• {proj}")

                    if result.get("certifications"):
                        st.markdown("<div class='cm-section-title'>🏆 Certifications</div>", unsafe_allow_html=True)
                        for cert in result["certifications"]:
                            st.markdown(f"• {cert}")

                    if result.get("achievements"):
                        st.markdown("<div class='cm-section-title'>🥇 Achievements</div>", unsafe_allow_html=True)
                        for ach in result["achievements"]:
                            st.markdown(f"• {ach}")

                    if result.get("languages"):
                        st.markdown("<div class='cm-section-title'>🌐 Languages</div>", unsafe_allow_html=True)
                        langs = "".join([f"<span class='skill-tag'>{l}</span>" for l in result["languages"]])
                        st.markdown(f"<div>{langs}</div>", unsafe_allow_html=True)

                st.info("👉 Go to **Resume Score** to see how strong your resume is!")
            else:
                st.error("Could not analyze resume. Make sure Ollama is running and try again.")

# ══════════════════════════════════════════════════════════════════════════════
# RESUME SCORE
# ══════════════════════════════════════════════════════════════════════════════
elif "Resume Score" in page:
    st.markdown("## ⭐ Resume Score")
    st.caption("Get your resume scored out of 100 with specific improvement tips")

    extracted_data = st.session_state.get("extracted_data")
    resume_text    = st.session_state.get("resume_text", "")

    if not extracted_data:
        st.warning("Please analyze your resume first in the Resume Analyzer page!")
        st.stop()

    if st.button("⭐ Score My Resume"):
        with st.spinner("Scoring your resume..."):
            total, scores, feedback = score_resume(extracted_data, resume_text)

        st.session_state["resume_score"] = total
        saved_data = load_session()
        saved_data["resume_score"] = total
        save_session(saved_data)

        # Big score display
        color = "#16a34a" if total >= 80 else "#d97706" if total >= 60 else "#dc2626"
        grade = "Excellent 🌟" if total >= 85 else "Good 👍" if total >= 70 else "Average ⚠️" if total >= 50 else "Needs Work ❌"

        st.markdown(f"""
        <div style='text-align:center; background:linear-gradient(135deg,#1e3a8a,#2563eb);
                    border-radius:16px; padding:30px; margin:16px 0; color:white;'>
            <div style='font-size:4rem; font-weight:800;'>{total}<span style='font-size:2rem;'>/100</span></div>
            <div style='font-size:1.3rem; margin-top:8px;'>{grade}</div>
        </div>""", unsafe_allow_html=True)

        # Section breakdown
        st.markdown("### 📊 Score Breakdown")
        max_scores = {
            "Contact Info": 10, "Skills": 20, "Education": 15,
            "Experience": 20,   "Projects": 20, "Certifications": 10, "Objective": 5
        }
        section_colors = {
            "Contact Info": "#2563eb",  "Skills": "#7c3aed",
            "Education":    "#0891b2",  "Experience": "#059669",
            "Projects":     "#d97706",  "Certifications": "#dc2626", "Objective": "#9333ea"
        }

        for section, score in scores.items():
            max_s   = max_scores[section]
            pct     = int(score / max_s * 100)
            color_s = section_colors.get(section, "#2563eb")
            tips    = feedback.get(section, [])

            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{section}**")
                st.markdown(f"""
                <div class='score-bar-wrap'>
                    <div class='score-bar-fill' style='width:{pct}%; background:{color_s};'></div>
                </div>""", unsafe_allow_html=True)
                for tip in tips:
                    if tip and not tip.startswith("Good") and not tip.startswith("All") and not tip.startswith(str(score)):
                        st.caption(f"💡 {tip}")
            with col2:
                st.markdown(f"<div style='text-align:right; font-weight:700; color:{color_s}; font-size:1.1rem; padding-top:4px;'>{score}/{max_s}</div>", unsafe_allow_html=True)

            st.markdown("")

        # AI detailed feedback
        st.markdown("### 🤖 AI Feedback on Your Resume")
        with st.spinner("Getting AI feedback..."):
            skills_list  = ", ".join(extracted_data.get("skills", []))
            proj_count   = len(extracted_data.get("projects", []))
            exp_count    = len(extracted_data.get("experience", []))
            cert_count   = len(extracted_data.get("certifications", []))
            prompt = f"""You are an expert resume reviewer for engineering students in India.
Review this resume and give specific, actionable feedback.

Resume details:
- Name: {extracted_data.get('name','')}
- Skills ({len(extracted_data.get('skills',[]))} found): {skills_list}
- Projects: {proj_count}
- Experience/Internships: {exp_count}
- Certifications: {cert_count}
- Has objective: {'Yes' if extracted_data.get('objective') else 'No'}
- Resume Score: {total}/100

Give feedback in exactly this format:
STRENGTHS:
- [strength 1]
- [strength 2]

IMPROVEMENTS NEEDED:
- [specific improvement 1]
- [specific improvement 2]
- [specific improvement 3]

TOP 3 ACTIONS TO TAKE NOW:
1. [most important action]
2. [second action]
3. [third action]

Be specific, practical and encouraging."""

            ai_feedback = ask_ollama(prompt)

        if ai_feedback:
            lines = ai_feedback.split('\n')
            for line in lines:
                line = line.strip()
                if not line: continue
                if line.endswith(':') and line.isupper():
                    st.markdown(f"**{line}**")
                elif line.startswith(('- ', '* ')):
                    st.markdown(f"  {line}")
                elif re.match(r'^\d+\.', line):
                    st.markdown(f"  {line}")
                else:
                    st.write(line)

        # What to do next
        st.markdown("---")
        if total < 60:
            st.error("Your resume needs significant improvements before applying. Follow the tips above!")
        elif total < 75:
            st.warning("Good start! Fix the improvements above to make your resume stand out.")
        else:
            st.success("Great resume! Go to Skill Gap Analysis to check your role readiness.")

# ══════════════════════════════════════════════════════════════════════════════
# SKILL GAP ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif "Skill Gap" in page:
    st.markdown("## 📊 Skill Gap Analysis")
    st.caption("Compare your skills to what employers need — with smart synonym matching")

    ROLE_SKILLS = {
        "Data Analyst":       ["Python", "SQL", "Excel", "Power BI", "Tableau", "Statistics", "Machine Learning"],
        "Data Scientist":     ["Python", "R", "Machine Learning", "Statistics", "SQL", "TensorFlow", "Data Visualization"],
        "AI Engineer":        ["Python", "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "NLP", "MLOps", "Docker"],
        "Backend Developer":  ["Python", "SQL", "REST API", "Django", "FastAPI", "Docker", "Git", "Linux"],
        "Frontend Developer": ["HTML", "CSS", "JavaScript", "React", "TypeScript", "Git", "Figma"],
        "Full Stack Developer":["Python", "JavaScript", "SQL", "React", "Django", "Docker", "Git", "REST API"],
        "DevOps Engineer":    ["Linux", "Docker", "Kubernetes", "CI/CD", "AWS", "Git", "Bash", "Ansible"],
        "Cloud Engineer":     ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "Linux", "Networking"],
    }

    target_role = st.selectbox("Select your target role", list(ROLE_SKILLS.keys()))

    default_skills = ""
    if st.session_state.get("extracted_skills"):
        default_skills = ", ".join(st.session_state["extracted_skills"])
        st.info("📋 Auto-filled from your resume. Edit if needed.")

    user_skills_input = st.text_input(
        "Your current skills (comma separated)",
        value=default_skills,
        placeholder="Python, SQL, Excel, Power BI..."
    )

    if st.button("Analyze Gap"):
        if not user_skills_input.strip():
            st.warning("Please enter your skills or analyze your resume first.")
        else:
            user_skills = [s.strip() for s in user_skills_input.split(",") if s.strip()]
            required    = ROLE_SKILLS[target_role]

            # Smart matching with synonyms
            matching = [req for req in required if any(skills_match(u, req) for u in user_skills)]
            missing  = [req for req in required if not any(skills_match(u, req) for u in user_skills)]
            match_pct = round(len(matching) / len(required) * 100)

            st.markdown("---")
            m1, m2, m3 = st.columns(3)
            color = "#16a34a" if match_pct >= 70 else "#d97706" if match_pct >= 40 else "#dc2626"
            with m1:
                st.markdown(f"""<div class='cm-metric' style='background:linear-gradient(135deg,{color},{color}bb)'>
                    <div class='value'>{match_pct}%</div><div class='label'>Match Score</div></div>""",
                    unsafe_allow_html=True)
            with m2:
                st.markdown(f"""<div class='cm-metric' style='background:linear-gradient(135deg,#16a34a,#22c55e)'>
                    <div class='value'>{len(matching)}</div><div class='label'>Skills You Have</div></div>""",
                    unsafe_allow_html=True)
            with m3:
                st.markdown(f"""<div class='cm-metric' style='background:linear-gradient(135deg,#dc2626,#ef4444)'>
                    <div class='value'>{len(missing)}</div><div class='label'>Skills to Learn</div></div>""",
                    unsafe_allow_html=True)

            st.markdown(f"""
            <div style='margin:16px 0 4px; font-weight:600; color:#1e3a8a;'>Readiness for {target_role}</div>
            <div class='cm-progress-wrap'><div class='cm-progress-fill' style='width:{match_pct}%'></div></div>
            <div style='color:#64748b; font-size:0.85rem; margin-bottom:16px;'>{match_pct}% ready</div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div class='cm-section-title'>✅ Skills You Have</div>", unsafe_allow_html=True)
                if matching:
                    st.markdown("".join([f"<span class='skill-match'>✓ {s}</span>" for s in matching]), unsafe_allow_html=True)
                else:
                    st.warning("No matching skills found")
            with col2:
                st.markdown("<div class='cm-section-title'>❌ Skills to Learn</div>", unsafe_allow_html=True)
                if missing:
                    st.markdown("".join([f"<span class='skill-miss'>✗ {s}</span>" for s in missing]), unsafe_allow_html=True)
                else:
                    st.success("🎉 You have all required skills!")

            st.session_state.update({
                "missing_skills": missing, "matching_skills": matching,
                "target_role": target_role, "match_percent": match_pct
            })
            saved_data = load_session()
            saved_data.update({
                "missing_skills": missing, "matching_skills": matching,
                "target_role": target_role, "match_percent": match_pct
            })
            save_session(saved_data)
            if missing:
                st.info("👉 Go to **Learning Roadmap** to get your personalised study plan!")

# ══════════════════════════════════════════════════════════════════════════════
# LEARNING ROADMAP
# ══════════════════════════════════════════════════════════════════════════════
elif "Roadmap" in page:
    st.markdown("## 🗺️ Learning Roadmap")
    st.caption("Personalised week-by-week study plan with free verified resources")

    roles = ["Data Analyst","Data Scientist","AI Engineer","Backend Developer",
             "Frontend Developer","Full Stack Developer","DevOps Engineer","Cloud Engineer"]
    saved_role = st.session_state.get("target_role", "Data Analyst")
    idx = roles.index(saved_role) if saved_role in roles else 0
    target_role = st.selectbox("Target role", roles, index=idx)

    missing = st.session_state.get("missing_skills", [])
    if missing:
        st.success(f"📋 Based on your skill gap: **{', '.join(missing)}**")
    else:
        st.info("Complete Skill Gap Analysis first for a personalised roadmap.")

    duration = st.selectbox("Preparation duration",
                            ["2 weeks", "4 weeks", "8 weeks", "3 months", "6 months"])

    if st.button("Generate Roadmap"):
        with st.spinner("Generating roadmap — please wait..."):
            missing_text = ", ".join(missing) if missing else "core skills for this role"
            prompt = f"""Create a detailed {duration} learning roadmap for becoming a {target_role}.
Skills to focus on: {missing_text}

Use EXACTLY this format and nothing else:

Week 1: [Topic Name]
Day 1-2: [What to study] - Resource: [Name] - URL: [real free URL]
Day 3-4: [What to study] - Resource: [Name] - URL: [real free URL]
Day 5-7: Practice Task: [specific practice task]

Week 2: [Topic Name]
...continue for all {duration}...

Final Week: Capstone Project
Build: [specific project idea using the skills learned]

RULES:
- Only FREE resources: Kaggle Learn, freeCodeCamp, official documentation, YouTube
- Kaggle Learn URL format: https://www.kaggle.com/learn/[topic]
- freeCodeCamp URL: https://www.freecodecamp.org
- Be specific with day numbers
- Each week must have one clear focus
- Do NOT suggest paid courses"""

            roadmap = ask_ollama(prompt)

        if roadmap:
            st.markdown(f"### Your {duration} Roadmap — {target_role}")
            st.markdown("---")
            for line in roadmap.split('\n'):
                if not line.strip(): st.markdown(""); continue
                clean = clean_markdown(line.strip())
                if not clean: continue
                if re.match(r'^(Week|Month|Phase)\s+\d+', clean, re.IGNORECASE):
                    st.markdown(f"### 📅 {clean}")
                elif re.match(r'^Day\s+\d+', clean, re.IGNORECASE):
                    st.markdown(f"**{clean}**")
                elif clean.lower().startswith("practice task"):
                    st.info(f"🛠️ {clean}")
                elif clean.lower().startswith("build:"):
                    st.success(f"🚀 {clean}")
                elif clean.startswith(("*", "-", "•")):
                    st.markdown(f"  {clean}")
                else:
                    st.write(clean)

            st.session_state["roadmap"] = roadmap
            saved_data = load_session()
            saved_data["roadmap"] = roadmap
            save_session(saved_data)
            st.success("✅ Roadmap saved! Go to PDF Report to download.")
        else:
            st.error("Could not generate roadmap. Please check Ollama is running.")

# ══════════════════════════════════════════════════════════════════════════════
# PDF REPORT
# ══════════════════════════════════════════════════════════════════════════════
elif "PDF" in page:
    st.markdown("## 📑 PDF Report")
    st.caption("Download your complete career analysis as a professional PDF")

    name = st.text_input("Your name", placeholder="Chaithanya AS")

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown("✅ Resume" if st.session_state.get("resume_analyzed") else "⚠️ Resume")
    with col2: st.markdown("✅ Score"  if st.session_state.get("resume_score")    else "⚠️ Score")
    with col3: st.markdown("✅ Gap"    if st.session_state.get("missing_skills") is not None else "⚠️ Gap")
    with col4: st.markdown("✅ Roadmap" if st.session_state.get("roadmap")        else "⚠️ Roadmap")

    target_role    = st.session_state.get("target_role",    "Not set")
    match_percent  = st.session_state.get("match_percent",  0)
    missing_skills = st.session_state.get("missing_skills", [])
    matching_skills= st.session_state.get("matching_skills",[])
    roadmap        = st.session_state.get("roadmap",        "")
    extracted_data = st.session_state.get("extracted_data", {})
    resume_score   = st.session_state.get("resume_score",   None)

    st.markdown(f"**Target Role:** {target_role} &nbsp;|&nbsp; **Match Score:** {match_percent}%")
    if resume_score:
        st.markdown(f"**Resume Score:** {resume_score}/100")

    if st.button("📥 Generate & Download PDF"):
        if not name.strip():
            st.warning("Please enter your name.")
        else:
            with st.spinner("Generating PDF..."):
                path = generate_pdf_report(
                    name, target_role, match_percent,
                    matching_skills, missing_skills,
                    roadmap, extracted_data, resume_score
                )
            st.success("✅ PDF ready!")
            with open(path, "rb") as f:
                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=f,
                    file_name=f"CareerMind_{name.replace(' ','_')}.pdf",
                    mime="application/pdf"
                )

# ══════════════════════════════════════════════════════════════════════════════
# CAREER CHAT
# ══════════════════════════════════════════════════════════════════════════════
elif "Chat" in page:
    st.markdown("## 💬 Career Chat")
    st.caption("Ask anything about careers, skills, interviews, or your roadmap")

    st.markdown("**Quick questions:**")
    qcols = st.columns(3)
    quick = [
        "Best free courses for my target role",
        "How to prepare for technical interviews",
        "How to build a strong portfolio as a fresher"
    ]
    for i, q in enumerate(quick):
        with qcols[i]:
            if st.button(q, key=f"quick_{i}"):
                st.session_state.setdefault("messages", [])
                st.session_state["messages"].append({"role": "user", "content": q})
                st.rerun()

    st.markdown("---")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Ask your career question...")

    if user_input:
        st.session_state["messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                context = ""
                if st.session_state.get("target_role"):
                    context += f"User is targeting: {st.session_state['target_role']}. "
                if st.session_state.get("missing_skills"):
                    context += f"Missing skills: {', '.join(st.session_state['missing_skills'])}. "
                if st.session_state.get("resume_score"):
                    context += f"Resume score: {st.session_state['resume_score']}/100. "

                prompt = f"""You are an expert career mentor for engineering students in India.
{context}
Give practical, specific, encouraging career advice.
Only suggest FREE resources: Kaggle, Coursera free tier, YouTube, official docs, freeCodeCamp.
Keep your answer clear, structured and under 300 words.

Question: {user_input}"""

                response = ask_ollama(prompt)
                if response:
                    st.write(response)
                    st.session_state["messages"].append({"role": "assistant", "content": response})
                else:
                    st.error("No response — check Ollama is running with: ollama serve")

    if st.session_state.get("messages"):
        if st.button("🗑️ Clear chat"):
            st.session_state["messages"] = []
            st.rerun()