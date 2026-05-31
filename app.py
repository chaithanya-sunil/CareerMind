from fpdf import FPDF
import streamlit as st
import requests
import json
import re
import fitz
from docx import Document
import io
import os

SESSION_FILE = "C:\\Users\\ACER\\careermind_session.json"

def save_session(data):
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f)

def load_session():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    return {}

def read_uploaded_file(uploaded_file):
    if uploaded_file.type == "application/pdf":
        pdf_bytes = uploaded_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = Document(io.BytesIO(uploaded_file.read()))
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text
    return None

def ask_ollama(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3.2:3b",
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]

def extract_skills_from_resume(resume_text):
    prompt = f"""
    Analyze this resume and extract information in JSON format only.
    Return exactly this structure:
    {{
        "name": "person name",
        "skills": ["skill1", "skill2"],
        "education": "education details",
        "experience": "experience details",
        "projects": ["project1", "project2"],
        "certifications": ["cert1", "cert2"]
    }}
    Resume:
    {resume_text}
    Return JSON only, nothing else.
    """
    for attempt in range(3):
        try:
            response = ask_ollama(prompt)
            clean = re.search(r'\{.*\}', response, re.DOTALL)
            if clean:
                return json.loads(clean.group())
        except:
            continue
    return None

st.set_page_config(page_title="CareerMind", page_icon="🧠")
st.title("🧠 CareerMind")
st.subheader("Offline AI Career Mentor")
st.write("100% Private — Your data never leaves your laptop")

saved = load_session()
for key, value in saved.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", [
    "Resume Analyzer",
    "Skill Gap Analysis",
    "Learning Roadmap",
    "PDF Report",
    "Career Chat"
])

if page == "Resume Analyzer":
    st.header("📄 Resume Analyzer")

    uploaded_file = st.file_uploader(
        "Upload your resume (PDF or DOCX)",
        type=["pdf", "docx"]
    )

    resume_text = ""
    if uploaded_file:
        resume_text = read_uploaded_file(uploaded_file)
        st.success("File uploaded successfully!")
    else:
        resume_text = st.text_area(
            "Or paste your resume here",
            height=200,
            placeholder="Paste your resume text here..."
        )

    if st.button("Analyze Resume ↗"):
        if resume_text:
            with st.spinner("Analyzing your resume..."):
                result = extract_skills_from_resume(resume_text)

            if result:
                st.success("Resume analyzed successfully!")

                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("👤 Name")
                    st.write(result.get("name", "Not found"))

                    st.subheader("🎓 Education")
                    st.write(result.get("education", "Not found"))

                    st.subheader("💼 Experience")
                    experience = result.get("experience", "Not found")
                    if isinstance(experience, list):
                        for exp in experience:
                            if isinstance(exp, dict):
                                st.write(f"• {exp.get('title', '')}")
                            else:
                                st.write(f"• {exp}")
                    else:
                        st.write(experience)

                with col2:
                    st.subheader("🛠️ Skills Found")
                    skills = result.get("skills", [])
                    for skill in skills:
                        st.write(f"• {skill}")

                    st.subheader("📁 Projects")
                    projects = result.get("projects", [])
                    for project in projects:
                        st.write(f"• {project}")

                st.session_state["extracted_skills"] = skills
                st.session_state["resume_analyzed"] = True

                save_session({
                    "extracted_skills": skills,
                    "resume_analyzed": True
                })
            else:
                st.error("Could not analyze resume. Please try again.")
        else:
            st.warning("Please upload or paste your resume first!")

elif page == "Skill Gap Analysis":
    st.header("📊 Skill Gap Analysis")

    target_role = st.selectbox(
        "Select your target role",
        ["Data Analyst", "AI Engineer", "Backend Developer",
         "Frontend Developer", "Full Stack Developer"]
    )

    required_skills = {
        "Data Analyst": ["Python", "SQL", "Excel", "Power BI",
                        "Tableau", "Statistics", "Machine Learning"],
        "AI Engineer": ["Python", "Machine Learning", "Deep Learning",
                       "TensorFlow", "PyTorch", "NLP", "MLOps"],
        "Backend Developer": ["Python", "SQL", "REST API", "Django",
                             "FastAPI", "Docker", "Git"],
        "Frontend Developer": ["HTML", "CSS", "JavaScript", "React",
                              "TypeScript", "Git"],
        "Full Stack Developer": ["Python", "JavaScript", "SQL", "React",
                                "Django", "Docker", "Git"]
    }

    user_skills_input = st.text_input(
        "Enter your skills (comma separated)",
        placeholder="Python, SQL, Excel..."
    )

    if st.session_state.get("extracted_skills"):
        st.info(f"Skills from resume: {', '.join(st.session_state['extracted_skills'])}")

    if st.button("Analyze Gap ↗"):
        if user_skills_input:
            user_skills_lower = [s.strip().lower() for s in user_skills_input.split(",")]
            required_lower = [s.lower() for s in required_skills[target_role]]

            matching = [required_skills[target_role][i] for i, s in enumerate(required_lower) if s in user_skills_lower]
            missing = [required_skills[target_role][i] for i, s in enumerate(required_lower) if s not in user_skills_lower]
            match_percent = round(len(matching) / len(required_skills[target_role]) * 100)

            st.subheader(f"Results for {target_role}")

            col1, col2, col3 = st.columns(3)
            col1.metric("Match Score", f"{match_percent}%")
            col2.metric("Matching Skills", len(matching))
            col3.metric("Missing Skills", len(missing))

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("✅ Matching Skills")
                for skill in matching:
                    st.success(skill)

            with col2:
                st.subheader("❌ Missing Skills")
                for skill in missing:
                    st.error(skill)

            st.session_state["missing_skills"] = missing
            st.session_state["target_role"] = target_role
            st.session_state["match_percent"] = match_percent

            save_session({
                "extracted_skills": st.session_state.get("extracted_skills", []),
                "missing_skills": missing,
                "target_role": target_role,
                "match_percent": match_percent
            })
        else:
            st.warning("Please enter your skills!")

elif page == "Learning Roadmap":
    st.header("🗺️ Learning Roadmap")

    target_role = st.selectbox(
        "Select your target role",
        ["Data Analyst", "AI Engineer", "Backend Developer",
         "Frontend Developer", "Full Stack Developer"]
    )

    missing = st.session_state.get("missing_skills", [])

    if missing:
        st.info(f"Based on your skill gap: {', '.join(missing)}")

    duration = st.selectbox(
        "How long do you want to prepare?",
        ["2 weeks", "4 weeks", "8 weeks", "3 months", "6 months", "1 year", "2 years"]
    )

    if st.button("Generate Roadmap ↗"):
        with st.spinner("Generating your personalized roadmap..."):
            missing_text = ", ".join(missing) if missing else "general skills"
            prompt = f"""Create a {duration} learning roadmap for someone who wants to become a {target_role}.
            They need to learn: {missing_text}

            Format the response as:
            Week 1: [topic] - [resource]
            Week 2: [topic] - [resource]
            ...and so on for the full {duration}.

            Be specific and practical."""

            roadmap = ask_ollama(prompt)

        st.subheader(f"Your {duration} Roadmap to become {target_role}")

        weeks = roadmap.split('\n')
        for week in weeks:
            if week.strip():
                if week.startswith("Week") or week.startswith("Month") or week.startswith("Year"):
                    st.markdown(f"**{week}**")
                else:
                    st.write(week)

        st.session_state["roadmap"] = roadmap

        saved_data = load_session()
        saved_data["roadmap"] = roadmap
        save_session(saved_data)

        st.success("Roadmap generated! Go to PDF Report to download.")

elif page == "PDF Report":
    st.header("📑 PDF Report Generator")
    st.write("Generate a complete career analysis report!")

    name = st.text_input("Your Name", placeholder="Chaithanya AS")
    target_role = st.session_state.get("target_role", "Data Analyst")
    match_percent = st.session_state.get("match_percent", 0)
    missing_skills = st.session_state.get("missing_skills", [])
    roadmap = st.session_state.get("roadmap", "")

    st.info(f"Target Role: {target_role}")
    st.info(f"Match Score: {match_percent}%")

    if match_percent == 0:
        st.warning("⚠️ Please complete Skill Gap Analysis first for accurate results!")

    if st.button("Generate PDF Report ↗"):
        if name:
            with st.spinner("Generating your report..."):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_margins(15, 15, 15)

                pdf.set_font("Helvetica", "B", 24)
                pdf.cell(0, 15, "CareerMind Report", ln=True, align="C")

                pdf.set_font("Helvetica", "", 12)
                pdf.cell(0, 8, "Offline AI Career Mentor", ln=True, align="C")
                pdf.ln(10)

                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 10, "Personal Details", ln=True)
                pdf.set_font("Helvetica", "", 12)
                pdf.cell(0, 8, f"Name: {name}", ln=True)
                pdf.cell(0, 8, f"Target Role: {target_role}", ln=True)
                pdf.ln(5)

                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(0, 10, "Skill Gap Analysis", ln=True)
                pdf.set_font("Helvetica", "", 12)
                pdf.cell(0, 8, f"Match Score: {match_percent}%", ln=True)

                if missing_skills:
                    pdf.cell(0, 8, "Missing Skills:", ln=True)
                    for skill in missing_skills:
                        pdf.cell(0, 8, f"  - {skill}", ln=True)
                pdf.ln(5)

                if roadmap:
                    pdf.set_font("Helvetica", "B", 14)
                    pdf.cell(0, 10, "Learning Roadmap", ln=True)
                    pdf.set_font("Helvetica", "", 11)
                    for line in roadmap.split('\n'):
                        if line.strip():
                            clean_line = line.encode('latin-1', 'replace').decode('latin-1')
                            clean_line = clean_line.strip()
                            if clean_line:
                                try:
                                    pdf.multi_cell(180, 7, clean_line)
                                except:
                                    pass

                pdf.ln(10)
                pdf.set_font("Helvetica", "I", 10)
                pdf.cell(0, 8, "Generated by CareerMind - 100% Offline & Private", ln=True, align="C")

                report_path = "C:\\Users\\ACER\\careermind_report.pdf"
                pdf.output(report_path)

            st.success("PDF Report generated!")

            with open(report_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download PDF Report",
                    data=f,
                    file_name="careermind_report.pdf",
                    mime="application/pdf"
                )
        else:
            st.warning("Please enter your name!")

elif page == "Career Chat":
    st.header("💬 Career Chat Assistant")
    st.write("Ask me anything about your career!")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Ask your career question...")

    if user_input:
        st.session_state["messages"].append({
            "role": "user",
            "content": user_input
        })

        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                context = ""
                if st.session_state.get("target_role"):
                    context = f"The user is targeting {st.session_state['target_role']} role."

                prompt = f"""You are a helpful career mentor.
                {context}
                Answer this career question clearly and practically:
                {user_input}"""

                response = ask_ollama(prompt)
                st.write(response)

                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": response
                })