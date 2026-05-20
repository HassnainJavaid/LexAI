# ⚖️ LexAI — AI Legal Advisor & Pakistan Tax Filer
### **Version 2.0.0 | BSCS24041 Assignment 2 & Semester Project**
> **RAG-Enhanced Legal Intelligence** · **FBR-Compliant PDF Generation** · **Groq LLaMA 3.3 70B** · **Secure Vault & Compliance Verification Engine**

---

## 📋 Project Overview

LexAI is a professional, full-stack legal artificial intelligence application that democratizes legal advisory services and streamlines Pakistan FBR tax compliance. Built with **Layered Clean Architecture**, the platform addresses and satisfies all functional and non-functional requirements detailed in the SRS document (`BSCS24041_ASM2_SRS.docx`).

### 📦 Application Modules

| Module | Description |
| :--- | :--- |
| ⚖️ **Global Legal Advisor** | RAG-grounded legal guidance across multiple jurisdictions (Pakistan, US, UK) that dynamically cites actual statutes and clauses. |
| 📄 **Pakistan Tax Filer** | 4-step interactive wizard that automatically generates official, professional FBR-compliant NTN applications, Income Tax Returns, and Wealth Statements. |
| 📊 **Filer vs Non-Filer Rates** | Visual comparison chart of withholding tax rates under the FBR 2024–25 budget alongside an interactive personal savings calculator. |
| 🔒 **Secure Vault & Audit** | Private document manager where users can upload contracts and run instant **AI Compliance Audits** using visual progress wheels and rating dashboards. |

---

## 🏗️ Architecture & Folder Structure

The repository uses a highly modular structure promoting separation of concerns across clean logical boundaries:

```
lexai/
├── backend/
│   ├── main.py              # FastAPI Web Application & 18+ endpoints
│   └── pdf_generator.py     # ReportLab universal PDF renderer (FBR Forms & Agreements)
├── rag_data/
│   └── legal_kb.py          # In-memory Legal RAG KB (Pakistan, UK, US statutes)
├── frontend/
│   └── index.html           # Courtroom-themed front-end layout (HTML5/CSS3/Vanilla JS)
├── database.py              # Thread-safe SQLite persistence manager
├── logger.py                # Security audit logging engine
├── requirements.txt         # Package dependencies
├── test_lexai.py            # Automated Pytest Suite (7 isolated tests)
└── USER_MANUAL.md           # Formal walk-through and operation guide
```

### Technology Stack
* **Backend Framework:** Python 3.10+, FastAPI, Uvicorn
* **AI & LLM Orchestrator:** Groq API (LLaMA 3.3 70B Free Tier)
* **Vector Database:** ChromaDB + SentenceTransformers (`all-MiniLM-L6-v2`)
* **Document Compiler:** ReportLab 4.5+ (Standard A4 layout)
* **Security & Auth:** PyJWT (Token Sessions) + Passlib / Bcrypt (Hashing)
* **Concurrency:** Native `threading.Lock()` safeguards

---

## 🚀 Quick Start Guide

### Step 1 — Paste/Configure Groq API Key
1. Get a free API key at [console.groq.com](https://console.groq.com).
2. Set it up inside a local `.env` file in the root directory:
   ```env
   GROQ_API_KEY=gsk_your_key_here
   SECRET_KEY=your_jwt_secret_key_here
   ALGORITHM=HS256
   ```

### Step 2 — Install Dependencies & Seed Vector DB
Ensure you have active virtual settings:
```bash
# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Seed the RAG legal constraints database
python3 batch_ingest.py
```

### Step 3 — Launch the Application
Start the FastAPI uvicorn workers:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
* **App URL:** http://localhost:8000
* **API Interactive Docs:** http://localhost:8000/docs

---

## 🔌 API Reference

### Auth & Security
* `POST /api/v1/auth/signup` - Creates an account and hashes credentials.
* `POST /api/v1/auth/login` - Validates credentials and returns a secure JWT token.
* `GET /api/v1/notifications` - Fetches user notifications.

### Legal Advisor Chat
* `POST /api/legal/chat` - Generates a jurisdiction-specific RAG brief.
* `POST /api/legal/document` - Orchestrates legal contracts (returns text and PDF bytes).

### Tax Compliance Wizard
* `POST /api/tax/calculate` - Computes FBR 2024–25 tax liability.
* `POST /api/tax/generate-ntn-pdf` - Renders professional NTN Application form.
* `POST /api/tax/generate-itr-pdf` - Renders professional Income Tax Return form.
* `POST /api/tax/generate-wealth-pdf` - Renders professional Wealth Statement form.

### Secure Vault & Audit Engine
* `POST /api/v1/documents/upload` - Securely uploads user legal agreements.
* `GET /api/v1/documents/list` - Lists uploaded files in user vault.
* `POST /api/v1/documents/verify/{doc_id}` - Runs a compliance audit over document clauses, outputting circular progress metric scores and structured warning checklists.

---

## ✅ SRS Requirements Compliance Matrix

| Section | SRS Core Requirement | Verification Method / Compliance Hook | Status |
| :--- | :--- | :--- | :---: |
| **Legal** | Country & Region contexts | Dynamic selectors (12 countries, custom state dropdowns) | **✅ Passed** |
| **Legal** | Natural language queries | Conversational interface with 10-message sliding window | **✅ Passed** |
| **Legal** | AI Statute References | RAG knowledge base automatically injects sections into Groq | **✅ Passed** |
| **Legal** | Formal Legal Disclaimers | Automatically rendered beneath every single AI output | **✅ Passed** |
| **Tax** | NTN Registration Wizard | Step-by-step form validator separating assets, info, income | **✅ Passed** |
| **Tax** | Professional A4 Forms | ReportLab compilation (IRIS Portal links, declarations) | **✅ Passed** |
| **Tax** | Savings Comparator | Rates calculator matching the official 2024–25 withholding rules | **✅ Passed** |
| **Vault** | Encrypted/Secure Storage | User document paths mapped via SQLite DB permissions | **✅ Passed** |
| **Vault** | Compliance Auditor | Deep-learning clause analyzer & circular audit score display | **✅ Passed** |
| **Security** | Audits & Security logs | Real-time IP and transaction logging saved in database | **✅ Passed** |

---

## 🔒 Privacy & Security Actions
1. **Cryptographic Hashes:** All password storage uses standard `bcrypt` hashing algorithms.
2. **Access Safeguards:** Session authorization is completely checked via `HS256` token verifications.
3. **Database Concurrency:** Database interactions are synchronized with `db_lock` to block SQLite write collisions.
4. **Data Isolation:** Uploaded user files are completely isolated by owner email addresses and secure server directories.

---
*Developed by LexAI team — AI Legal Advisor & Pakistan Tax Filer Platform*
*BSCS24041 Assignment 2 | Fully Tested & Production-Ready*