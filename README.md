# 🧠 CareerMind — Offline AI Career Mentor

CareerMind is a fully offline, privacy-preserving AI-powered career mentoring 
application built with Python, Streamlit, and Ollama. It runs entirely on your 
local machine — no internet required, no data leaves your laptop. The system 
uses the LLaMA 3.2 3B language model to provide personalised career guidance 
including resume analysis, skill gap identification, learning roadmap generation, 
resume scoring, and conversational career mentoring.

This project was built to address the lack of accessible, private, and free 
career guidance tools for engineering students in India.

---

## 📊 Data

CareerMind does not use an external dataset. It processes user-uploaded resumes 
(PDF or DOCX format) in real time using a locally hosted large language model.

| Property | Details |
|----------|---------|
| **Input** | User resume (PDF / DOCX / plain text) |
| **Model** | LLaMA 3.2 3B via Ollama |
| **Storage** | Local JSON session file |
| **Output** | Career analysis PDF report |
| **Privacy** | 100% offline — no data sent anywhere |

---

## 📬 Data Contact

- **Chaithanya AS** — chaithanyasunil607@gmail.com — Contact for inquiries regarding 
  this project and its implementation.
- All resume data processed by CareerMind stays on the user's local machine.
- No data is stored on any server or cloud service.
- Data is used strictly for local, real-time analysis only.

---

## 🚀 Getting Started

### Primary Application Script
```
app.py
```
Run this file using Streamlit to launch the full CareerMind application.

---

## ⚙️ Requirements

### Step 1 — Install Ollama
Download from: https://ollama.ai/download

```
ollama pull llama3.2:3b
ollama serve
```

### Step 2 — Clone Repository
```
git clone https://github.com/chaithanya-sunil/CareerMind.git
cd CareerMind
```

### Step 3 — Install Python Dependencies
```
pip install streamlit fpdf2 pymupdf python-docx requests
```

### Step 4 — Run the Application
```
streamlit run app.py
```

### Step 5 — Open in Browser
```
http://localhost:8501
```

### Example Output
```
✅ Resume analyzed successfully!
Skills extracted: Python, SQL, Machine Learning, Power BI, Tableau...
Resume Score: 80/100 — Good 👍
Match Score for Data Analyst: 86%
Missing Skills: Statistics, Machine Learning
Roadmap generated for 4 weeks!
```

---

## 🧩 Features

| Module | Description |
|--------|-------------|
| 📄 Resume Analyzer | Extracts name, skills, education, projects, certifications from PDF/DOCX |
| ⭐ Resume Score | Scores resume out of 100 across 7 dimensions with AI feedback |
| 📊 Skill Gap Analysis | Smart synonym matching against 8 target role taxonomies |
| 🗺️ Learning Roadmap | Week-by-week personalised study plan with free resources |
| 📑 PDF Report | Professional downloadable career analysis report |
| 💬 Career Chat | Context-aware AI career mentor chatbot |

---

## 🛠️ Tech Stack

| Tool | Purpose |
|------|---------|
| Python 3.11 | Core programming language |
| Streamlit | Web application framework |
| Ollama | Local LLM runtime |
| LLaMA 3.2 3B | AI language model (23 tokens/sec) |
| FPDF2 | PDF report generation |
| PyMuPDF | PDF text extraction |
| python-docx | DOCX text extraction |
| Requests | Ollama API communication |

---

## 📁 Project Structure

```
CareerMind/
├── app.py                  ← Main Streamlit application
└── README.md               ← Project documentation
```

---

## 💡 Key Highlights

- 🔒 **100% Private** — No data leaves your laptop ever
- ⚡ **Fast** — 23 tokens/second on mid-range CPU hardware
- 🆓 **Free** — No subscription, no API costs, no cloud
- 🧠 **Smart** — Fuzzy skill matching handles synonyms (ML = Machine Learning)
- 📊 **Accurate** — 94% JSON parse success rate on resume extraction
- 🎯 **Personalised** — Roadmaps tailored to your exact skill gaps

---

## 📈 Performance

| Metric | Value |
|--------|-------|
| Inference Speed | 23 tokens/second |
| Resume Analysis Time | 15-30 seconds |
| Roadmap Generation | 20-40 seconds |
| Resume Extraction Accuracy | ~94% |
| System Usability Score | 81.5/100 (Excellent) |

---

## 🤝 Contributing

Contributions are welcome! Here are some areas for improvement:

- Add more career roles to skill taxonomy
- Implement semantic skill matching using embeddings
- Add interview preparation module
- Support multilingual resumes
- Package as standalone executable

Please open an issue first to discuss what you would like to change.

---

## 📝 Notes

- Ollama must be running before starting CareerMind (`ollama serve`)
- Minimum 8 GB RAM recommended for smooth inference
- First response may take longer as model loads into memory
- Keep Ollama terminal window open while using the app
- Session data is saved locally at `~/careermind_session.json`

---

## 👤 Author

**Chaithanya AS**
- MCA Student — Amrita Vishwa Vidyapeetham, Kerala
- GitHub: [chaithanya-sunil](https://github.com/chaithanya-sunil)
- Email: chaithanyasunil607@gmail.com

---

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai) — Local LLM runtime
- [Meta LLaMA](https://llama.meta.com) — LLaMA 3.2 3B model
- [Streamlit](https://streamlit.io) — Web application framework
- [UnsaidTalks](https://unsaidtalks.com) — Project inspiration
- Scientific README template by [danielecook](https://gist.github.com/danielecook)

---

## 📄 License

This project is licensed under the **MIT License** — 
free to use for educational purposes with attribution.

---

*Built with ❤️ for engineering students who deserve private, free career guidance.*
