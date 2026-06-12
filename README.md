# AI-Powered Project Recommender System

An intelligent web-based application that recommends hardware and IoT project ideas based on the components provided by the user. The system understands natural language input, matches components logically, and uses semantic similarity to suggest the most relevant projects.

---

## 🚀 Overview

This project helps students and hobbyists answer questions like:
- *“I have a Raspberry Pi and a temperature sensor, what can I build?”*
- *“What are the components needed for a Home Automation System?”*

The system combines rule-based matching with AI-driven semantic understanding to produce accurate and meaningful project recommendations.

---

## ✨ Key Features

- 🔍 **Natural Language Understanding** using NLP (spaCy + embeddings)
- 🧠 **Semantic Project Matching** with Sentence-BERT (`all-MiniLM-L6-v2`)
- 🧩 **Component-Based Recommendations**
- 📝 **Project Requirement Queries** (e.g., required & optional components)
- ⭐ **Feedback Learning System** (like/dislike based ranking)
- ⚡ **Real-Time Chat Interface** using Flask-SocketIO
- 🎨 **Modern Dark UI** with interactive component selection

---

## 🛠️ Tech Stack

- **Backend:** Python, Flask, Flask-SocketIO  
- **AI / NLP:** SentenceTransformers, spaCy, RapidFuzz  
- **Frontend:** HTML, CSS, JavaScript  
- **Data Storage:** JSON (`data.json`, `feedback.json`)  

---

## 🧠 How It Works

1. User enters components or a natural language query.
2. Components are extracted using NLP and fuzzy matching.
3. Input is converted into embeddings using Sentence-BERT.
4. Each project is ranked using:
   - Logical component overlap
   - Semantic similarity (cosine similarity)
   - User feedback (likes/dislikes)
5. Top-ranked projects are displayed with match percentage, missing components, and enhancements.

---

## 📁 Project Structure

AI-Project-Recommender/
│
├── app.py # Main Flask backend
├── data.json # Components, relations, and project database
├── feedback.json # Stores user feedback (auto-created)
│
├── templates/
│ └── index.html # Frontend UI
│
└── README.md # Project documentation


---

## 💬 Sample Queries

- `I have an Arduino and an ultrasonic sensor`
- `What are the components needed for Home Automation System?`
- `Suggest beginner projects using Raspberry Pi`
- `Projects related to sensors and IoT`

---

## 🖥️ How to Run Locally

1. Clone the repository:
```bash
git clone https://github.com/your-username/AI-Project-Recommender.git
cd AI-Project-Recommender


pip install flask flask-socketio sentence-transformers rapidfuzz spacy
python -m spacy download en_core_web_sm


python app.py
http://127.0.0.1:5000

📄 License

This project is open-source and available for educational and non-commercial use.
