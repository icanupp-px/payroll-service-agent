# Payroll Service Agent - Workflow Guide

This document describes the current runtime workflow for the Payroll Service Agent after the latest refactors and holds-flow additions.

---

## High-Level Workflow

```text
Streamlit startup -> run tests once -> Parse Prompt -> Build Request -> Orchestrator -> LangGraph Subgraph ->
Status Fetch -> Optional Holds Lookup -> Compose Result -> Format & Display
```

---

## Detailed Step-by-Step Breakdown

### Step 0: Streamlit Startup Test Gate
File: `app/chatbot_local.py` -> `run_startup_test_suite()`

- On Streamlit startup, the app runs:
  - `uv run --with pytest --with pytest-asyncio pytest tests`
- The result is cached with `st.cache_resource`, so the suite runs once per Streamlit process.
- If tests fail:
  - the UI shows the test output
  - the app stops with `st.stop()`
- If tests pass, startup continues silently.

---

### Step 1: User Submits Request via Streamlit UI
File: `app/chatbot_local.py`

- User enters a prompt in the Streamlit UI.
- Supported prompt types are:
  - check-date payroll status
  - current-payroll status
  - payroll holds lookup

Examples:

- `status for ENT:... check date 2025-03-31`
- `What is the status of my current payroll for ENT:...?`
- `Has payroll been entered but on hold for ENT:...?`
- `Has payroll been entered but on hold for check date 2025-11-03 for ENT:...?`

---

### Step 2: Parse Prompt & Determine Flow Type
File: `app/chatbot_local.py` -> `parse_prompt()` and `process_prompt()`

- Regex parsing extracts an optional check date.
- Intent detection uses these patterns:
  - `CHECK_DATE_PATTERN`
  - `EXPLICIT_CHECK_DATE_PATTERN`
  - `CURRENT_PAYROLL_PATTERN`
  - `PAYROLL_STATUS_INTENT_PATTERN`
  - `HOLDS_INTENT_PATTERN`
- `parse_prompt()` returns:
  - `check_date`
  - `is_current_payroll_prompt`
  - `is_holds_prompt`

`process_prompt()` then builds metadata defaults:

- `userguid = CA:12345`
- `projection = payperiod`
- `x-payx-cnsmr = CA DOMAIN`

- holds keywords (`hold`, `on hold`, `payroll hold`) -> `flow_type = holds`
- otherwise current-payroll keywords with no explicit date -> `flow_type = current_payroll`

Date handling rules:

- check-date flow:
  - `metadata.asof = check_date`
  - `metadata.checkdateasof = check_date`
- current-payroll flow:
  - `metadata.checkdateasof = UTC(today - 30 days)`
- holds flow with explicit date:
  - `metadata.asof = check_date`
  - `metadata.checkdateasof = check_date`
- holds flow without explicit date:
  - `metadata.checkdateasof = UTC(today - 30 days)`

---

### Step 3: Build Initial Graph State
File: `app/orchestrator.py` -> `orchestrate_payroll_service_processing()`

- The orchestrator builds `PayrollServiceGraphState` with:
  - `request_id`
  - `prompt`
  - `flow_type`
  - `metadata`
  - empty status/result fields
- `flow_type` is normalized and copied into metadata.
- The graph is invoked and the final state is mapped into `ProcessResponse`.

Important mapped fields:

- `payperiod_status`
- `resolved_check_date`
- `payroll_status_by_submit_time`
- `payperiod_holds`

---

### Step 4: Execute Top-Level LangGraph
File: `app/payroll_service_agent/graph/graph_builder.py`

The top-level graph is intentionally shallow:

```text
START -> request_router -> payroll_status_lookup -> END
```

`payroll_status_lookup` is a compiled subgraph created by `create_payroll_status_lookup_subgraph()`.

---

### Step 5: Execute payroll_status_lookup Subgraph
Files:

- `app/payroll_service_agent/graph/graph_builder.py`
- `app/payroll_service_agent/nodes/payroll_status_lookup.py`

Subgraph nodes:

1. `fetch_status_by_check_date`
2. `fetch_status_by_current_payroll`
3. `fetch_holds`
4. `compose_result`

Branch selector:

- `_select_payroll_status_branch()`

Branching rules:

- if `flow_type == current_payroll` -> `fetch_status_by_current_payroll`
- if `flow_type == holds`:
  - with `metadata.asof` or `metadata.checkDate` -> `fetch_status_by_check_date`
  - otherwise -> `fetch_status_by_current_payroll`
- otherwise if a date is present -> `fetch_status_by_check_date`
- otherwise -> `fetch_status_by_current_payroll`

After either status node completes, the graph always continues to `fetch_holds`, then `compose_result`.

---

### Step 6a: Check-Date Status Flow
File: `app/payroll_service_agent/nodes/payroll_status_lookup.py` -> `fetch_status_by_check_date()`

Steps:

1. Read `requested_check_date` from `metadata.asof` or `metadata.checkDate`
2. Call `PayrollApiUtils.fetch_payperiods_payload(...)`
3. Extract status map by event time for the requested check date
4. Filter omitted statuses
5. If event-time map is empty, fall back to check-date map
6. Build `state.status` from all allowed statuses for that check date
7. If this is a holds flow, attempt to extract a qualifying `payperiod_id`

Qualifying rule for holds in check-date flow:

- A `payperiod_id` qualifies only when `payPeriodStatusValue` is one of:
  - `Released`
  - `Processing`
- Matching is case-insensitive.

If no qualifying pay period exists, `state.payperiod_id` remains unset.

---

### Step 6b: Current-Payroll Status Flow
File: `app/payroll_service_agent/nodes/payroll_status_lookup.py` -> `fetch_status_by_current_payroll()`

Steps:

1. Call `PayrollApiUtils.fetch_payperiods_payload(...)`
2. Build candidate rows using `CurrentPayrollSelectionUtils.extract_payperiod_candidates()`
3. Each candidate carries:
  - `checkDate`
  - `payPeriodStatusValue`
  - `payPeriodStatusEventTime`
  - `payPeriodId`
4. Try LLM selection first through `CurrentPayrollSelectionUtils.llm_current_selection()`
5. Fall back to `heuristic_current_selection()` if LLM is unavailable or unusable
6. Set:
  - `state.status`
  - `state.payperiod_status_by_event_time`
  - `metadata.asof` from the selected check date
7. If this is a holds flow, copy the selected `payperiod_id` only when selected status is:
  - `Released`
  - `Processing`

Matching is also case-insensitive here.

If the selected current payroll has status `Completed`, `Completed by MEC`, `Reissued`, etc., then `payperiod_id` is intentionally not passed to the holds API.

---

### Step 6c: Payperiod API Request Construction
File: `app/payroll_service_agent/utils/payroll_status_lookup_utils.py` -> `PayrollApiUtils.fetch_payperiods_payload()`

This utility is shared by both status flows.

Responsibilities:

- Resolve `x-payx-cnsmr`
- Resolve CA client account from ENT prompt content through `CrossAppMappingUtility`
- Persist the resolved CA client account into shared metadata as `cltacctnbrs`
- Build the payperiod API query with:
  - `status = Completed,Completed by MEC,Processing,Reissued,Released,Reversed,Time Delay`
  - `projection = payperiod`
  - `userguid = CA:12345`
  - `cltacctnbrs = resolved CA client account`
  - `page = 0`
  - `asof/checkdateasof` when applicable

This metadata persistence matters because downstream holds lookup can reuse `cltacctnbrs` without re-resolving it.

---

### Step 7: Holds Flow
File: `app/payroll_service_agent/nodes/payroll_status_lookup.py` -> `fetch_holds()`

`fetch_holds()` always runs after the status node, but behavior depends on whether a qualifying `payperiod_id` is available.

Path A: qualifying `payperiod_id` exists

1. Read `payperiod_id` from state or metadata
2. Resolve `x-payx-cnsmr`
3. Read `cltacctnbrs` from metadata
4. If `cltacctnbrs` is missing, resolve it again through `CrossAppMappingUtility`
5. Build holds API query with:
   - `userguid`
   - `cltacctnbrs`
6. Call `PAYROLL_HOLDS_API_BASE_URL/{payperiod_id}?userguid=...&cltacctnbrs=...`
7. Extract `content.clientPayrollHolds[]`
8. Keep only these fields per hold:
   - `systemHoldType`
   - `clientPayrollHoldId`
   - `payPeriodId`
   - `active`
9. Store the list in `state.holds`

Path B: qualifying `payperiod_id` does not exist during holds flow

- No holds API call is made.
- `state.holds` is set to an empty list.
- The UI then renders an explicit no-holds response.

This usually means the selected payroll status did not meet the qualifying rule (`Released` or `Processing`).

Path C: non-holds flow with no `payperiod_id`

- Holds lookup is skipped quietly because the request was not a holds question.

---

### Step 8: Compose Result & Return Response
Files:

- `app/payroll_service_agent/nodes/payroll_status_lookup.py` -> `compose_result()`
- `app/orchestrator.py`

- `compose_result()` is currently a pass-through node.
- The orchestrator maps final state into `ProcessResponse`.
- `resolved_check_date` is read from `metadata.asof`.
- `payperiod_holds` is surfaced when available.

---

### Step 9: Format Output for UI
File: `app/chatbot_local.py` -> `format_answer()`

Formatting priority is:

1. If `response.payperiod_holds is not None`
   - empty list -> `No holds were found for your payroll (check date: ...)`
   - one hold -> return single hold reason
   - multiple holds -> return multiple `Hold Reason = ...` lines
2. Else if `response.payperiod_status` exists
   - render a single payperiod status line
3. Else if `response.payroll_status_by_submit_time` exists
   - render one line per submission time
4. Else
   - show fallback no-status message

This means holds prompts no longer fall back to the generic payroll-status sentence once the holds path has been entered.

---

## Data Flow Diagram

```text
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
        │ fail    │ pass
        ▼         ▼
┌──────────────────────┐   ┌──────────────────────────┐
│ Show error + st.stop │   │ User submits prompt      │
└──────────────────────┘   └────────────┬─────────────┘
                                        │
                                        ▼
                           ┌──────────────────────────┐
                           │ parse_prompt()           │
                           │ detect flow_type         │
                           │ build ProcessRequest     │
                           └────────────┬─────────────┘
                                        │
                                        ▼
                           ┌──────────────────────────┐
                           │ Orchestrator             │
                           │ build GraphState         │
                           └────────────┬─────────────┘
                                        │
                                        ▼
╔══════════════════════════════════════════════════════════════════════╗
║ Top-Level Graph                                                     ║
║ START -> request_router -> payroll_status_lookup -> END             ║
╚═══════════════════════════════┬══════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════════════╗
║ payroll_status_lookup Subgraph                                      ║
║ Branch: _select_payroll_status_branch()                             ║
║   ├─ check_date -> fetch_status_by_check_date                       ║
║   ├─ current_payroll -> fetch_status_by_current_payroll             ║
║   └─ holds -> check-date path or current-payroll path               ║
║                                                                      ║
║  PayrollApiUtils.fetch_payperiods_payload                           ║
║    -> CrossAppMappingUtility.resolve_ca_client_account_number       ║
║    -> persist metadata.cltacctnbrs                                  ║
║                                                                      ║
║  current-payroll path                                                ║
║    -> LLM selection                                                  ║
║    -> heuristic fallback                                             ║
║                                                                      ║
║  holds qualification                                                 ║
║    -> only Released / Processing produce payperiod_id               ║
║                                                                      ║
║  fetch_holds                                                         ║
║    -> if payperiod_id exists, call holds API                        ║
║    -> else for holds flow, return []                                ║
║                                                                      ║
║  compose_result                                                      ║
╚═══════════════════════════════┬══════════════════════════════════════╝
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│ Orchestrator maps final state -> ProcessResponse                  │
│ resolved_check_date from metadata.asof                            │
└───────────────────────────────┬────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│ format_answer() in Streamlit UI                                   │
│ holds list -> hold reasons / no-holds message                     │
│ otherwise -> payroll status output                                │
└────────────────────────────────────────────────────────────────────┘
```

---

## Utility Layer

### `payroll_status_lookup_utils.py`

- `PayrollStatusLookupUtils`
  - status extraction helpers
  - omitted-status filtering
  - qualifying `payperiod_id` lookup for holds flow
- `PayrollApiUtils`
  - payperiod API query construction and execution
  - CA account persistence into metadata
- `CurrentPayrollSelectionUtils`
  - candidate extraction
  - heuristic selection
  - LLM-selection mapping back to `payperiod_id`

### `crossapp_mapping_utility.py`

- `CrossAppMappingUtility`
  - ENT -> CA account resolution
  - deterministic parsing first
  - optional LLM assist when needed

### `llm_selection_utility.py`

- `LlmSelectionUtility`
  - ChatOpenAI-backed structured selection helpers
  - current-payroll selection
  - cross-app CA extraction assist

---

## Key Business Rules

- Omitted statuses: `ENTRY`, `INITIAL`
- ENT account must be present in prompt for account resolution
- LLM is assistive only; deterministic fallback remains available
- current-payroll and holds-without-date default `checkdateasof` to `UTC(today - 30 days)`
- Holds API is only called when a qualifying status produces a `payperiod_id`
- Qualifying statuses for holds lookup are currently:
  - `Released`
  - `Processing`
- Holds flow is non-blocking:
  - missing qualifying `payperiod_id` -> empty holds result
  - holds API errors -> overall workflow still completes

---

## Key Files Summary

| File | Purpose |
|------|---------|
| `app/chatbot_local.py` | Streamlit UI, startup test gate, prompt parsing, flow detection, and response formatting |
| `app/orchestrator.py` | Builds graph state and maps final graph output into API response |
| `app/payroll_service_agent/graph/graph_builder.py` | Top-level graph and payroll-status subgraph wiring |
| `app/payroll_service_agent/nodes/payroll_status_lookup.py` | Node-level business logic for check-date, current-payroll, and holds flows |
| `app/payroll_service_agent/utils/payroll_status_lookup_utils.py` | Shared status extraction, payperiod lookup, and payperiod API utilities |
| `app/payroll_service_agent/utils/crossapp_mapping_utility.py` | ENT -> CA client account resolution helpers |
| `app/payroll_service_agent/utils/llm_selection_utility.py` | Centralized LLM utility for structured selections |


