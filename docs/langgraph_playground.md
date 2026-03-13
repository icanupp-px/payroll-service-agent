# LangGraph Playground (Local)

This project can be inspected in LangGraph Studio by running a local LangGraph API and connecting Studio to it.

## Prerequisites

- Docker + Docker Compose
- A valid `.env` file in the project root

## Start local LangGraph API

From the project root:

```bash
docker-compose up --build
```

This starts a local API at:

- `http://localhost:2024`

## Open LangGraph Studio

Use this URL:

- `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

## Graph available in this repo

Registered in `langgraph.json`:

- `payroll_service_graph` → `app.payroll_service_agent.graph.graph_builder:build_graph`

## Stop local API

```bash
docker-compose down
```

## Notes

- This setup uses `langgraph-cli[inmem]` for local development and Playground inspection.
- No remote LangGraph API URL is currently configured in this repository.
