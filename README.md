# IntelliRec — Web Content Intelligence & Recommendation Engine

**Final-Year Integrated Capstone Project** for **ASTMA (Advanced Social & Text Mining Analytics)**, **Enterprise Systems**, and **IT Project Management (ITPM)**.

---

## 🌟 Key Features

- **Modern Glassmorphic Responsive Web Application**: Sleek UI with Light & Dark themes, smooth animations, mobile responsive drawer navigation, and accessible typography.
- **5-Signal Hybrid Recommendation Engine**:
  - `Content Vector (40%)`: TF-IDF n-gram cosine similarity matched against user interests and reading history.
  - `Collaborative Filtering (25%)`: Item-Item cosine similarity matrix computed across user interaction vectors.
  - `Popularity Velocity (15%)`: Log-scaled composite engagement velocity.
  - `Recency Decay (10%)`: Dynamic linear freshness scoring.
  - `Explicit Feedback Slot (10%)`: Real-time user affinity tuning via 👍 / 👎 preference signals.
- **Explainable AI (XAI)**:
  - Transparent mathematical breakdown across all 5 ranking signals.
  - Natural language reasoning for why each recommendation was surfaced.
- **Interactive Full Article Reader**:
  - In-depth reader modal with hero images, estimated reading time, author metadata, and formatted typography.
  - Live Sentiment Polarity badge on every article and comment.
  - Instant Related / Similar Articles recommendations computed via cosine vector distance.
- **Community Discussion & Real-time Sentiment Analysis**:
  - Interactive comments feed with automated VADER sentiment scoring (Positive, Neutral, Negative).
- **ASTMA Analytics & NLP Laboratory**:
  - Live interactive testing sandbox: paste any headline, comment, or paragraph to extract VADER sentiment meters (-1.0 to +1.0), positive/neutral/negative breakdown percentages, top TF-IDF feature keywords, and predicted NMF topic clusters.
- **Admin Intelligence Command Center**:
  - Executive KPI cards with trend indicators.
  - Interactive **Chart.js** data visualizations:
    - Social Engagement by Category (Bar Chart).
    - Comment Sentiment Distribution (Doughnut Chart with emerald/amber/rose color scheme).
    - Media Type Performance Metrics (Bar Chart).
  - Unsupervised NMF Topic Discovery display.
  - Content Management Library (Add new articles/videos/images, delete content).
  - User Account Management with 1-click active/disabled toggle.
  - On-Demand Machine Learning Engine Retraining.
- **Enterprise Security & Architecture**:
  - PBKDF2 SHA-256 password hashing with 210,000 cryptographic iterations.
  - Stateless JWT Bearer token authentication with role-based access control (`ADMIN` vs `USER`).
  - Strong password strength meter enforcing 8+ characters, uppercase, lowercase, numbers, and symbols.
  - Dual support for SQLite (zero-config local run) and PostgreSQL (Docker enterprise deployment).

---

## 👥 Pre-Configured Demo Personas

The platform includes 1-click login buttons on the sign-in modal for seamless evaluation:

| Role | Name | Email | Password | Pre-seeded Interests |
| :--- | :--- | :--- | :--- | :--- |
| **Admin** | System Administrator | `admin@intellirec.local` | `Admin@2026!` | AI, Machine Learning, Cloud, Enterprise |
| **User** | Sarah Chen (Data Scientist) | `sarah.data@intellirec.local` | `User@2026!` | AI, Data Science, Machine Learning, NLP |
| **User** | Alex Rivera (Cloud Engineer) | `alex.dev@intellirec.local` | `User@2026!` | Cloud, Cybersecurity, Enterprise Systems |

---

## 🚀 How to Run Locally

### Option 1: Direct Local Execution (Python 3.12 - 3.14)

```powershell
# 1. Open the project directory
cd c:\Users\Admin\Downloads\IntelliRec_Final

# 2. Run the application with uvicorn
py -m uvicorn app.main:app --reload --port 8000
```

1. Open **`http://localhost:8000`** in your browser to view the Landing Page.
2. Open **`http://localhost:8000/app`** to enter the Interactive Workspace.
3. Open **`http://localhost:8000/docs`** for interactive OpenAPI / Swagger documentation.

---

### Option 2: Dockerized Deployment (PostgreSQL + FastAPI)

```bash
# 1. Build and start containers
docker compose up --build

# 2. Open http://localhost:8000
```

---

## 🧪 Running Automated Tests

```powershell
py -m pytest
```
All tests validate healthchecks, registration security constraints, JWT tokens, hybrid recommendations, interactions, comments, and ASTMA NLP endpoints.
