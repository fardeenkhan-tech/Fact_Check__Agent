# 🔍 Fact-Check Agent

An AI-powered fact-checking web application built with **Python** and **Streamlit** that automatically analyzes PDF documents, extracts factual claims, searches the live web for supporting evidence, and classifies each claim based on its accuracy.

## 🚀 Features

### 📄 PDF Claim Extraction

* Upload any PDF document.
* Automatically extract factual statements containing:

  * Percentages
  * Dates
  * Financial figures
  * User counts
  * Technical metrics
  * Statistical claims

### 🌐 Live Web Verification

* Searches the web in real time for evidence related to each claim.
* Collects supporting snippets from multiple sources.
* Requires **no paid API keys**.

### 🤖 Intelligent Fact Checking

Each extracted claim is analyzed and classified into one of the following categories:

| Verdict       | Description                                                                       |
| ------------- | --------------------------------------------------------------------------------- |
| ✅ Verified    | Strong supporting evidence with matching figures, dates, or statistics.           |
| ⚠️ Inaccurate | Related evidence exists, but quantities, dates, or values differ.                 |
| ❌ False       | No reliable supporting evidence found or the claim contradicts available sources. |

### 📊 Evidence-Based Reporting

For every claim, the system provides:

* Original claim
* Verdict classification
* Supporting source links
* Matched figures and dates
* Alternative values when discrepancies are detected
* Confidence indicators

---

## 🛠️ Tech Stack

* Python
* Streamlit
* Pandas
* PyMuPDF (PDF Processing)
* Regular Expressions (Claim Extraction)
* DuckDuckGo Search
* BeautifulSoup
* Requests

---

## 📂 Project Structure

```text
Fact-Check-Agent/
│
├── app.py                # Streamlit User Interface
├── factcheck.py          # Core Fact-Checking Engine
├── requirements.txt      # Project Dependencies
├── tests/                # Unit Tests
└── README.md
```

---

## ⚙️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/fact-check-agent.git
cd fact-check-agent
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
```

### 3. Activate Environment

#### Windows

```bash
.venv\Scripts\activate
```

#### Linux / macOS

```bash
source .venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Application

```bash
streamlit run app.py
```

---

## 🌍 Deployment

### Deploy on Streamlit Cloud

1. Push the project to GitHub.
2. Open Streamlit Cloud.
3. Create a new application.
4. Select the repository.
5. Set the entry file as:

```text
app.py
```

6. Click **Deploy**.

Your application will be available through a public URL.

---

## 🔄 Fact-Checking Workflow

```text
PDF Upload
     ↓
Text Extraction
     ↓
Claim Detection
     ↓
Web Search
     ↓
Evidence Collection
     ↓
Claim Comparison
     ↓
Verdict Generation
     ↓
Fact-Check Report
```

---

## 📸 Example Use Cases

* Research Paper Validation
* News Verification
* Academic Assignments
* Business Reports
* Market Analysis Documents
* Policy and Government Reports

---

## ⚠️ Limitations

* Search engines may occasionally rate-limit requests.
* Some claims require expert domain knowledge beyond public web sources.
* Verification quality depends on the availability of reliable online evidence.
* Recently published information may not yet be indexed by search engines.

---

## 🎯 Future Improvements

* Multi-language fact checking
* LLM-powered semantic verification
* Source credibility scoring
* PDF report export
* Batch document processing
* Advanced claim ranking

---

## 👨‍💻 Author

**Fardeen Khan**

Machine Learning Engineer | Data Science Enthusiast
