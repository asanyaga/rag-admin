# WS2 — OCR Tooling: Parking-Lot Constraints

**Status:** Parking lot (not a spec yet). Accumulates decisions/constraints surfaced
while brainstorming WS1 (the standalone explainable Probe). WS2 gets its own full
spec later; start it from here.

**Context:** WS1 = make the Probe a standalone, explainable feature (robust, legible
"needs OCR" evidence). WS2 = add actual OCR as composable custom-pipeline tool(s).
The two are decoupled because the user is the *manual* router for now — auto-routing
is a later iteration, explicitly out of scope.

---

## Constraints captured so far

### C1 — OCR execution location is configurable; do NOT assume "always local"
The OCR tool must be able to run locally **or** hand the job off to more capable
infrastructure (a remote/managed OCR service, GPU box, etc.), and this must be
**transparently configurable**. Local vs. remote execution is an implementation/config
detail behind the tool interface — callers (the pipeline, the merger) must not know or
care where OCR actually ran. Design the tool boundary so a remote backend can be
dropped in without touching pipeline or merge code.

*Implication:* engine selection (paddleocr / tesseract / easyocr) and execution
location (local / remote) are **two orthogonal axes** of configuration, not one.

### C2 — "LocalTool" naming now clashes with the remote-OCR ambition
The pipeline tool protocol is currently `LocalTool` (`tools/base.py`), a holdover from
the `local_pipeline → custom_pipeline` rename. Given C1, "Local" is misleading — an OCR
tool may execute remotely. Revisit naming during WS2 (e.g. `PipelineTool` /
`CustomPipelineTool`) so the interface name doesn't bake in a local assumption.

### C3 — Engine is user-selectable
OCR engine (paddleocr / tesseract / easyocr, and possibly others) is a configurable
choice at the custom-pipeline level, per the composable design. Each engine sits behind
the same tool interface.

---

---

## WS1 (Probe) constraints surfaced during design — move to the WS1 spec

### P1 — The probe is an evidence provider (mechanism), NOT the decision-maker (policy)
The probe observes and reports rich structured evidence — per-region signals + confidence.
It does **not** decide the parser config. A separate decision-maker/router (human today; AI
agent or ML router later) consumes the evidence and chooses. Separation of mechanism from
policy; keeps the same evidence reusable across human / agent / future model.

The **recommended parse configuration** stays but is **demoted to an advisory page/doc
summary** produced by a thin, replaceable heuristic that lives *outside* the probe core and
is clearly labeled "suggested — not authoritative." "Needs OCR" is one axis among several
(tables, font/CID health, copy-restriction, etc.). The primary deliverable is the evidence,
not the suggestion.

### P2 — Dual consumer: human UI **and** AI agent
The probe emits a structured, self-describing report object (JSON: doc summary →
recommended config + rationale → per-page → per-region findings w/ signal values +
confidence). The UI renders that object; an agent consumes the same JSON from the same
endpoint. Slice 1 has no persistence — just return the full structure per request.

### P3 — Confidence is surfaced as a number
Each signal carries a raw value + a normalized 0–1 strength; verdicts carry an aggregate
0–1 confidence with the contributing inputs visible. Honesty caveat to state in the spec:
heuristic confidence is a *calibrated score, not a probability*.

### P4 — The inspection *method* is pluggable (fitz → pdfplumber → small VLM)
NOT in scope this iteration, but design the seam now: the inspection backend is orthogonal
to the signal set and the report contract. Swapping fitz for pdfplumber or a VLM pipeline
must not touch the report shape or the UI. (Same orthogonality pattern as C1's engine vs.
location split.)

---

## Open questions for the WS2 spec (do not answer yet)

- How does the probe's per-region evidence (WS1 output) get *handed* to the OCR tool
  when the user routes manually? File + page list? Region bboxes? Just the page?
- Reconciliation: how do OCR blocks merge with an existing native text layer on `mixed`
  pages without duplicating (extends the existing `merger.py` eviction machinery)?
- Structure recovery for tables-embedded-as-images (deferred; possibly a later slice).
- Remote hand-off contract: sync vs. async, auth, payload shape, failure/timeouts.
