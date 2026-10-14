# Interior AI Customer Support — Multi-Agent System

An AI-powered customer support system developed for **Blue Whale Interior Solutions** using Python, AutoGen, OpenAI, FastAPI, and SQLite.

## Project Overview

The system uses a manager agent and specialist categories to classify customer queries and generate company-specific responses.

## Key Features

- **Multi-Agent System:** Manager agent with four specialist categories.
- **Query Classification:** Routes queries into relevant interior and product categories.
- **Company Profile Integration:** Uses company-specific information and business rules.
- **Conversation Memory:** Stores and retrieves chat history using SQLite.
- **REST API:** Provides endpoints for customer chat and API health checks.
- **Webhook Endpoint:** Includes an initial WhatsApp webhook verification and event-receiving implementation.

## Agent Categories

1. Home Interior
2. Commercial Interior
3. UPVC/PVC Interior
4. B2B Products

## Technologies Used

- Python 3.12
- AutoGen
- OpenAI GPT-4o-mini
- FastAPI
- SQLite
- JSON
- Uvicorn

## Project Files

- `main.py` — Manager agent, specialist categories, and customer query handling.
- `api.py` — FastAPI application, chat endpoint, and initial webhook endpoints.
- `memory.py` — SQLite conversation memory management.
- `company_profile.json` — Company information, service categories, and business rules.
- `.gitignore` — Excludes environment files and generated data from Git.

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/naagharamanas-arch/interior-ai-customer-support.git
cd interior-ai-customer-support
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```cmd
.venv\Scripts\activate
```

### 3. Install dependencies

Install the required packages used by the project, including FastAPI, Uvicorn, AutoGen, OpenAI, and python-dotenv.

If a `requirements.txt` file is provided, run:

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project directory and configure the required credentials:

```env
OPENAI_API_KEY=your_openai_api_key
WHATSAPP_VERIFY_TOKEN=your_webhook_verify_token
```

Replace the example values with your own credentials. Never commit `.env` to GitHub.

### 5. Run the application

Run the FastAPI server:

```bash
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Check the health endpoint:

```text
http://localhost:8000/
```

The chat endpoint is:

```text
POST http://localhost:8000/chat
```

## Testing Status

The following components have been tested successfully:

- Company profile loading.
- SQLite conversation memory.
- Customer query classification and specialist-agent responses.
- FastAPI health endpoint.
- Chat API returning a successful response.

## Current Limitations

The WhatsApp webhook implementation is at an initial stage. End-to-end integration for receiving WhatsApp messages, processing them through the AI agents, and sending automated replies has not yet been completed.

## Security

API keys and verification tokens must be stored in environment variables and must not be committed to the repository.

## Project Status

The core AI customer support application and chat API have been implemented and tested. WhatsApp end-to-end integration remains future work.
