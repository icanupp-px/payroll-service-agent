# Payroll Service Agent - Workflow Guide

This document describes the current step-by-step runtime workflow for the Payroll Service Agent after the latest refactors.

---

## 🔄 High-Level Workflow

```
Streamlit startup -> run tests once -> Parse Prompt -> Build State -> Route to payroll_status_lookup Subgraph -> Fetch Data -> Compose Response -> Format & Display
```

---

## 📋 Detailed Step-by-Step Breakdown

### **Step 0: Streamlit Startup Test Gate**
**File**: `app/chatbot_local.py` -> `run_startup_test_suite()`

- On Streamlit server startup, the app executes:
  - `uv run --with pytest --with pytest-asyncio pytest tests`
- The result is cached with `st.cache_resource`, so this runs once per Streamlit process.
- If tests fail, the app:
  - shows failure output
  - blocks usage via `st.stop()`
- If tests pass, startup continues silently.

---

### **Step 1: User Submits Request via Streamlit UI**
**File**: `app/chatbot_local.py`

- User submits a payroll prompt in the chat UI.
- Typical prompts are either:
  - check-date status
  - current-payroll status

---

### **Step 2: Parse Prompt & Determine Flow Type**
**File**: `app/chatbot_local.py` -> `parse_prompt()`

- Regex parsing extracts optional check date.
- Intent detection decides whether prompt is current-payroll.
- `process_prompt()` sets:
  - `flow_type`: `check_date` or `current_payroll`
  - metadata defaults (`userguid`, `projection`, `x-payx-cnsmr`, `page`)
  - `checkdateasof`:
    - explicit check date for check-date flow
    - UTC(today - 30 days) for current-payroll flow

---

### **Step 3: Build Initial Graph State**
**File**: `app/orchestrator.py` -> `orchestrate_payroll_service_processing()`

- Orchestrator builds `PayrollServiceGraphState`.
- State includes prompt, flow type, metadata, and request id.
- Graph invocation returns final state that is mapped into `ProcessResponse`.

---

### **Step 4: Execute Top-Level LangGraph**
**File**: `app/payroll_service_agent/graph/graph_builder.py`

Top-level graph is intentionally shallow:

- `START -> request_router -> payroll_status_lookup -> END`

`payroll_status_lookup` is a compiled subgraph from `create_payroll_status_lookup_subgraph()`.

---

### **Step 5: Execute payroll_status_lookup Subgraph**
**Files**:
- `app/payroll_service_agent/graph/graph_builder.py`
- `app/payroll_service_agent/nodes/payroll_status_lookup.py`

Subgraph nodes:

1. `fetch_status_by_check_date`
2. `fetch_status_by_current_payroll`
3. `fetch_holds`
4. `compose_result`

Branch selector:

- `_select_payroll_status_branch()` in `payroll_status_lookup.py`

Decision logic:

- if `flow_type == current_payroll` -> `fetch_status_by_current_payroll`
- elif `metadata.checkDate` or `metadata.asof` exists -> `fetch_status_by_check_date`
- else -> `fetch_status_by_current_payroll`

---

### **Step 6a: Check-Date Status Flow**
**File**: `app/payroll_service_agent/nodes/payroll_status_lookup.py` -> `fetch_status_by_check_date()`

Steps:

1. Fetch payperiod payload through utility layer
2. Extract status map by event time + check date
3. Filter omitted statuses (`ENTRY`, `INITIAL`)
4. Fallback to check-date status map if event-time map is unavailable
5. Set final `state.status` and `state.payperiod_status_by_event_time`

---

### **Step 6b: Current-Payroll Status Flow**
**File**: `app/payroll_service_agent/nodes/payroll_status_lookup.py` -> `fetch_status_by_current_payroll()`

Steps:

1. Fetch payperiod payload through utility layer
2. Extract current-payroll candidates
3. Try LLM-assisted selection first
4. Fallback to heuristic closest-event-time selection
5. Set `state.status`, `state.payperiod_status_by_event_time`, and resolved `metadata.asof`

---

### **Step 7: Optional Holds Flow**
**File**: `app/payroll_service_agent/nodes/payroll_status_lookup.py` -> `fetch_holds()`

- Runs after status selection.
- If `payperiod_id` is missing, holds call is skipped.
- Holds errors do not fail the overall payroll response path.

---

### **Step 8: Compose Result & Return Response**
**Files**:
- `app/payroll_service_agent/nodes/payroll_status_lookup.py` -> `compose_result()`
- `app/orchestrator.py`

- `compose_result()` finalizes state (pass-through currently).
- Orchestrator maps graph state into `ProcessResponse`.
- `resolved_check_date` is populated from final `metadata.asof`.

---

### **Step 9: Format Output for UI**
**File**: `app/chatbot_local.py` -> `format_answer()`

- Uses explicit check date when present; otherwise uses `resolved_check_date` from response.
- Displays either:
  - `payperiod_status`, or
  - `payroll_status_by_submit_time` lines

---

## 📊 Data Flow Diagram

```
┌──────────────────────────┐
│ Streamlit Server Start   │
└────────────┬─────────────┘
       │
       ▼
┌──────────────────────────┐
│ run_startup_test_suite() │
│ uv run ... pytest tests  │
└───────┬─────────┬────────┘
    │         │
    │fail     │pass
    ▼         ▼
┌──────────────────────┐   ┌──────────────────────────┐
│ Show error + st.stop │   │ User Submits Prompt      │
└──────────────────────┘   └────────────┬─────────────┘
                    │
                    ▼
               ┌──────────────────────────┐
               │ parse_prompt()           │
               │ process_prompt()         │
               │ Build ProcessRequest     │
               └────────────┬─────────────┘
                    │
                    ▼
               ┌──────────────────────────┐
               │ Orchestrator             │
               │ Build GraphState         │
               └────────────┬─────────────┘
                    │
                    ▼
    ╔════════════════════════════════════════════════════════════╗
    ║ Top-Level Graph                                            ║
    ║ START -> request_router -> payroll_status_lookup -> END    ║
    ╚═══════════════════════┬════════════════════════════════════╝
                │
                ▼
    ╔════════════════════════════════════════════════════════════╗
    ║ payroll_status_lookup Subgraph                             ║
    ║ Branch: _select_payroll_status_branch()                    ║
    ║   ├─ fetch_status_by_check_date                            ║
    ║   └─ fetch_status_by_current_payroll                       ║
    ║          │                                                 ║
    ║          ▼                                                 ║
    ║  PayrollApiUtils.fetch_payperiods_payload                  ║
    ║    -> CrossAppMappingUtility.resolve_ca_client_account     ║
    ║    -> LlmSelectionUtility (assistive)                      ║
    ║          │                                                 ║
    ║          ▼                                                 ║
    ║  current flow: LLM selection -> heuristic fallback         ║
    ║          │                                                 ║
    ║          ▼                                                 ║
    ║  fetch_holds (optional) -> compose_result                  ║
    ╚═══════════════════════┬════════════════════════════════════╝
                │
                ▼
┌─────────────────────────────────────────────────────┐
│ Orchestrator maps final state -> ProcessResponse    │
│ resolved_check_date from metadata.asof              │
└──────────────────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│ format_answer() in Streamlit UI                    │
│ Render payperiod_status or status-by-submit-time   │
└─────────────────────────────────────────────────────┘
```

---

## 🧩 Utility Layer (Current Structure)

### **`payroll_status_lookup_utils.py`**
- `PayrollStatusLookupUtils`: status extraction/filtering helpers
- `PayrollApiUtils`: payperiod API query and call
- `CurrentPayrollSelectionUtils`: candidate extraction + heuristic + LLM result mapping

### **`crossapp_mapping_utility.py`**
- `CrossAppMappingUtility`: ENT -> CA mapping resolution
- deterministic extraction and normalization
- cross-app mapping API call helpers

### **`llm_selection_utility.py`**
- `LlmSelectionUtility`: all ChatOpenAI calls
- cross-app client account extraction prompt
- current-payroll record selection prompt

---

## 📝 Key Business Rules

- Omitted statuses: `ENTRY`, `INITIAL`
- Account resolution requires ENT-style prompt content
- LLM is assistive; deterministic fallback remains authoritative
- Current-payroll defaults `checkdateasof` to UTC(today - 30 days)
- Holds are optional and non-blocking

---

## 📚 Key Files Summary

| File | Purpose |
|------|---------|
| `app/chatbot_local.py` | Streamlit UI, startup test gate, prompt parsing, and response formatting |
| `app/orchestrator.py` | Builds graph state and maps final graph output into API response |
| `app/payroll_service_agent/graph/graph_builder.py` | Top-level graph and payroll-status subgraph wiring |
| `app/payroll_service_agent/nodes/payroll_status_lookup.py` | Node-level business logic for both payroll flows and holds |
| `app/payroll_service_agent/utils/payroll_status_lookup_utils.py` | Shared payroll status and payperiod helper utilities |
| `app/payroll_service_agent/utils/crossapp_mapping_utility.py` | Cross-app client account mapping utilities |
| `app/payroll_service_agent/utils/llm_selection_utility.py` | Centralized LLM utility for structured selections |


