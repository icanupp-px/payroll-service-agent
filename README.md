# Payroll Service Agent  

A LangGraph-based agent for processing payroll service requests using FastAPI and OpenAI.

## Project structure
This project is organized to support modular, testable, and scalable LangGraph-based agents. Below is a breakdown of the key directories and files.

```bash
app/
├── main.py                               # Entrypoint: runs LangGraph or starts FastAPI server
├── orchestrator.py                       # Orchestrates high-level workflows
│
├── api/                                  # FastAPI routing and request/response models
│   ├── routes.py                         # Defines public API endpoints
│   └── models/                           # Pydantic models for external request/response payloads
│       ├── input.py
│       └── output.py
│
├── payroll_service_agent/                # Core logic for the payroll service agent
│   ├── config/                           # Configuration files
│   │   ├── config.py                     # Loads config values from .env or YAML
│   │
│   ├── graph/                            # LangGraph graph builder and shared state definitions
│   │   ├── graph_builder.py              # Wires up LangGraph nodes and edges
│   │   └── states/                       # Pydantic models for the subgraphs
│   │       ├── payroll_status_lookup.py  # State for lookup subgraph
│   │
│   ├── models/                           # LLM output schemas used for structured parsing
│   │   ├── payroll_status_lookup.py      # Structured outputs for lookup graph
│   │
│   ├── nodes/                            # LangGraph-compatible node functions (SubGraphs)
│   │   ├── payroll_status_lookup.py      # TKTKTKTKTK
│   │   └── utils/                        # Shared helpers for nodes (internal)
│   │
│   ├── prompts/                          # YAML-based prompt templates used by each node
│   │   ├── payroll_status_lookup.yml     #
│   │
│   ├── libraries/                        # Customizable instructions for the agent 
│   │
│   └── utils/                            # Shared helpers and infrastructure
```

### 📌 Notes:
- **LangGraph** handles the node orchestration and state transitions.
- Each node uses its own **structured prompt**, stored in YAML and loaded dynamically.
- The agent is built for **clean separation of reasoning, validation, and submission logic**.

## Getting Started
1. Clone the repository:

    ```bash
    git TKTKTKTKTK &&
    cd payroll-service-agent
    ```

2. Copy the environment template and fill in your values:

    ```bash
    cp .env.example .env
    ```

## Running the Service
1. Install uv (if not already installed):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2. Create and activate virtual environment:
    ```bash
    uv venv
    source .venv/bin/activate  # On Unix/macOS
    # or
    .venv\Scripts\Activate.ps1  # On Windows PowerShell
    ```

3. Install dependencies:
    ```bash
    uv pip install -e .
    ```
4. **Ensure your `.env` is in place**

### Client Account Resolution (ENT -> CA)

- The workflow now resolves client account number indirectly.
- Supported input modes are:
    - Check-date flow
    - Current-payroll flow
- payperiod_id-based input is not part of the user/API workflow.
- Provide the ENT client account number in the request prompt (for example: `ENT:008WQ28JLJR1C7M97QIQ`).
- No metadata input is required from chatbot users.
- Internal defaults used by the service:
    - `userguid`: `CA:12345`
    - `projection`: `payperiod`
    - `page`: `0`
    - `x-payx-cnsmr`: `CA DOMAIN`
- Additional payperiod request rule:
    - If prompt contains a check date, `checkdateasof` is set to that date.
    - For current-payroll prompts, `checkdateasof` is set to system date minus 30 days (UTC).
- `Entry` and `Initial` payroll statuses are omitted from this flow.
- The service calls:
    - `https://ca-ose-crossappmappings-v1-svc-pyx.n2a-lb.paychex.com/crossappmappings?userguid=<...>&cltacctnbrs=<ENT...>`
    - Header: `x-payx-cnsmr: CA DOMAIN` (or your environment-specific consumer value)
- The response field `content.crossappmappings[].caClientAcctNbr` is extracted (via LLM-assisted parsing), normalized, and assigned to `cltacctnbrs` for downstream payperiod API calls.
- If ENT is missing in prompt, or no valid `caClientAcctNbr` is found, the response is:
    - `Please send a valid Client Account number`

5. **Stop any previously running container and delete volumes**
   ```bash
   docker-compose down -v
   ```
   This step is necessary if any project dependencies change and you need to recreate the virtual environment. Otherwise the virtual environment is persisted between container startups in an anonymous volume.

6. **Build & start the service:**
   ```bash
   docker-compose up --build
   ```
7. **Access the services:**
   * POST: http://localhost:8000/api/v1/process
    * Supported POST workflow: check_date-based request
    * LangGraph Playground API: http://localhost:2024
    * LangGraph Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
        * Sample Request/Response - Flow (by check_date):
        ```json
        {
            "request_id": "req-12346",
            "prompt": "status for ENT:008WQ28JLJR1C7M97QIQ check date 2025-03-31",
            "check_date": "2025-03-31"
        }
        ```
        ```json
        {
            "request_id": "req-12346",
            "payrollStatusBySubmitTime": {
                "2025-03-31T10:11:12Z": "Initial",
                "2025-03-31T12:30:00Z": "Completed by MEC"
            }
        }
        ```

## LangGraph Playground

- Local setup and Studio connection steps: [docs/langgraph_playground.md](docs/langgraph_playground.md)

## Local Chatbot UI (No New API Endpoint)

If you want a chatbot in the browser without creating a separate chatbot endpoint, run the local Streamlit UI. It calls the orchestrator directly in-process.

Chatbot supports:

- Check-date prompts
- Current-payroll prompts

1. Create a virtual environment (first time only):

    ```bash
    uv venv
    ```

2. Activate the virtual environment:

    ```bash
    source .venv/bin/activate  # Unix/macOS
    # or
    .venv\Scripts\Activate.ps1  # Windows PowerShell
    ```

3. Install dependencies:

    ```bash
    uv pip install -e .
    ```

4. Start the chatbot UI:

    ```bash
    streamlit run app/chatbot_local.py --server.port 8501
    ```

5. Open in Chrome:

    - http://localhost:8501

Prompt examples:

- "status for ENT:008WQ28JLJR1C7M97QIQ check date 2025-03-31"
- "what is my current payroll status for ENT:008WQ28JLJR1C7M97QIQ"