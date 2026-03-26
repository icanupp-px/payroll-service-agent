# Payroll Service Agent: Sample Prompts & Responses

Complete coverage of all possible user prompts, flow types, positive/negative scenarios, and expected responses based on the current workflow diagram.

---

## ⚠️ IMPORTANT: ENT ID Must Be in Prompt

**All prompts MUST include ENT ID directly in the prompt text** (not in metadata).

- **ENT ID Format:** `ENT:xxxxxxxxxxxxxxxxxxxxx` 
- **Examples:** `ENT:008WQ28JLJR1C7M97QIQ`, `ENT:008WQ28JLWTDMQHZ19WM`
- **Placement:** Embed in the prompt itself
  - ✅ Correct: `"What is my status for ENT:008WQ28JLJR1C7M97QIQ check date 2025-03-31?"`
  - ❌ Wrong: `"What is my status for check date 2025-03-31?"` (missing ENT ID)
- **Purpose:** Used by CrossAppMappingUtility to map ENT ID → CA (Client Account)
- **If Missing:** System returns: `"Please send a valid Client Account number"`

**Note:** The ENT ID may also be extracted from the user session context if available, but explicit inclusion in the prompt is the most reliable method.

---

## 1. CHECK_DATE Flow (Get status for a specific check date)

### ✅ Positive Scenarios

#### 1.1 Basic Check Date Query - Status Found
**Prompt:** What is my payroll status for ENT:008WQ28JLJR1C7M97QIQ check date 2024-03-15?

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt)

**UI Output:**
```
✓ Your payroll status for check date 2024-03-15 is: Released
```

---

#### 1.2 Check Date Query - Multiple Status Events (by submission time)
**Prompt:** Show me all payroll status updates for ENT:008WQ28JLJR1C7M97QIQ check date 2024-02-29

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt)

**UI Output:**
```
Status History for Check Date 2024-02-29:
  • 2024-02-28 14:32 UTC: Initial
  • 2024-02-29 08:15 UTC: Processing
  • 2024-02-29 16:45 UTC: Released
```

---

#### 1.3 Check Date with Holds
**Prompt:** Check my status and any holds for ENT:008WQ28JLJR1C7M97QIQ check date 2024-03-01

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt)

**UI Output:**
```
✓ Your payroll status for check date 2024-03-01 is: Released

⚠️ Active Holds on This Check:
  1. Tax Compliance Hold (Hold ID: HOLD-5001)
  2. Court Order - Garnishment (Hold ID: HOLD-5002)

Contact HR for more information about these holds.
```

---

### ❌ Negative Scenarios

#### 1.4 Check Date - No Status Found (Invalid/Future Date)
**Prompt:** What is my payroll status for ENT:008WQ28JLJR1C7M97QIQ check date 2099-12-31?

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt)

**UI Output:**
```
❌ No payroll records found for check date 2099-12-31.
   This date may be in the future or outside your payroll history.
```

---

#### 1.5 Check Date - Invalid Date Format (Validation Error)
**Prompt:** What's my status for ENT:008WQ28JLJR1C7M97QIQ on 03/15/24?

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt)

**UI Output:**
```
❌ Error: Invalid date format. Please use YYYY-MM-DD format (e.g., 2024-03-15).
Example: "What is my payroll status for 2024-03-15?"
```

---

#### 1.6 Check Date - Missing Required Field (No ENT ID)
**Prompt:** What is my payroll status for check date 2024-03-20?

**ENT ID Format:** Missing/Not provided in prompt - Will fail

**UI Output:**
```
❌ ValidationError: Please provide checkdate to get the payroll status.
Example: "What is my payroll status for 2024-03-15?"
```

---

#### 1.7 Check Date - Status Not ENTRY or INITIAL (e.g., Pending, Draft)
**Prompt:** Check my status for ENT:008WQ28JLJR1C7M97QIQ check date 2024-03-20

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt)

**UI Output:**
```
ℹ️ No final payroll status available for check date 2024-03-20 yet.
   Status may still be in draft or initial review stage.
```

---

#### 1.8 Check Date - API Timeout / Service Error
**Prompt:** What's my payroll status for ENT:008WQ28JLJR1C7M97QIQ check date 2024-03-15?

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt)

**UI Output:**
```
❌ Unable to fetch payroll status at this time.
   Please try again later or contact support.
(Error: Service unavailable - request timeout)
```

---

---

## 2. CURRENT_PAYROLL Flow (Get current/latest payroll status)

### ✅ Positive Scenarios

#### 2.1 Current Payroll - Basic Query
**Prompt:** What is my current payroll status for ENT:008WQ28JLJR1C7M97QIQ?

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt - no date, uses current - 30 days)

**UI Output:**
```
✓ Your current payroll status is: Released
   Last check date: 2024-03-15
```

---

#### 2.2 Current Payroll - LLM Selected (Multiple Candidates)
**Prompt:** Show me my latest pay status for ENT:008WQ28JLJR1C7M97QIQ

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt - LLM selects from candidates)

**UI Output:**
```
✓ Your current payroll status is: Processing
   Latest pay period: 2024-03-22
   Expected release: 2024-03-25
```

---

#### 2.3 Current Payroll - Heuristic Selection (No LLM)
**Prompt:** What's my most recent payroll for ENT:008WQ28JLJR1C7M97QIQ?

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt - heuristic selection)

**UI Output:**
```
✓ Your current payroll status is: Released
   Check date: 2024-03-14
```

---

#### 2.4 Current Payroll with Holds
**Prompt:** Tell me my current status and any holds for ENT:008WQ28JLJR1C7M97QIQ

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt - fetches holds if payperiod qualifies)

**UI Output:**
```
✓ Your current payroll status is: Released
   Check date: 2024-03-15

⚠️ Active Hold:
  • Direct Deposit Setup Pending (Hold ID: HOLD-6001)

Please complete setup to receive your payment.
```

---

### ❌ Negative Scenarios

#### 2.5 Current Payroll - No Records in Last 30 Days
**Prompt:** What is my current payroll status for ENT:NEW-EMPLOYEE-001?

**ENT ID Format:** `ENT:NEW-EMPLOYEE-001` (embedded in prompt - new employee, no history)

**UI Output:**
```
ℹ️ No payroll records found in the last 30 days.
   Please contact HR if you believe this is incorrect.
```

---

#### 2.6 Current Payroll - LLM Selection Fails (Heuristic Fallback)
**Prompt:** Show my latest payroll info for ENT:008WQ28JLJR1C7M97QIQ

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt - LLM fails, fallback used)

**UI Output:**
```
✓ Your current payroll status is: Released
   Check date: 2024-03-10
   (Selected using standard logic)
```

---

#### 2.7 Current Payroll - API Failure
**Prompt:** What's my current status for ENT:008WQ28JLJR1C7M97QIQ?

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt - API unavailable)

**UI Output:**
```
❌ Unable to retrieve current payroll status.
   The payroll service is temporarily unavailable.
   Please try again in a few moments.
```

---

#### 2.8 Current Payroll - Account Resolution Fails (Invalid ENT)
**Prompt:** Get my current payroll for ENT:INVALID-ACCOUNT-999

**ENT ID Format:** `ENT:INVALID-ACCOUNT-999` (embedded in prompt - Cannot map to CA account)

**UI Output:**
```
❌ Unable to find your payroll account.
   Please verify your account information with HR.
(Error: Account mapping failed)
```

---

---

## 3. HOLDS Flow (Get holds information)

### ✅ Positive Scenarios

#### 3.1 Holds - With Explicit Check Date
**Prompt:** What holds are on my paycheck for ENT:008WQ28JLWTDMQHZ19WM check date 2024-02-29?

**ENT ID Format:** `ENT:008WQ28JLWTDMQHZ19WM` (embedded in prompt - resolves cltacctnbrs)

**UI Output:**
```
Payroll Holds for Check Date 2024-02-29:

✓ Status: Released

⚠️ Active Holds (2):
  1. Tax Levy - Federal (Hold ID: HOLD-7001)
  2. Student Loan Collection (Hold ID: HOLD-7002)

ℹ️ Inactive Holds (1):
  • Child Support - State Order (HOLD-7003)

For assistance, contact HR or Payroll Services.
```

---

#### 3.2 Holds - Without Explicit Date (Current Payroll Holds)
**Prompt:** Are there any holds on my current paycheck for ENT:008WQ28JLJR1C7M97QIQ?

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt - current payroll + holds)

**UI Output:**
```
Current Paycheck Holds (Check Date: 2024-03-22):

Status: Processing (Expected Release: 2024-03-25)

⚠️ Active Hold:
  • IRS Tax Debt Collection (Hold ID: HOLD-8001)

This hold will prevent payment processing until resolved.
Contact the IRS or our Payroll Department for details.
```

---

#### 3.3 Holds - No Active Holds
**Prompt:** Do I have any holds on my paycheck for ENT:CLEAN-ACCOUNT-003 check date 2024-03-01?

**ENT ID Format:** `ENT:CLEAN-ACCOUNT-003` (embedded in prompt - clean account, no holds)

**UI Output:**
```
✓ Good news! No holds on your paycheck for 2024-03-01.
  Your payment should process without delays.
```

---

#### 3.4 Holds - Status Not Released/Processing (Ineligible for Holds)
**Prompt:** Check holds for ENT:008WQ28JLJR1C7M97QIQ check date 2024-03-05

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt - status draft, ineligible)

**UI Output:**
```
ℹ️ Holds information is not available for payroll in Draft status.
   Please check back once the status changes to Released or Processing.
```

---

### ❌ Negative Scenarios

#### 3.5 Holds - Check Date Invalid (PII Account Resolution Failed)
**Prompt:** What holds are on check date 2024-02-15 for ENT:UNMAPPED-ID-XYZ?

**ENT ID Format:** `ENT:UNMAPPED-ID-XYZ` (embedded in prompt - ENT→CA mapping fails)

**UI Output:**
```
⚠️ Unable to retrieve holds information for check date 2024-02-15.
   Your account details could not be verified.
   Please contact HR with your Employee ID.
```

---

#### 3.6 Holds - No PayPeriod ID (Cannot Look Up Holds)
**Prompt:** Tell me about holds on check date 2024-03-18 for ENT:008WQ28JLJR1C7M97QIQ

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt - status cancelled, no payperiod_id)

**UI Output:**
```
ℹ️ No holds information available for cancelled payroll (2024-03-18).
   This payment was not processed.
```

---

#### 3.7 Holds - Metadata cltacctnbrs Missing and Irresolvable
**Prompt:** Check my holds (No ENT ID provided)

**ENT ID Format:** Missing - Will fail to resolve cltacctnbrs

**UI Output:**
```
❌ Unable to retrieve holds information.
   Your account information could not be verified.
   Please log in with your full credentials and try again.
```

---

#### 3.8 Holds - API Service Error
**Prompt:** What holds do I have for ENT:008WQ28JLJR1C7M97QIQ?

**ENT ID Format:** `ENT:008WQ28JLJR1C7M97QIQ` (embedded in prompt - Holds API unavailable)

**UI Output:**
```
⚠️ Unable to fetch holds information at this time.
   Please try again later or contact support.
(Error: Holds service temporarily unavailable)
```

---

---

## 4. COMBINED/COMPLEX SCENARIOS

### Scenario 4.1: Full Status + Holds with Multiple Events
**Prompt:** Tell me complete status and holds history for ENT:008WQ28JLJR1C7M97QIQ check date 2024-03-01

**UI Output:**
```
COMPLETE PAYROLL SUMMARY for 2024-03-01
=========================================

Status Timeline:
  2024-02-28 10:00 UTC → Initial
  2024-03-01 12:30 UTC → Processing
  2024-03-01 15:45 UTC → Released ✓

Final Status: RELEASED

Previous Holds (Now Cleared):
  ✓ Background Check Review (Resolved)

Current Status: Clean - No active holds
```

---

### Scenario 4.2: Ambiguous Prompt - Requires NLU/LLM Parsing
**Prompt:** When's my next paycheck for ENT:008WQ28JLJR1C7M97QIQ?

**UI Output:**
```
Your next paycheck is scheduled for 2024-03-22.
Status: Processing
Expected release: 2024-03-25
```

---

### Scenario 4.3: Informal Inquiry - Multiple Possible Interpretations
**Prompt:** Hey, am I getting paid this week for ENT:008WQ28JLJR1C7M97QIQ?

**UI Output:**
```
✓ Yes! Your paycheck for 2024-03-15 has been released.
  No holds detected. Your payment should arrive within 1-2 business days.
```

---

### Scenario 4.4: Batch/Multi-Query (Not Yet Implemented - Future Feature)
**Prompt:** Check status for ENTs: 008WQ28JLJR1C7M97QIQ, 008WQ28JLWTDMQHZ19WM, CLEAN-ACCOUNT-003 for dates: 2024-02-01, 2024-02-15, 2024-03-01

**Note:** Batch queries not yet implemented - this is a future feature suggestion

---

---

## 5. EDGE CASES & ERROR HANDLING

### Edge Case 5.1: Weekend Date Query
**Prompt:** What's my status for ENT:008WQ28JLJR1C7M97QIQ on 2024-03-16? (Saturday)

**UI Output:**
```
ℹ️ No payroll records for 2024-03-16 (Saturday).
   Paychecks are typically issued on business days.
   Try the closest business day: 2024-03-15 (Friday).
```

---

### Edge Case 5.2: Leap Year Date (Feb 29)
**Prompt:** Tell me my payroll for ENT:008WQ28JLJR1C7M97QIQ on February 29, 2024

**Expected Response:** Check date 2024-02-29 returns released status (valid leap year date)

---

### Edge Case 5.3: Timezone Ambiguity
**Prompt:** What was my status yesterday for ENT:008WQ28JLJR1C7M97QIQ?

**UI Output:**
```
❌ Unable to determine date. Please provide a specific date (YYYY-MM-DD format).
Example: "What is my payroll status for 2024-03-14?"
```

---

### Edge Case 5.4: Very Old Historical Date (10+ years)
**Prompt:** What was my payroll for ENT:008WQ28JLJR1C7M97QIQ on 2014-03-15?

**UI Output:**
```
ℹ️ Payroll records are not available for 2014-03-15.
   Historical data beyond 7 years is archived.
   Contact HR Records for archived payroll information.
```

---

### Edge Case 5.5: Metadata with Cross-Tenant Account
**Prompt:** Check my status for ENT:ORG-002-TENANT-1/ACCT-999999 on 2024-03-15

**Expected Response:** Status retrieved across tenant boundaries

---

### Edge Case 5.6: Null/Empty Prompt
**Prompt:** (empty string or null - No ENT ID provided)

**UI Output:**
```
❌ Please provide a question or request.
Examples:
  • "What is my payroll status?"
  • "Check my status for 2024-03-15"
  • "Do I have any holds on my paycheck?"
```

---

---

## 6. TESTING MATRIX

| Scenario | Flow Type | Input | Expected Status | Expected Holds | Test Type |
|----------|-----------|-------|-----------------|-----------------|-----------|
| Basic check_date | check_date | Valid date | Released | None/Empty | Happy Path |
| Multiple events | check_date | Valid date | N/A | N/A (Events) | Happy Path |
| With holds | check_date_with_holds | Valid date | Released | Multiple | Happy Path |
| Current payroll | current_payroll | None | Released | None | Happy Path |
| Current + holds | current_payroll_with_holds | None | Processing | Active | Happy Path |
| No records found | check_date | Future/invalid | Null | Null | Negative |
| Missing check_date | check_date | None | Error | N/A | Negative |
| API timeout | check_date | Valid | Null | Null | Negative |
| Account resolve fail | holds | Valid | Null (partial) | Null | Negative |
| No payperiod_id | holds | Valid | Status | Empty list | Edge Case |
| Weekend date | check_date | Saturday | Null | Null | Edge Case |
| Ambiguous prompt | current_payroll | "When next pay?" | Latest | None | NLU Test |
| Old historical | check_date | 10yr old | Null | Null | Edge Case |

---

## 7. REAL-WORLD CONVERSATION FLOWS

### Flow A: Employee Checking Weekly Pay Status
```
User: "Is my paycheck released for this week for ENT:008WQ28JLJR1C7M97QIQ?"
Assistant Response: 
  ✓ Yes! Your paycheck for 2024-03-15 has been released.
  
User: "Great! Any holds?"
Assistant Response:
  ✓ No active holds on this check.

User: "What about the previous week?"
[Interprets as: check_date for 2024-03-08 for same ENT]
Assistant Response:
  ✓ Your paycheck for 2024-03-08: Released (No holds)
```

### Flow B: Employee with Complex Hold Situations
```
User: "Why hasn't my paycheck been released for ENT:008WQ28JLJR1C7M97QIQ?"
[Current payroll shows: Processing status]
Assistant Response:
  ℹ️ Your paycheck is still Processing.
     Expected release: 2024-03-25

User: "Is there a hold?"
Assistant Response:
  ⚠️ Yes, one active hold: "Tax Levy - Federal"
     Contact HR Payroll Department for assistance.

User: "Since when?"
[Query hold history for same ENT]
Assistant Response:
  This hold has been active since 2024-03-15.
  Please speak with our Payroll team for resolution steps.
```

### Flow C: Reconciliation Check
```
User: "Show me statuses for my recent paychecks for ENT:008WQ28JLJR1C7M97QIQ"
[Batch query - not yet impl, current system makes individual calls]
Assistant Response:
  Mar 15: Released (No holds)
  Mar 08: Released (1 hold: Tax Hold)
  Mar 01: Processing (No holds)
```

---

## 8. PROMPT PATTERNS FOR LLM PARSING & ENT ID EXTRACTION

### Patterns to Detect check_date Flow:
- "check date 2024-03-15" or "check date 2024-03-15 for ENT:xxxxx"
- "for 2024-03-15" with ENT ID
- "payroll on March 15" with ENT ID
- "status for 2024-03-15" with ENT ID
- Explicit date format (YYYY-MM-DD)

### Patterns to Detect current_payroll Flow:
- "current payroll for ENT:xxxxx"
- "latest payroll for ENT:xxxxx"
- "latest pay for ENT:xxxxx"
- "today's payroll for ENT:xxxxx"
- "my paycheck for ENT:xxxxx"
- "this week for ENT:xxxxx"
- "recent payroll for ENT:xxxxx"
- "now for ENT:xxxxx"

### Patterns to Detect holds Flow:
- "holds for ENT:xxxxx"
- "on hold for ENT:xxxxx"
- "what's holding ENT:xxxxx"
- "block for ENT:xxxxx"
- "garnishment for ENT:xxxxx"
- Combined with dates or "current"

### ENT ID Extraction Pattern:
- **Regex:** `ENT:[A-Z0-9]{20,}` (case-sensitive)
- **Examples:** 
  - `ENT:008WQ28JLJR1C7M97QIQ` ✓
  - `ENT:008WQ28JLWTDMQHZ19WM` ✓
  - `ent:008WQ28JLJR1C7M97QIQ` ✗ (must be uppercase)
- **Failure Handling:** If no ENT ID found in prompt, system should prompt user: `"Please include your Employee ID in the format ENT:xxxxx"`

---

## Usage Instructions

1. **Testing Individual Scenarios:** Copy the prompt and ENT ID format, modify with your test ENT IDs
2. **Automated Testing:** Use prompts as-is with your test/staging ENT IDs from your environment
3. **UI Testing:** Verify chatbot correctly extracts ENT ID and resolves to correct account
4. **Load Testing:** Vary ENT IDs and dates while maintaining proper ENT format
5. **Regression Testing:** Run this suite after any ENT ID parsing or account resolution changes
6. **Error Testing:** Test with invalid/missing ENT IDs to verify proper error messages

**Test ENT ID Examples:**
- Valid: `ENT:008WQ28JLJR1C7M97QIQ`, `ENT:008WQ28JLWTDMQHZ19WM`
- Invalid: `EMP-12345` (wrong prefix), `ENTXXXXX` (wrong format), `ent:xxxxx` (wrong case)

---

**Last Updated:** 2024-03-25  
**Workflow Version:** Current (with holds flow)  
**Format:** Prompts with embedded ENT ID (required), UI outputs only
