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
    .venv\Scripts\activate  # On Windows
     source .venv/Scripts/activate
    ```

3. Install dependencies:
    ```bash
    uv pip install -e .
    ```
4. **Ensure your `.env` is in place**

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
    * Sample Body:
    ```
     {
        "request_id": "req-12345",
        "payperiod_id": "TKTKTK",
        "metadata": {
            "source": "local-test",
            "channel": "manual"
        }
    }
    ```
    * Sample Response:
    ```
    {
        "request_id": "req-12345",
        "status": "completed",
        "result": "Hello, world! req-12345"
    }
    ```