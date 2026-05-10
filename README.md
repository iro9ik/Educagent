# EducAgent 

**EducAgent** is an advanced AI-powered educational assistant designed to streamline learning through a sophisticated multi-agent orchestration. It leverages RAG (Retrieval-Augmented Generation) to process documents and provides interactive tools like automated quizzes, multi-layered evaluations, and persistent student memory.

---

## 🤖 The Multi-Agent Ecosystem

EducAgent operates using a team of **10+ specialized agents**, each responsible for a specific part of the learning cycle:

1.  **Orchestrator Agent**: The brain of the system. It routes user requests and coordinates all sub-agents.
2.  **RAG Agent**: Expert in document retrieval. It searches your uploaded PDFs and files to find exact answers.
3.  **Search Agent**: Performs real-time internet research to supplement document knowledge.
4.  **Quiz Agent**: Generates high-quality, relevant assessment questions based on your documents.
5.  **Evaluation Agent (Layer 1)**: Performs strict, objective grading of student answers.
6.  **Explanation Agent (Layer 2)**: Analyzes student errors and provides deep pedagogical feedback.
7.  **Feedback Agent (Layer 3)**: Polishes the final response into clear, encouraging Markdown.
8.  **Memory Agent**: Tracks student performance and learning style over time to personalize future help.
9.  **Checker Agent**: A security layer that prevents hallucinations and ensures all answers are grounded in truth.
10. **Thinking/Fusion Agent**: Synthesizes complex information before presenting it to the user.

---

## 🚀 Getting Started

### Requirements
*   **Python 3.10+**
*   **Node.js 18+**
*   **Ollama**: For running local LLMs (Recommended: `qwen3:8b`).
*   **PostgreSQL**: For persistent storage (or fallback to local).

### Configuration
1.  **Environment Variables**:
    *   Rename `.env.example` to `.env`.
    *   Configure your `OLLAMA_BASE_URL` and `LLM_MODEL`.
2.  **Install Dependencies**:
    *   **Backend**: `pip install -r requirements.txt`
    *   **Frontend**: `cd frontend && npm install`

---

## How to Launch

The project includes a unified launcher for Windows users.

1.  **First Time Setup**: Run the database migration to prepare your storage:
    ```powershell
    python migrate.py
    ```

2.  **Start the Application**: Simply run the batch file in the root directory:
    ```powershell
    ./start.bat
    ```
    This script will:
    *   Activate the Python virtual environment.
    *   Start the **Uvicorn** backend server on port `8000`.
    *   Start the **Next.js** frontend dev server on port `3000`.

---

## 📂 Project Structure
*   `agents/`: Core multi-agent logic and individual agent definitions.
*   `api/`: FastAPI routes, database models, and streaming logic.
*   `rag/`: LlamaIndex implementation for document indexing and retrieval.
*   `storage/`: (Local) Your uploaded files and ChromaDB indices.
*   `frontend/`: Modern Next.js interface with real-time streaming and interactive quiz overlays.

---

## 🛡️ Security & Hardening
EducAgent uses a **3-Layer Validation Gate** for all assessments:
1.  **Immutability Gate**: Scores are locked during the first evaluation phase.
2.  **PED-Feedback Gate**: Detailed explanations are generated separately to avoid contradictory grading.
3.  **Presentation Gate**: Clean formatting ensures the student focuses on the learning outcome.

---
*Created for advanced educational automation.*
