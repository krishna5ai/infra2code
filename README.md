# Infra2Code AI

Turns a plain-English AWS requirement into least-cost, secure Terraform, with the architecture, request flow and a cost estimate.

## Run it
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env     # add your own ANTHROPIC_API_KEY
    uvicorn app.web:app --reload
Open http://127.0.0.1:8000

Command line: `python -m app.cli "web app with two servers and a database"`

Never commit your `.env` file.
