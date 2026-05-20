# ⚖️ LexAI — AI Legal Advisor & Pakistan Tax Filer
### Version 2.0.0 | BSCS24041 Assignment 2

> **RAG-Enhanced Legal Intelligence** · **FBR-Compliant PDF Generation** · **Groq LLaMA 3.3 70B**

---

## 📋 Project Overview

LexAI is a full-stack AI application that democratizes legal advice and Pakistan tax compliance. It satisfies all requirements from the SRS (BSCS24041_ASM2_SRS.docx).

### Modules

| Module | Description |
|--------|-------------|
| ⚖️ **Global Legal Advisor** | RAG-grounded jurisdiction-specific legal guidance for 195+ countries, referencing actual statutes (e.g., Section 14 PRPA 2009) |
| 📄 **Pakistan Tax Filer** | 4-step NTN registration wizard → generates professional FBR-compliant PDFs |
| 📊 **Filer vs Non-Filer** | Interactive comparison of FBR 2024–25 withholding rates with personal savings calculator |

---

## 🏗️ Architecture

```
lexai/
├── backend/
│   ├── main.py              # FastAPI app — 17 REST endpoints
│   └── pdf_generator.py     # ReportLab PDF engine (NTN, ITR, Wealth Statement)
├── rag_data/
│   └── legal_kb.py          # RAG knowledge base — 8 legal topics × multiple jurisdictions
│                              # FBR tax slabs, withholding rates, utility functions
├── frontend/
│   └── index.html           # Full single-file frontend (no build step required)
├── documents/               # Sample generated PDFs
├── run.py                   # One-command startup script
└── requirements.txt
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| AI / LLM | Groq API (LLaMA 3.3 70B) — **Free tier** |
| RAG | In-memory legal knowledge base (statute-referenced) |
| PDF Engine | ReportLab 4.x — professional A4 documents |
| Frontend | Vanilla HTML/CSS/JS — zero dependencies, zero build step |
| HTTP Client | aiohttp (async Groq calls) |

---

## 🚀 Quick Start

### Step 1 — Get a Free Groq API Key
1. Visit [console.groq.com](https://console.groq.com)
2. Sign up (no credit card needed)
3. Create an API key (starts with `gsk_`)

### Step 2 — Install & Run

```bash
# Clone / extract the project
cd lexai

# Option A: One-command startup
python3 run.py

# Option B: Manual
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 3 — Open the App
- **App**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- Enter your Groq API key when prompted → click **Launch App**

> **Standalone mode**: You can also open `frontend/index.html` directly in a browser (PDF download will use the backend fallback).

---

## 🔌 API Reference

All endpoints are prefixed with `/api/`.

### Legal Module

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/jurisdictions` | All supported countries + regions |
| `POST` | `/api/legal/chat` | RAG-enhanced legal Q&A |
| `POST` | `/api/legal/document` | Generate legal document (PDF + text) |

**Legal Chat Request:**
```json
{
  "country": "Pakistan",
  "region": "Punjab",
  "topic": "Tenant Rights",
  "question": "My landlord wants to evict me without notice. What are my rights?",
  "history": [],
  "api_key": "gsk_..."
}
```

### Tax Module

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/tax/calculate` | Compute FBR 2024–25 tax liability |
| `POST` | `/api/tax/ai-advice` | AI tax optimization advice |
| `POST` | `/api/tax/savings-calculator` | Filer vs non-filer savings |
| `POST` | `/api/tax/generate-ntn-pdf` | NTN Application PDF |
| `POST` | `/api/tax/generate-itr-pdf` | Income Tax Return PDF |
| `POST` | `/api/tax/generate-wealth-pdf` | Wealth Statement PDF |
| `POST` | `/api/tax/generate-all-pdfs` | All 3 PDFs as base64 |
| `GET` | `/api/tax/slabs` | FBR 2024–25 tax slab table |

---

## 📚 RAG Knowledge Base

The legal KB (`rag_data/legal_kb.py`) contains curated, statute-referenced content injected into every AI prompt:

| Jurisdiction | Topics Covered |
|-------------|---------------|
| **Pakistan** | Tenant Rights (PRPA 2009), Employment Law (1968 Ordinance), Family Law (MFLO 1961), Business Registration (Companies Act 2017), Criminal Procedure (CrPC 1898), Consumer Rights, Property Law (TPA 1882), Contract Law (1872) |
| **United Kingdom** | Tenant Rights (Housing Act 1988), Employment Law (ERA 1996, Equality Act 2010) |
| **United States** | Tenant Rights, Employment Law (FLSA, Title VII, ADA) |

This ensures responses cite **real sections** — e.g., *"Under Section 14 of the Punjab Rented Premises Act 2009, eviction requires a court order..."*

---

## 📄 Generated Documents

All PDFs are professional A4 documents with:
- FBR official header (navy + gold branding)
- Structured data tables
- Tax computation with slab breakdown
- Signature and declaration sections
- FBR IRIS portal submission link

Sample documents are in the `documents/` folder.

---

## ✅ SRS Requirements Compliance

| SRS Requirement | Status |
|----------------|--------|
| Country + region selector | ✅ 12 countries, full region lists |
| Natural language legal questions | ✅ Chat interface with history |
| AI-generated jurisdiction-specific guidance | ✅ RAG + Groq LLaMA 3.3 70B |
| Plain language + law references | ✅ RAG injects statutes into prompts |
| Follow-up questions (conversation history) | ✅ Last 10 messages sent to API |
| Disclaimer on every response | ✅ Shown below every AI bubble |
| NTN registration step-by-step wizard | ✅ 4-step wizard |
| Generate NTN, ITR, Wealth Statement | ✅ Professional PDF (ReportLab) |
| PDF download | ✅ Direct browser download |
| Filer/non-filer comparison | ✅ Full rate table + calculator |
| Tax slab computation | ✅ FBR 2024–25 slabs, exact formula |
| Overseas Pakistani support | ✅ Citizenship type selector |
| Input validation (CNIC 13 digits) | ✅ Client + server validation |
| API failure graceful handling | ✅ Try/catch + toast notifications |
| Session-only data (privacy) | ✅ No server storage, key in browser |

---

## 🔒 Privacy & Security

- API key stored in browser memory **only** (never in server logs)
- No personal data (CNIC, income) persisted server-side
- All Groq calls made directly from the frontend to Groq's servers
- Backend PDF generation uses only the data provided in the current request

---

*Generated by LexAI — AI Legal Advisor & Pakistan Tax Filer*
*SRS: BSCS24041_ASM2 | Built with FastAPI + Groq + ReportLab*
setup Guide:
cd ~/Downloads/files
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload