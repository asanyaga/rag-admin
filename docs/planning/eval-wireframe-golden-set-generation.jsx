import { useState } from "react";
import {
  Plus, Play, ArrowLeft, FileText, Search, ChevronRight,
  CheckCircle2, XCircle, BarChart3, GitCompare, Upload,
  Trash2, ChevronDown, Target, Layers, Sparkles, PenLine,
  FileUp, Check, X, Edit3, Loader2, RefreshCw, Filter
} from "lucide-react";

// ─── shadcn default light theme tokens ───
const c = {
  background: "hsl(0 0% 100%)",
  foreground: "hsl(240 10% 3.9%)",
  card: "hsl(0 0% 100%)",
  popover: "hsl(0 0% 100%)",
  primary: "hsl(240 5.9% 10%)",
  primaryForeground: "hsl(0 0% 98%)",
  secondary: "hsl(240 4.8% 95.9%)",
  secondaryForeground: "hsl(240 5.9% 10%)",
  muted: "hsl(240 4.8% 95.9%)",
  mutedForeground: "hsl(240 3.8% 46.1%)",
  accent: "hsl(240 4.8% 95.9%)",
  destructive: "hsl(0 84.2% 60.2%)",
  border: "hsl(240 5.9% 90%)",
  input: "hsl(240 5.9% 90%)",
  green: "hsl(142 71% 45%)",
  greenMuted: "hsl(142 71% 45% / 0.1)",
  red: "hsl(0 84% 60%)",
  redMuted: "hsl(0 84% 60% / 0.1)",
  amber: "hsl(38 92% 50%)",
  amberMuted: "hsl(38 92% 50% / 0.1)",
};

const radius = "0.5rem";
const radiusSm = "calc(0.5rem - 2px)";
const fontSans = 'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
const fontMono = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace';

// ─── Shared Components ───

function Button({ children, variant = "default", size = "default", onClick, disabled }) {
  const base = {
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8,
    borderRadius: radius, fontSize: 14, fontWeight: 500, fontFamily: fontSans,
    cursor: disabled ? "not-allowed" : "pointer", transition: "all 150ms",
    whiteSpace: "nowrap", opacity: disabled ? 0.5 : 1, lineHeight: 1,
  };
  const sizes = {
    default: { height: 36, padding: "0 16px" },
    sm: { height: 32, padding: "0 12px", fontSize: 13 },
    icon: { height: 36, width: 36, padding: 0 },
  };
  const variants = {
    default: { background: c.primary, color: c.primaryForeground, border: "none" },
    outline: { background: "transparent", color: c.foreground, border: `1px solid ${c.border}` },
    ghost: { background: "transparent", color: c.foreground, border: "none" },
    secondary: { background: c.secondary, color: c.secondaryForeground, border: "none" },
    destructive: { background: c.destructive, color: "#fff", border: "none" },
  };
  return (
    <button onClick={onClick} disabled={disabled}
      style={{ ...base, ...sizes[size], ...variants[variant] }}>
      {children}
    </button>
  );
}

function Card({ children, style: s, onClick }) {
  return (
    <div onClick={onClick} style={{ background: c.card, border: `1px solid ${c.border}`, borderRadius: radius, ...s }}>
      {children}
    </div>
  );
}

function Badge({ children, variant = "secondary" }) {
  const variants = {
    default: { background: c.primary, color: c.primaryForeground },
    secondary: { background: c.secondary, color: c.secondaryForeground },
    outline: { background: "transparent", color: c.foreground, border: `1px solid ${c.border}` },
    success: { background: c.greenMuted, color: c.green },
    warning: { background: c.amberMuted, color: c.amber },
    destructive: { background: c.redMuted, color: c.red },
  };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", fontSize: 12, fontWeight: 500,
      fontFamily: fontSans, padding: "2px 10px", borderRadius: "9999px", lineHeight: "20px",
      ...variants[variant],
    }}>{children}</span>
  );
}

function StatusBadge({ status }) {
  const map = {
    completed: { v: "success", l: "Completed" }, running: { v: "default", l: "Running" },
    failed: { v: "destructive", l: "Failed" }, draft: { v: "secondary", l: "Draft" },
  };
  const s = map[status] || map.draft;
  return <Badge variant={s.v}>{s.l}</Badge>;
}

function Input({ value, placeholder }) {
  return (
    <div style={{
      height: 36, padding: "0 12px", borderRadius: radiusSm, border: `1px solid ${c.input}`,
      fontSize: 14, color: value ? c.foreground : c.mutedForeground, fontFamily: fontSans,
      display: "flex", alignItems: "center",
    }}>{value || placeholder}</div>
  );
}

function Label({ children }) {
  return <label style={{ fontSize: 14, fontWeight: 500, color: c.foreground, fontFamily: fontSans, display: "block", marginBottom: 6 }}>{children}</label>;
}

function Select({ value, options, placeholder, action }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <div onClick={() => setOpen(!open)} style={{
        height: 36, padding: "0 12px", borderRadius: radiusSm, border: `1px solid ${c.input}`,
        fontSize: 14, color: c.foreground, fontFamily: fontSans,
        display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer",
      }}>
        <span>{value || <span style={{ color: c.mutedForeground }}>{placeholder}</span>}</span>
        <ChevronDown size={14} color={c.mutedForeground} />
      </div>
      {open && (
        <div style={{
          position: "absolute", top: 40, left: 0, right: 0, zIndex: 50,
          background: c.popover, border: `1px solid ${c.border}`, borderRadius: radius,
          boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)", overflow: "hidden",
        }}>
          {action && (
            <div onClick={(e) => { e.stopPropagation(); setOpen(false); action.onClick(); }}
              style={{
                padding: "8px 12px", fontSize: 14, fontFamily: fontSans, cursor: "pointer",
                display: "flex", alignItems: "center", gap: 8,
                color: c.foreground, fontWeight: 500, borderBottom: `1px solid ${c.border}`,
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = c.accent)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <Plus size={14} />{action.label}
            </div>
          )}
          {options.map((opt, i) => (
            <div key={i} onClick={() => setOpen(false)} style={{
              padding: "8px 12px", fontSize: 14, fontFamily: fontSans, cursor: "pointer",
              color: c.foreground, background: opt.value === value ? c.accent : "transparent",
            }}
              onMouseEnter={(e) => (e.currentTarget.style.background = c.accent)}
              onMouseLeave={(e) => (e.currentTarget.style.background = opt.value === value ? c.accent : "transparent")}
            >
              <div>{opt.label}</div>
              {opt.description && <div style={{ fontSize: 12, color: c.mutedForeground }}>{opt.description}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, subtitle }) {
  return (
    <Card style={{ flex: 1, minWidth: 140 }}>
      <div style={{ padding: 20 }}>
        <div style={{ fontSize: 14, color: c.mutedForeground, marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 28, fontWeight: 700, color: c.foreground, fontFamily: fontMono, letterSpacing: "-0.02em" }}>{value}</div>
        {subtitle && <div style={{ fontSize: 13, color: c.mutedForeground, marginTop: 4 }}>{subtitle}</div>}
      </div>
    </Card>
  );
}

function PageBadge({ page, hit }) {
  if (hit === undefined) {
    return <span style={{ fontSize: 12, fontFamily: fontMono, padding: "2px 8px", borderRadius: radiusSm, background: c.secondary, color: c.secondaryForeground }}>p.{page}</span>;
  }
  return (
    <span style={{ fontSize: 12, fontFamily: fontMono, padding: "2px 8px", borderRadius: radiusSm, background: hit ? c.greenMuted : c.redMuted, color: hit ? c.green : c.red }}>
      p.{page} {hit ? "✓" : "✗"}
    </span>
  );
}

function Hover({ children, style: s }) {
  return (
    <div style={{ ...s, transition: "background 150ms" }}
      onMouseEnter={(e) => (e.currentTarget.style.background = c.muted)}
      onMouseLeave={(e) => (e.currentTarget.style.background = s?.background || "transparent")}
    >{children}</div>
  );
}

// ═══════════════════════════════════════════════════════
// GOLDEN SET SCREENS
// ═══════════════════════════════════════════════════════

// ─── Golden Sets List ───
function GoldenSetsListView({ onCreateNew, onSelect }) {
  const goldenSets = [
    { id: 1, name: "Financial Queries v1", queries: 12, docs: 3, created: "Jan 15, 2025", status: "completed", method: "manual" },
    { id: 2, name: "Policy Questions", queries: 8, docs: 2, created: "Jan 20, 2025", status: "draft", method: "import" },
    { id: 3, name: "Revenue Deep Dive", queries: 24, docs: 5, created: "Feb 1, 2025", status: "completed", method: "auto" },
  ];
  const methodBadge = { manual: { l: "Manual", v: "secondary" }, import: { l: "Imported", v: "outline" }, auto: { l: "Auto-generated", v: "warning" } };

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>Golden Sets</h2>
          <p style={{ fontSize: 14, color: c.mutedForeground, margin: "4px 0 0" }}>Ground truth query-relevance pairs for evaluating retrieval quality</p>
        </div>
        <Button onClick={onCreateNew}><Plus size={14} /> New Golden Set</Button>
      </div>
      <Card>
        <div style={{ overflow: "hidden", borderRadius: radius }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 0.8fr 0.8fr 0.8fr 32px", padding: "12px 24px", borderBottom: `1px solid ${c.border}`, fontSize: 13, fontWeight: 500, color: c.mutedForeground }}>
            <div>Name</div><div>Queries</div><div>Method</div><div>Status</div><div></div>
          </div>
          {goldenSets.map((gs) => (
            <Hover key={gs.id} style={{ display: "grid", gridTemplateColumns: "2fr 0.8fr 0.8fr 0.8fr 32px", padding: "14px 24px", borderBottom: `1px solid ${c.border}`, cursor: "pointer", alignItems: "center" }}>
              <div onClick={() => onSelect(gs)}>
                <div style={{ fontWeight: 500, color: c.foreground, fontSize: 14 }}>{gs.name}</div>
                <div style={{ fontSize: 13, color: c.mutedForeground }}>{gs.docs} documents · {gs.created}</div>
              </div>
              <div style={{ fontFamily: fontMono, fontSize: 14, color: c.mutedForeground }}>{gs.queries}</div>
              <div><Badge variant={methodBadge[gs.method].v}>{methodBadge[gs.method].l}</Badge></div>
              <div><StatusBadge status={gs.status} /></div>
              <ChevronRight size={16} color={c.mutedForeground} />
            </Hover>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ─── NEW: Method Picker (Manual / Import / Auto-Generate) ───
function GoldenSetMethodPicker({ onBack, onManual, onImport, onAutoGenerate }) {
  const methods = [
    {
      id: "manual", icon: PenLine, title: "Create Manually",
      desc: "Write queries and select relevant document pages one by one. Best for small, precise golden sets.",
      detail: "You'll write each query and use the PDF viewer to mark relevant pages.",
      onClick: onManual,
    },
    {
      id: "import", icon: FileUp, title: "Import CSV / JSON",
      desc: "Upload a file with pre-existing query-relevance pairs. Best when migrating from another tool.",
      detail: "Supports CSV and JSON. You'll map columns to fields and preview before saving.",
      onClick: onImport,
    },
    {
      id: "auto", icon: Sparkles, title: "Auto-Generate with LLM",
      desc: "An LLM reads your documents and generates query-relevance pairs automatically. Best for bootstrapping.",
      detail: "Select documents, configure generation, then review and curate each generated entry.",
      onClick: onAutoGenerate,
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>New Golden Set</h2>
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: "2px 0 0" }}>Choose how you'd like to create your evaluation dataset</p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, maxWidth: 900 }}>
        {methods.map((m) => (
          <Card
            key={m.id}
            onClick={m.onClick}
            style={{ cursor: "pointer", transition: "border-color 150ms, box-shadow 150ms" }}
          >
            <div style={{ padding: 24 }}
              onMouseEnter={(e) => { e.currentTarget.parentElement.style.borderColor = c.foreground; e.currentTarget.parentElement.style.boxShadow = "0 1px 3px rgb(0 0 0 / 0.08)"; }}
              onMouseLeave={(e) => { e.currentTarget.parentElement.style.borderColor = c.border; e.currentTarget.parentElement.style.boxShadow = "none"; }}
            >
              <div style={{
                width: 40, height: 40, borderRadius: radius, background: c.secondary,
                display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16,
              }}>
                <m.icon size={20} color={c.foreground} />
              </div>
              <h3 style={{ fontSize: 16, fontWeight: 600, color: c.foreground, margin: "0 0 8px" }}>{m.title}</h3>
              <p style={{ fontSize: 14, color: c.mutedForeground, margin: "0 0 12px", lineHeight: 1.5 }}>{m.desc}</p>
              <p style={{ fontSize: 13, color: c.mutedForeground, margin: 0, lineHeight: 1.5, fontStyle: "italic" }}>{m.detail}</p>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

// ─── NEW: Import CSV/JSON Flow ───
function ImportGoldenSetView({ onBack, onConfirm }) {
  const [step, setStep] = useState("upload"); // upload | preview

  const previewRows = [
    { query: "What was revenue in 2024?", doc: "FY2025 Annual Report.pdf", pages: "45", status: "valid" },
    { query: "What is the refund policy?", doc: "Enterprise Agreement v3.pdf", pages: "12, 13", status: "valid" },
    { query: "Operating cost trends", doc: "FY2025 Annual Report.pdf", pages: "23, 45", status: "valid" },
    { query: "CEO compensation details", doc: "Compensation Report.pdf", pages: "8", status: "warning" },
    { query: "", doc: "FY2025 Annual Report.pdf", pages: "10", status: "error" },
  ];

  if (step === "upload") {
    return (
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
          <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>Import Golden Set</h2>
            <p style={{ fontSize: 13, color: c.mutedForeground, margin: "2px 0 0" }}>Upload a CSV or JSON file with query-relevance pairs</p>
          </div>
        </div>

        <div style={{ maxWidth: 600 }}>
          <Card>
            <div style={{ padding: 24 }}>
              <Label>Golden Set Name</Label>
              <Input value="" placeholder="e.g., Imported Financial Queries" />

              <div style={{ marginTop: 20 }}>
                <Label>Upload File</Label>
                <div style={{
                  border: `2px dashed ${c.border}`, borderRadius: radius, padding: "40px 24px",
                  display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
                  cursor: "pointer", transition: "border-color 150ms",
                }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = c.foreground)}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = c.border)}
                >
                  <Upload size={24} color={c.mutedForeground} />
                  <div style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>Drop your file here, or click to browse</div>
                  <div style={{ fontSize: 13, color: c.mutedForeground }}>CSV or JSON · Max 5MB</div>
                </div>
              </div>

              <div style={{ marginTop: 20, padding: 16, background: c.muted, borderRadius: radius }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: c.foreground, marginBottom: 8 }}>Expected format</div>
                <div style={{ fontSize: 12, fontFamily: fontMono, color: c.mutedForeground, lineHeight: 1.8 }}>
                  <div style={{ marginBottom: 8 }}>
                    <span style={{ color: c.foreground }}>CSV:</span> query, document, pages
                  </div>
                  <pre style={{ margin: 0, fontSize: 11, background: c.background, padding: 12, borderRadius: radiusSm, border: `1px solid ${c.border}`, overflowX: "auto" }}>
{`query,document,pages
"What was revenue in 2024?","FY2025 Annual Report.pdf","45"
"Refund policy?","Enterprise Agreement v3.pdf","12,13"`}
                  </pre>
                  <div style={{ marginTop: 12, marginBottom: 8 }}>
                    <span style={{ color: c.foreground }}>JSON:</span>
                  </div>
                  <pre style={{ margin: 0, fontSize: 11, background: c.background, padding: 12, borderRadius: radiusSm, border: `1px solid ${c.border}`, overflowX: "auto" }}>
{`[{
  "query": "What was revenue in 2024?",
  "sources": [{
    "document": "FY2025 Annual Report.pdf",
    "pages": [45]
  }]
}]`}
                  </pre>
                </div>
              </div>
            </div>
          </Card>

          <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
            <Button onClick={() => setStep("preview")}><Upload size={14} /> Upload & Preview</Button>
            <Button variant="outline" onClick={onBack}>Cancel</Button>
          </div>
        </div>
      </div>
    );
  }

  // Preview step
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={() => setStep("upload")}><ArrowLeft size={16} /></Button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>Review Import</h2>
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: "2px 0 0" }}>financial_queries.csv · 5 rows detected</p>
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <Card style={{ flex: 1, padding: "12px 16px", display: "flex", alignItems: "center", gap: 8 }}>
          <CheckCircle2 size={16} color={c.green} />
          <span style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>3 valid</span>
        </Card>
        <Card style={{ flex: 1, padding: "12px 16px", display: "flex", alignItems: "center", gap: 8 }}>
          <AlertCircle size={16} color={c.amber} />
          <span style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>1 warning</span>
          <span style={{ fontSize: 13, color: c.mutedForeground }}>— document not found in project</span>
        </Card>
        <Card style={{ flex: 1, padding: "12px 16px", display: "flex", alignItems: "center", gap: 8 }}>
          <XCircle size={16} color={c.red} />
          <span style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>1 error</span>
          <span style={{ fontSize: 13, color: c.mutedForeground }}>— missing query</span>
        </Card>
      </div>

      <Card>
        <div style={{ overflow: "hidden", borderRadius: radius }}>
          <div style={{ display: "grid", gridTemplateColumns: "32px 2fr 1.5fr 0.8fr 0.5fr", padding: "12px 24px", borderBottom: `1px solid ${c.border}`, fontSize: 13, fontWeight: 500, color: c.mutedForeground }}>
            <div></div><div>Query</div><div>Document</div><div>Pages</div><div>Status</div>
          </div>
          {previewRows.map((row, i) => {
            const statusMap = {
              valid: { icon: CheckCircle2, color: c.green, bg: "transparent" },
              warning: { icon: AlertCircle, color: c.amber, bg: c.amberMuted },
              error: { icon: XCircle, color: c.red, bg: c.redMuted },
            };
            const st = statusMap[row.status];
            return (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "32px 2fr 1.5fr 0.8fr 0.5fr",
                padding: "12px 24px", borderBottom: `1px solid ${c.border}`, alignItems: "center",
                background: st.bg, fontSize: 14,
              }}>
                <input type="checkbox" defaultChecked={row.status !== "error"} style={{ width: 16, height: 16, accentColor: c.foreground }} />
                <div style={{ color: row.query ? c.foreground : c.red, fontStyle: row.query ? "normal" : "italic" }}>
                  {row.query || "Empty query"}
                </div>
                <div style={{ color: c.mutedForeground, fontSize: 13 }}>{row.doc}</div>
                <div style={{ fontFamily: fontMono, fontSize: 13, color: c.mutedForeground }}>{row.pages}</div>
                <st.icon size={16} color={st.color} />
              </div>
            );
          })}
        </div>
      </Card>

      <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
        <Button onClick={onConfirm}><Check size={14} /> Import 4 entries</Button>
        <Button variant="outline" onClick={() => setStep("upload")}>Back</Button>
      </div>
    </div>
  );
}

// ─── NEW: Auto-Generate Config ───
function AutoGenerateConfigView({ onBack, onGenerate }) {
  const [selectedDocs, setSelectedDocs] = useState(["FY2025 Annual Report.pdf", "Enterprise Agreement v3.pdf"]);
  const allDocs = [
    { name: "FY2025 Annual Report.pdf", pages: 86 },
    { name: "Enterprise Agreement v3.pdf", pages: 24 },
    { name: "Q4 Board Deck.pdf", pages: 15 },
    { name: "Compensation Report.pdf", pages: 42 },
  ];

  const toggleDoc = (name) => {
    setSelectedDocs((prev) => prev.includes(name) ? prev.filter((d) => d !== name) : [...prev, name]);
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>Auto-Generate Golden Set</h2>
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: "2px 0 0" }}>An LLM will read your documents and generate query-relevance pairs</p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, maxWidth: 800 }}>
        {/* Name */}
        <Card>
          <div style={{ padding: 20 }}>
            <Label>Golden Set Name</Label>
            <Input value="" placeholder="e.g., Auto-gen Financial v1" />
          </div>
        </Card>

        {/* LLM Provider */}
        <Card>
          <div style={{ padding: 20 }}>
            <Label>LLM Provider</Label>
            <Select
              value="Anthropic — Claude Sonnet 4"
              options={[
                { value: "Anthropic — Claude Sonnet 4", label: "Anthropic — Claude Sonnet 4" },
                { value: "OpenAI — GPT-4o", label: "OpenAI — GPT-4o" },
                { value: "Ollama — llama3", label: "Ollama — llama3 (local)" },
              ]}
            />
            <p style={{ fontSize: 13, color: c.mutedForeground, margin: "8px 0 0" }}>Uses your configured API key</p>
          </div>
        </Card>

        {/* Documents */}
        <Card style={{ gridColumn: "1 / -1" }}>
          <div style={{ padding: "14px 20px", borderBottom: `1px solid ${c.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <span style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>Select Documents</span>
              <span style={{ fontSize: 13, color: c.mutedForeground, marginLeft: 8 }}>{selectedDocs.length} of {allDocs.length} selected</span>
            </div>
          </div>
          {allDocs.map((doc) => {
            const selected = selectedDocs.includes(doc.name);
            return (
              <Hover key={doc.name} style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "12px 20px", borderBottom: `1px solid ${c.border}`, cursor: "pointer",
              }}>
                <input type="checkbox" checked={selected} onChange={() => toggleDoc(doc.name)}
                  style={{ width: 16, height: 16, accentColor: c.foreground }} />
                <FileText size={16} color={c.mutedForeground} />
                <div style={{ flex: 1 }} onClick={() => toggleDoc(doc.name)}>
                  <div style={{ fontSize: 14, fontWeight: selected ? 500 : 400, color: c.foreground }}>{doc.name}</div>
                  <div style={{ fontSize: 12, color: c.mutedForeground }}>{doc.pages} pages</div>
                </div>
              </Hover>
            );
          })}
        </Card>

        {/* Generation Config */}
        <Card>
          <div style={{ padding: 20 }}>
            <Label>Queries per Document</Label>
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              {[3, 5, 10, 15].map((n) => (
                <button key={n} style={{
                  flex: 1, padding: "8px 0", borderRadius: radiusSm, fontSize: 14, fontFamily: fontMono,
                  border: `1px solid ${n === 5 ? c.foreground : c.border}`, cursor: "pointer",
                  background: n === 5 ? c.foreground : "transparent",
                  color: n === 5 ? c.primaryForeground : c.foreground,
                  fontWeight: n === 5 ? 600 : 400,
                }}>{n}</button>
              ))}
            </div>
            <p style={{ fontSize: 13, color: c.mutedForeground, margin: "8px 0 0" }}>
              Estimated: ~{selectedDocs.length * 5} queries total
            </p>
          </div>
        </Card>

        {/* Question Types */}
        <Card>
          <div style={{ padding: 20 }}>
            <Label>Question Types</Label>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
              {[
                { label: "Factual lookup", desc: "Direct answers found on specific pages", checked: true },
                { label: "Comparison / reasoning", desc: "Require synthesizing across pages", checked: true },
                { label: "Summarization", desc: "Broad questions about document themes", checked: false },
              ].map((qt) => (
                <label key={qt.label} style={{
                  display: "flex", alignItems: "flex-start", gap: 10, padding: "8px 10px",
                  borderRadius: radiusSm, border: `1px solid ${c.border}`, cursor: "pointer",
                }}>
                  <input type="checkbox" defaultChecked={qt.checked} style={{ marginTop: 2, width: 16, height: 16, accentColor: c.foreground }} />
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>{qt.label}</div>
                    <div style={{ fontSize: 12, color: c.mutedForeground }}>{qt.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
        </Card>
      </div>

      <div style={{ marginTop: 24, display: "flex", gap: 8 }}>
        <Button onClick={onGenerate}><Sparkles size={14} /> Generate Queries</Button>
        <Button variant="outline" onClick={onBack}>Cancel</Button>
      </div>
    </div>
  );
}

// ─── NEW: Review Auto-Generated Entries ───
function ReviewGeneratedView({ onBack, onSave }) {
  const [entries, setEntries] = useState([
    { id: 1, query: "What was the total revenue for fiscal year 2024?", doc: "FY2025 Annual Report.pdf", pages: [45], type: "factual", status: "accepted" },
    { id: 2, query: "How did operating expenses in 2025 compare to 2024?", doc: "FY2025 Annual Report.pdf", pages: [23, 45], type: "comparison", status: "accepted" },
    { id: 3, query: "What is the company's debt-to-equity ratio?", doc: "FY2025 Annual Report.pdf", pages: [52], type: "factual", status: "pending" },
    { id: 4, query: "What are the key risk factors mentioned in the report?", doc: "FY2025 Annual Report.pdf", pages: [71, 72, 73], type: "summarization", status: "rejected" },
    { id: 5, query: "What is the termination clause for enterprise contracts?", doc: "Enterprise Agreement v3.pdf", pages: [8, 9], type: "factual", status: "pending" },
    { id: 6, query: "How does the refund policy differ by payment method?", doc: "Enterprise Agreement v3.pdf", pages: [12, 13], type: "comparison", status: "pending" },
    { id: 7, query: "What SLA guarantees are provided for uptime?", doc: "Enterprise Agreement v3.pdf", pages: [14], type: "factual", status: "accepted" },
    { id: 8, query: "Summarize the key obligations of the client.", doc: "Enterprise Agreement v3.pdf", pages: [3, 4, 5], type: "summarization", status: "pending" },
  ]);

  const [filterStatus, setFilterStatus] = useState("all");
  const [editingId, setEditingId] = useState(null);

  const updateStatus = (id, status) => {
    setEntries((prev) => prev.map((e) => e.id === id ? { ...e, status } : e));
  };

  const counts = {
    all: entries.length,
    accepted: entries.filter((e) => e.status === "accepted").length,
    pending: entries.filter((e) => e.status === "pending").length,
    rejected: entries.filter((e) => e.status === "rejected").length,
  };

  const filtered = filterStatus === "all" ? entries : entries.filter((e) => e.status === filterStatus);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>Review Generated Entries</h2>
            <Badge variant="warning">Auto-generated</Badge>
          </div>
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: "2px 0 0" }}>
            Review each entry before saving. Accept, edit, or reject queries that don't meet quality standards.
          </p>
        </div>
        <Button variant="outline" onClick={() => {
          setEntries((prev) => prev.map((e) => e.status === "pending" ? { ...e, status: "accepted" } : e));
        }}><Check size={14} /> Accept All Pending</Button>
      </div>

      {/* Summary cards */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        {[
          { key: "all", label: "Total", count: counts.all, color: c.foreground },
          { key: "accepted", label: "Accepted", count: counts.accepted, color: c.green },
          { key: "pending", label: "Pending Review", count: counts.pending, color: c.amber },
          { key: "rejected", label: "Rejected", count: counts.rejected, color: c.red },
        ].map((f) => (
          <Card
            key={f.key}
            onClick={() => setFilterStatus(f.key)}
            style={{
              flex: 1, padding: "12px 16px", cursor: "pointer",
              borderColor: filterStatus === f.key ? c.foreground : c.border,
              transition: "border-color 150ms",
            }}
          >
            <div style={{ fontSize: 13, color: c.mutedForeground, marginBottom: 2 }}>{f.label}</div>
            <div style={{ fontSize: 24, fontWeight: 700, fontFamily: fontMono, color: f.color }}>{f.count}</div>
          </Card>
        ))}
      </div>

      {/* Entry list */}
      <Card>
        <div style={{ overflow: "hidden", borderRadius: radius }}>
          {filtered.map((entry) => {
            const statusColors = { accepted: c.greenMuted, pending: "transparent", rejected: c.redMuted };
            const isEditing = editingId === entry.id;

            return (
              <div key={entry.id} style={{
                padding: "16px 24px", borderBottom: `1px solid ${c.border}`,
                background: statusColors[entry.status],
              }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
                  {/* Status indicator */}
                  <div style={{ paddingTop: 2 }}>
                    {entry.status === "accepted" && <CheckCircle2 size={18} color={c.green} />}
                    {entry.status === "pending" && <AlertCircle size={18} color={c.amber} />}
                    {entry.status === "rejected" && <XCircle size={18} color={c.red} />}
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      {isEditing ? (
                        <div style={{
                          flex: 1, padding: "6px 10px", borderRadius: radiusSm,
                          border: `1px solid ${c.foreground}`, fontSize: 14, color: c.foreground,
                          background: c.background,
                        }}>
                          {entry.query}
                        </div>
                      ) : (
                        <span style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>{entry.query}</span>
                      )}
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <FileText size={12} color={c.mutedForeground} />
                        <span style={{ fontSize: 13, color: c.mutedForeground }}>{entry.doc}</span>
                      </div>
                      <div style={{ display: "flex", gap: 4 }}>
                        {entry.pages.map((p) => <PageBadge key={p} page={p} />)}
                      </div>
                      <Badge variant="outline">{entry.type}</Badge>
                    </div>
                  </div>

                  {/* Actions */}
                  <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                    {isEditing ? (
                      <>
                        <Button variant="outline" size="sm" onClick={() => setEditingId(null)}><Check size={13} /> Done</Button>
                      </>
                    ) : (
                      <>
                        {entry.status !== "accepted" && (
                          <Button variant="ghost" size="icon" onClick={() => updateStatus(entry.id, "accepted")}>
                            <Check size={16} color={c.green} />
                          </Button>
                        )}
                        <Button variant="ghost" size="icon" onClick={() => setEditingId(entry.id)}>
                          <Edit3 size={14} />
                        </Button>
                        {entry.status !== "rejected" && (
                          <Button variant="ghost" size="icon" onClick={() => updateStatus(entry.id, "rejected")}>
                            <X size={16} color={c.red} />
                          </Button>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <div style={{ marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 13, color: c.mutedForeground }}>
          {counts.accepted} entries will be saved · {counts.rejected} rejected · {counts.pending} still pending review
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button variant="outline" onClick={onBack}>Discard All</Button>
          <Button onClick={onSave} disabled={counts.pending > 0}>
            <Check size={14} /> Save {counts.accepted} Entries
          </Button>
        </div>
      </div>

      {counts.pending > 0 && (
        <div style={{
          marginTop: 8, padding: "10px 16px", borderRadius: radius,
          background: c.amberMuted, border: `1px solid hsl(38 92% 50% / 0.2)`,
          fontSize: 13, color: c.amber,
        }}>
          Review all pending entries before saving. Accept or reject each one.
        </div>
      )}
    </div>
  );
}

// ─── Golden Set Editor (updated with Add Entries dropdown) ───
function GoldenSetEditorView({ onBack, onAddImport, onAddAutoGenerate }) {
  const [selectedQuery, setSelectedQuery] = useState(0);
  const [showAddMenu, setShowAddMenu] = useState(false);

  const queries = [
    { query: "What was revenue in 2024?", sources: [{ doc: "FY2025 Annual Report.pdf", pages: [45] }], method: "manual" },
    { query: "What is the refund policy for enterprise clients?", sources: [{ doc: "Enterprise Agreement v3.pdf", pages: [12, 13] }], method: "auto" },
    { query: "How did operating costs change year-over-year?", sources: [{ doc: "FY2025 Annual Report.pdf", pages: [23, 45] }, { doc: "Q4 Board Deck.pdf", pages: [8] }], method: "manual" },
  ];
  const q = queries[selectedQuery];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>Financial Queries v1</h2>
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: 0 }}>12 queries · 3 documents · Created Jan 15</p>
        </div>
        {/* Add Entries dropdown */}
        <div style={{ position: "relative" }}>
          <Button onClick={() => setShowAddMenu(!showAddMenu)}>
            <Plus size={14} /> Add Entries <ChevronDown size={12} />
          </Button>
          {showAddMenu && (
            <div style={{
              position: "absolute", top: 42, right: 0, width: 220, zIndex: 50,
              background: c.popover, border: `1px solid ${c.border}`, borderRadius: radius,
              boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)", overflow: "hidden",
            }}>
              {[
                { icon: PenLine, label: "Add Manually", onClick: () => setShowAddMenu(false) },
                { icon: FileUp, label: "Import CSV / JSON", onClick: () => { setShowAddMenu(false); onAddImport(); } },
                { icon: Sparkles, label: "Auto-Generate", onClick: () => { setShowAddMenu(false); onAddAutoGenerate(); } },
              ].map((item) => (
                <div key={item.label} onClick={item.onClick} style={{
                  padding: "10px 14px", fontSize: 14, display: "flex", alignItems: "center", gap: 10,
                  cursor: "pointer", color: c.foreground, borderBottom: `1px solid ${c.border}`,
                }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = c.accent)}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <item.icon size={15} color={c.mutedForeground} />
                  {item.label}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 16 }}>
        <Card>
          <div style={{ padding: "12px 16px", borderBottom: `1px solid ${c.border}` }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: c.mutedForeground }}>Queries</span>
          </div>
          {queries.map((q, i) => (
            <div key={i} onClick={() => setSelectedQuery(i)} style={{
              padding: "12px 16px", borderBottom: `1px solid ${c.border}`, cursor: "pointer",
              background: selectedQuery === i ? c.muted : "transparent",
              borderLeft: selectedQuery === i ? `2px solid ${c.foreground}` : "2px solid transparent",
            }}
              onMouseEnter={(e) => selectedQuery !== i && (e.currentTarget.style.background = c.muted)}
              onMouseLeave={(e) => selectedQuery !== i && (e.currentTarget.style.background = "transparent")}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 14, color: c.foreground, fontWeight: selectedQuery === i ? 500 : 400 }}>{q.query}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
                <span style={{ fontSize: 12, color: c.mutedForeground }}>
                  {q.sources.length} doc{q.sources.length > 1 ? "s" : ""} · {q.sources.reduce((a, s) => a + s.pages.length, 0)} pages
                </span>
                {q.method === "auto" && <Badge variant="warning" style={{ fontSize: 10 }}>auto</Badge>}
              </div>
            </div>
          ))}
        </Card>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card><div style={{ padding: 20 }}><Label>Query</Label><Input value={q.query} /></div></Card>
          <Card>
            <div style={{ padding: "14px 20px", borderBottom: `1px solid ${c.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>Relevant Sources</span>
              <Button variant="outline" size="sm"><Plus size={14} /> Add Source</Button>
            </div>
            {q.sources.map((src, i) => (
              <div key={i} style={{ padding: "14px 20px", borderBottom: `1px solid ${c.border}`, display: "flex", alignItems: "center", gap: 12 }}>
                <FileText size={16} color={c.mutedForeground} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>{src.doc}</div>
                  <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                    {src.pages.map((p) => <PageBadge key={p} page={p} />)}
                  </div>
                </div>
                <Button variant="ghost" size="icon"><Trash2 size={14} /></Button>
              </div>
            ))}
          </Card>
          <Card style={{ minHeight: 220 }}>
            <div style={{ height: 220, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8 }}>
              <FileText size={32} strokeWidth={1} color={c.mutedForeground} />
              <div style={{ fontSize: 14, color: c.mutedForeground, fontWeight: 500 }}>PDF Viewer</div>
              <p style={{ fontSize: 13, color: c.mutedForeground, textAlign: "center", maxWidth: 300, margin: 0 }}>
                Click a document above to preview. Click pages to toggle relevance.
              </p>
              <Badge variant="outline">Reuses existing react-pdf viewer</Badge>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// EVALUATION RUN SCREENS (unchanged from previous)
// ═══════════════════════════════════════════════════════

function EvalRunsListView({ onNewRun, onSelectRun, onCompare }) {
  const runs = [
    { id: "run_001", name: "Run #1", index: "FY2025 — 512 tokens", config: "hybrid · k=5 · rrf=0.6", status: "completed", precision: 0.72, recall: 0.83, f1: 0.77, date: "Feb 5, 14:32" },
    { id: "run_002", name: "Run #2", index: "FY2025 — 256 tokens", config: "hybrid · k=5 · rrf=0.6", status: "completed", precision: 0.65, recall: 0.91, f1: 0.76, date: "Feb 5, 15:10" },
    { id: "run_003", name: "Run #3", index: "FY2025 — 512 tokens", config: "vector · k=10", status: "completed", precision: 0.58, recall: 0.67, f1: 0.62, date: "Feb 6, 09:45" },
    { id: "run_004", name: "Run #4", index: "FY2025 — 512 tokens", config: "hybrid · k=5 · rrf=0.8", status: "running", precision: null, recall: null, f1: null, date: "Feb 9, 11:20" },
  ];
  const [selected, setSelected] = useState([]);
  const toggleSelect = (id) => setSelected((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : prev.length < 2 ? [...prev, id] : prev);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>Evaluation Runs</h2>
          <p style={{ fontSize: 14, color: c.mutedForeground, margin: "4px 0 0" }}>Compare retrieval performance across indexes and configurations</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {selected.length === 2 && <Button variant="outline" onClick={onCompare}><GitCompare size={14} /> Compare</Button>}
          <Button onClick={onNewRun}><Play size={14} /> New Run</Button>
        </div>
      </div>
      {selected.length === 1 && (
        <div style={{ background: c.muted, borderRadius: radius, padding: "10px 16px", fontSize: 13, color: c.mutedForeground, marginBottom: 12, border: `1px solid ${c.border}` }}>
          Select one more run to compare
        </div>
      )}
      <Card>
        <div style={{ overflow: "hidden", borderRadius: radius }}>
          <div style={{ display: "grid", gridTemplateColumns: "36px 1.5fr 1.2fr 1.5fr 0.6fr 0.6fr 0.6fr auto", padding: "12px 24px", borderBottom: `1px solid ${c.border}`, fontSize: 13, fontWeight: 500, color: c.mutedForeground }}>
            <div></div><div>Run</div><div>Index</div><div>Config</div><div>P@k</div><div>R@k</div><div>F1</div><div>Status</div>
          </div>
          {runs.map((run) => (
            <Hover key={run.id} style={{
              display: "grid", gridTemplateColumns: "36px 1.5fr 1.2fr 1.5fr 0.6fr 0.6fr 0.6fr auto",
              padding: "12px 24px", borderBottom: `1px solid ${c.border}`, alignItems: "center",
              background: selected.includes(run.id) ? c.muted : "transparent",
            }}>
              <div><input type="checkbox" checked={selected.includes(run.id)} onChange={() => toggleSelect(run.id)} disabled={run.status !== "completed"} style={{ width: 16, height: 16, accentColor: c.foreground }} /></div>
              <div onClick={() => onSelectRun(run)} style={{ cursor: "pointer" }}>
                <div style={{ fontWeight: 500, color: c.foreground, fontSize: 14 }}>{run.name}</div>
                <div style={{ fontSize: 13, color: c.mutedForeground }}>{run.date}</div>
              </div>
              <div style={{ fontSize: 14, color: c.mutedForeground }}>{run.index}</div>
              <div style={{ fontFamily: fontMono, fontSize: 13, color: c.mutedForeground }}>{run.config}</div>
              <div style={{ fontFamily: fontMono, fontSize: 14, fontWeight: 600, color: run.precision ? c.foreground : c.mutedForeground }}>{run.precision?.toFixed(2) ?? "—"}</div>
              <div style={{ fontFamily: fontMono, fontSize: 14, fontWeight: 600, color: run.recall ? c.foreground : c.mutedForeground }}>{run.recall?.toFixed(2) ?? "—"}</div>
              <div style={{ fontFamily: fontMono, fontSize: 14, fontWeight: 600, color: run.f1 ? c.foreground : c.mutedForeground }}>{run.f1?.toFixed(2) ?? "—"}</div>
              <div><StatusBadge status={run.status} /></div>
            </Hover>
          ))}
        </div>
      </Card>
    </div>
  );
}

function NewRunConfigView({ onBack, onExecute, onCreateGoldenSet }) {
  const [searchMode, setSearchMode] = useState("Hybrid");
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>Configure Evaluation Run</h2>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, maxWidth: 800 }}>
        <Card><div style={{ padding: 20 }}>
          <Label>Golden Set</Label>
          <Select value="Financial Queries v1" placeholder="Select a golden set..."
            action={{ label: "Create New Golden Set", onClick: onCreateGoldenSet }}
            options={[
              { value: "Financial Queries v1", label: "Financial Queries v1", description: "12 queries · 3 documents" },
              { value: "Policy Questions", label: "Policy Questions", description: "8 queries · 2 documents" },
            ]} />
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: "8px 0 0" }}>12 queries · 3 documents</p>
        </div></Card>
        <Card><div style={{ padding: 20 }}>
          <Label>Index</Label>
          <Select value="FY2025 — 512 tokens" options={[
            { value: "FY2025 — 512 tokens", label: "FY2025 — 512 tokens", description: "text-embedding-3-small · hybrid" },
            { value: "FY2025 — 256 tokens", label: "FY2025 — 256 tokens", description: "text-embedding-3-small · hybrid" },
          ]} />
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: "8px 0 0" }}>text-embedding-3-small · hybrid</p>
        </div></Card>
        <Card><div style={{ padding: 20 }}>
          <Label>Retrieval Configuration</Label>
          <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 4 }}>
            <div>
              <div style={{ fontSize: 13, color: c.mutedForeground, marginBottom: 8 }}>Search Mode</div>
              <div style={{ display: "flex", gap: 4, background: c.muted, borderRadius: radius, padding: 4 }}>
                {["Vector", "BM25", "Hybrid"].map((mode) => (
                  <button key={mode} onClick={() => setSearchMode(mode)} style={{
                    flex: 1, padding: "6px 12px", borderRadius: radiusSm, fontSize: 13, fontWeight: 500,
                    fontFamily: fontSans, cursor: "pointer", border: "none", transition: "all 150ms",
                    background: searchMode === mode ? c.background : "transparent",
                    color: searchMode === mode ? c.foreground : c.mutedForeground,
                    boxShadow: searchMode === mode ? "0 1px 2px rgb(0 0 0 / 0.05)" : "none",
                  }}>{mode}</button>
                ))}
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div><div style={{ fontSize: 13, color: c.mutedForeground, marginBottom: 6 }}>Top K</div><Input value="5" /></div>
              <div><div style={{ fontSize: 13, color: c.mutedForeground, marginBottom: 6 }}>RRF Weight</div><Input value="0.6" /></div>
            </div>
          </div>
        </div></Card>
        <Card><div style={{ padding: 20 }}>
          <Label>Run Name <span style={{ fontWeight: 400, color: c.mutedForeground }}>(optional)</span></Label>
          <Input placeholder="Auto: Run #5 — hybrid · k=5 · rrf=0.6" />
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: "8px 0 0" }}>A descriptive name helps when comparing runs later</p>
        </div></Card>
      </div>
      <div style={{ marginTop: 24, display: "flex", gap: 8 }}>
        <Button onClick={onExecute}><Play size={14} /> Run Evaluation</Button>
        <Button variant="outline" onClick={onBack}>Cancel</Button>
      </div>
    </div>
  );
}

function RunResultsView({ onBack }) {
  const [expandedQuery, setExpandedQuery] = useState(0);
  const queryResults = [
    { query: "What was revenue in 2024?", precision: 0.60, recall: 1.0, f1: 0.75,
      retrieved: [
        { rank: 1, doc: "FY2025 Annual Report.pdf", page: 12, relevant: false, snippet: "Our revenue 2025 performance (USD 4.2B) exceeded 2024 targets..." },
        { rank: 2, doc: "FY2025 Annual Report.pdf", page: 2, relevant: false, snippet: "This annual report covers fiscal year ending December 2025..." },
        { rank: 3, doc: "FY2025 Annual Report.pdf", page: 45, relevant: true, snippet: "Revenue comparison: 2023: $3.1B, 2024: $3.8B, 2025: $4.2B..." },
        { rank: 4, doc: "Q4 Board Deck.pdf", page: 8, relevant: false, snippet: "Q4 revenue targets were met across all business units..." },
        { rank: 5, doc: "FY2025 Annual Report.pdf", page: 46, relevant: false, snippet: "Revenue by segment: Enterprise $2.1B, SMB $1.2B..." },
      ], expected: [{ doc: "FY2025 Annual Report.pdf", pages: [45] }] },
    { query: "Refund policy for enterprise?", precision: 0.80, recall: 1.0, f1: 0.89,
      retrieved: [
        { rank: 1, doc: "Enterprise Agreement v3.pdf", page: 12, relevant: true, snippet: "Section 4.2: Refund Policy. Enterprise clients are entitled to..." },
        { rank: 2, doc: "Enterprise Agreement v3.pdf", page: 13, relevant: true, snippet: "...pro-rated refunds within 30 days of service termination..." },
        { rank: 3, doc: "FY2025 Annual Report.pdf", page: 78, relevant: false, snippet: "Customer retention metrics improved with revised refund..." },
      ], expected: [{ doc: "Enterprise Agreement v3.pdf", pages: [12, 13] }] },
    { query: "Operating costs YoY?", precision: 0.40, recall: 0.50, f1: 0.44,
      retrieved: [
        { rank: 1, doc: "FY2025 Annual Report.pdf", page: 67, relevant: false, snippet: "Total operating expenses for FY2025 were $2.8B..." },
        { rank: 2, doc: "FY2025 Annual Report.pdf", page: 23, relevant: true, snippet: "Year-over-year operating cost analysis shows 8.2% increase..." },
        { rank: 3, doc: "Q4 Board Deck.pdf", page: 3, relevant: false, snippet: "Operating efficiency metrics dashboard..." },
      ], expected: [{ doc: "FY2025 Annual Report.pdf", pages: [23, 45] }, { doc: "Q4 Board Deck.pdf", pages: [8] }] },
  ];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>Run #1</h2>
            <StatusBadge status="completed" />
          </div>
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: "2px 0 0" }}>Financial Queries v1 · FY2025 — 512 tokens · hybrid · k=5 · rrf=0.6</p>
        </div>
      </div>
      <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
        <MetricCard label="Precision@5" value="0.72" subtitle="Avg across 12 queries" />
        <MetricCard label="Recall@5" value="0.83" subtitle="Avg across 12 queries" />
        <MetricCard label="F1@5" value="0.77" subtitle="Harmonic mean" />
      </div>
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, color: c.foreground, margin: 0 }}>Per-Query Results</h3>
      </div>
      <Card>
        {queryResults.map((qr, i) => (
          <div key={i}>
            <Hover style={{ display: "grid", gridTemplateColumns: "2fr 0.5fr 0.5fr 0.5fr 28px", padding: "14px 24px", borderBottom: `1px solid ${c.border}`, cursor: "pointer", alignItems: "center", background: expandedQuery === i ? c.muted : "transparent" }}>
              <div onClick={() => setExpandedQuery(expandedQuery === i ? -1 : i)} style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>{qr.query}</div>
              <div style={{ fontFamily: fontMono, fontSize: 13, color: c.mutedForeground }}>P: {qr.precision.toFixed(2)}</div>
              <div style={{ fontFamily: fontMono, fontSize: 13, color: c.mutedForeground }}>R: {qr.recall.toFixed(2)}</div>
              <div style={{ fontFamily: fontMono, fontSize: 13, fontWeight: 600, color: qr.f1 >= 0.7 ? c.green : qr.f1 >= 0.5 ? c.amber : c.red }}>F1: {qr.f1.toFixed(2)}</div>
              <ChevronDown size={14} color={c.mutedForeground} onClick={() => setExpandedQuery(expandedQuery === i ? -1 : i)} style={{ transform: expandedQuery === i ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 200ms", cursor: "pointer" }} />
            </Hover>
            {expandedQuery === i && (
              <div style={{ padding: 24, borderBottom: `1px solid ${c.border}`, background: c.muted }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
                  <div>
                    <h4 style={{ fontSize: 13, fontWeight: 600, color: c.mutedForeground, margin: "0 0 12px", textTransform: "uppercase", letterSpacing: "0.05em" }}>Retrieved</h4>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {qr.retrieved.map((ch, j) => (
                        <div key={j} style={{ display: "flex", gap: 10, padding: "10px 12px", borderRadius: radiusSm, background: ch.relevant ? c.greenMuted : c.background, border: `1px solid ${ch.relevant ? "hsl(142 71% 45% / 0.3)" : c.border}` }}>
                          <div style={{ width: 24, height: 24, borderRadius: radiusSm, display: "flex", alignItems: "center", justifyContent: "center", background: c.secondary, fontSize: 12, fontFamily: fontMono, color: c.mutedForeground, flexShrink: 0 }}>{ch.rank}</div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                              <span style={{ fontSize: 13, fontWeight: 500, color: c.foreground }}>{ch.doc}</span>
                              <PageBadge page={ch.page} />
                              {ch.relevant ? <CheckCircle2 size={13} color={c.green} /> : <XCircle size={13} color={c.mutedForeground} />}
                            </div>
                            <div style={{ fontSize: 13, color: c.mutedForeground, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ch.snippet}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h4 style={{ fontSize: 13, fontWeight: 600, color: c.mutedForeground, margin: "0 0 12px", textTransform: "uppercase", letterSpacing: "0.05em" }}>Expected</h4>
                    {qr.expected.map((exp, j) => (
                      <div key={j} style={{ padding: "10px 12px", borderRadius: radiusSm, background: c.background, border: `1px solid ${c.border}`, marginBottom: 8 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                          <FileText size={14} color={c.mutedForeground} />
                          <span style={{ fontSize: 13, fontWeight: 500, color: c.foreground }}>{exp.doc}</span>
                        </div>
                        <div style={{ display: "flex", gap: 6 }}>
                          {exp.pages.map((p) => {
                            const found = qr.retrieved.some((r) => r.doc === exp.doc && r.page === p && r.relevant);
                            return <PageBadge key={p} page={p} hit={found} />;
                          })}
                        </div>
                      </div>
                    ))}
                    <Card style={{ marginTop: 12 }}>
                      <div style={{ padding: "12px 14px" }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: c.mutedForeground, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>Observation</div>
                        <div style={{ fontSize: 13, color: c.mutedForeground, lineHeight: 1.6 }}>
                          {qr.f1 >= 0.7 ? "Good retrieval — relevant sources found in top results." : `Relevant page appeared at rank ${qr.retrieved.findIndex((r) => r.relevant) + 1}. Semantic similarity may be ranking non-ideal chunks higher.`}
                        </div>
                      </div>
                    </Card>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </Card>
    </div>
  );
}

function RunComparisonView({ onBack }) {
  const runs = [
    { name: "Run #1", index: "512 tokens", config: "hybrid · k=5 · rrf=0.6", precision: 0.72, recall: 0.83, f1: 0.77 },
    { name: "Run #2", index: "256 tokens", config: "hybrid · k=5 · rrf=0.6", precision: 0.65, recall: 0.91, f1: 0.76 },
  ];
  const qc = [
    { query: "Revenue in 2024?", run1: { p: 0.60, r: 1.0, f1: 0.75 }, run2: { p: 0.40, r: 1.0, f1: 0.57 } },
    { query: "Refund policy?", run1: { p: 0.80, r: 1.0, f1: 0.89 }, run2: { p: 0.80, r: 1.0, f1: 0.89 } },
    { query: "Operating costs?", run1: { p: 0.40, r: 0.50, f1: 0.44 }, run2: { p: 0.60, r: 0.75, f1: 0.67 } },
  ];
  const delta = (a, b) => { const d = b - a; if (Math.abs(d) < 0.005) return <span style={{ color: c.mutedForeground }}>—</span>; return <span style={{ fontFamily: fontMono, fontSize: 13, fontWeight: 600, color: d > 0 ? c.green : c.red }}>{d > 0 ? "+" : ""}{d.toFixed(2)}</span>; };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: c.foreground, margin: 0 }}>Compare Runs</h2>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        {runs.map((run, i) => (
          <Card key={i}><div style={{ padding: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 600, color: c.foreground }}>{run.name}</div>
                <div style={{ fontSize: 13, color: c.mutedForeground }}>{run.index} · {run.config}</div>
              </div>
              <Badge variant={i === 0 ? "secondary" : "outline"}>{i === 0 ? "Baseline" : "Challenger"}</Badge>
            </div>
            <div style={{ display: "flex", gap: 16 }}>
              {[{ l: "P@k", v: run.precision }, { l: "R@k", v: run.recall }, { l: "F1", v: run.f1 }].map((m) => (
                <div key={m.l} style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, color: c.mutedForeground, marginBottom: 2 }}>{m.l}</div>
                  <div style={{ fontSize: 24, fontWeight: 700, fontFamily: fontMono, color: c.foreground }}>{m.v.toFixed(2)}</div>
                </div>
              ))}
            </div>
          </div></Card>
        ))}
      </div>
      <Card>
        <div style={{ overflow: "hidden", borderRadius: radius }}>
          <div style={{ display: "grid", gridTemplateColumns: "2fr 0.6fr 0.6fr 0.6fr 0.6fr 0.6fr 0.6fr 0.8fr", padding: "12px 24px", borderBottom: `1px solid ${c.border}`, fontSize: 12, fontWeight: 500, color: c.mutedForeground }}>
            <div>Query</div><div>P@k ①</div><div>P@k ②</div><div>R@k ①</div><div>R@k ②</div><div>F1 ①</div><div>F1 ②</div><div>Δ F1</div>
          </div>
          {qc.map((q, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "2fr 0.6fr 0.6fr 0.6fr 0.6fr 0.6fr 0.6fr 0.8fr", padding: "14px 24px", borderBottom: `1px solid ${c.border}`, alignItems: "center" }}>
              <div style={{ fontSize: 14, fontWeight: 500, color: c.foreground }}>{q.query}</div>
              <div style={{ fontFamily: fontMono, fontSize: 13, color: c.mutedForeground }}>{q.run1.p.toFixed(2)}</div>
              <div style={{ fontFamily: fontMono, fontSize: 13, color: c.mutedForeground }}>{q.run2.p.toFixed(2)}</div>
              <div style={{ fontFamily: fontMono, fontSize: 13, color: c.mutedForeground }}>{q.run1.r.toFixed(2)}</div>
              <div style={{ fontFamily: fontMono, fontSize: 13, color: c.mutedForeground }}>{q.run2.r.toFixed(2)}</div>
              <div style={{ fontFamily: fontMono, fontSize: 13, fontWeight: 600, color: c.foreground }}>{q.run1.f1.toFixed(2)}</div>
              <div style={{ fontFamily: fontMono, fontSize: 13, fontWeight: 600, color: c.foreground }}>{q.run2.f1.toFixed(2)}</div>
              <div>{delta(q.run1.f1, q.run2.f1)}</div>
            </div>
          ))}
        </div>
      </Card>
      <Card style={{ marginTop: 16 }}>
        <div style={{ padding: 20 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, color: c.foreground, margin: "0 0 8px" }}>Summary</h4>
          <p style={{ fontSize: 14, color: c.mutedForeground, margin: 0, lineHeight: 1.6 }}>
            Smaller chunk size (256) improved recall (+0.08) but decreased precision (−0.07) with negligible F1 change.
          </p>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// MAIN SHELL
// ═══════════════════════════════════════════════════════

export default function EvalWireframe() {
  const [activeTab, setActiveTab] = useState("golden-sets");
  const [currentView, setCurrentView] = useState("method-picker");

  const nav = (view, tab) => { if (tab) setActiveTab(tab); setCurrentView(view); };

  const renderContent = () => {
    if (activeTab === "golden-sets") {
      switch (currentView) {
        case "method-picker":
          return <GoldenSetMethodPicker onBack={() => nav("list")} onManual={() => nav("gs-editor")} onImport={() => nav("import")} onAutoGenerate={() => nav("auto-config")} />;
        case "gs-editor":
          return <GoldenSetEditorView onBack={() => nav("list")} onAddImport={() => nav("import")} onAddAutoGenerate={() => nav("auto-config")} />;
        case "import":
          return <ImportGoldenSetView onBack={() => nav("method-picker")} onConfirm={() => nav("gs-editor")} />;
        case "auto-config":
          return <AutoGenerateConfigView onBack={() => nav("method-picker")} onGenerate={() => nav("auto-review")} />;
        case "auto-review":
          return <ReviewGeneratedView onBack={() => nav("auto-config")} onSave={() => nav("gs-editor")} />;
        default:
          return <GoldenSetsListView onCreateNew={() => nav("method-picker")} onSelect={() => nav("gs-editor")} />;
      }
    }
    switch (currentView) {
      case "new-run": return <NewRunConfigView onBack={() => nav("list")} onExecute={() => nav("run-results")} onCreateGoldenSet={() => nav("method-picker", "golden-sets")} />;
      case "run-results": return <RunResultsView onBack={() => nav("list")} />;
      case "comparison": return <RunComparisonView onBack={() => nav("list")} />;
      default: return <EvalRunsListView onNewRun={() => nav("new-run")} onSelectRun={() => nav("run-results")} onCompare={() => nav("comparison")} />;
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: c.background, fontFamily: fontSans, color: c.foreground }}>
      <div style={{ borderBottom: `1px solid ${c.border}`, padding: "12px 24px", display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
        <span style={{ color: c.mutedForeground }}>Projects</span>
        <ChevronRight size={12} color={c.mutedForeground} />
        <span style={{ color: c.mutedForeground }}>FY2025 Analysis</span>
        <ChevronRight size={12} color={c.mutedForeground} />
        <span style={{ color: c.foreground, fontWeight: 500 }}>Evaluation</span>
      </div>
      <div style={{ display: "flex" }}>
        <div style={{ width: 200, borderRight: `1px solid ${c.border}`, padding: "20px 0", minHeight: "calc(100vh - 45px)" }}>
          <div style={{ padding: "0 16px", marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: c.mutedForeground, marginBottom: 4 }}>Project</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: c.foreground }}>FY2025 Analysis</div>
          </div>
          {[{ id: "documents", label: "Documents", icon: FileText }, { id: "indexes", label: "Indexes", icon: Layers }, { id: "eval", label: "Evaluation", icon: BarChart3, active: true }].map((item) => (
            <div key={item.id} style={{
              display: "flex", alignItems: "center", gap: 10, padding: "8px 16px", fontSize: 14,
              color: item.active ? c.foreground : c.mutedForeground,
              background: item.active ? c.muted : "transparent",
              fontWeight: item.active ? 500 : 400, cursor: "pointer",
            }}><item.icon size={16} />{item.label}</div>
          ))}
        </div>
        <div style={{ flex: 1, padding: 24, maxWidth: 1100 }}>
          <div style={{ display: "flex", gap: 0, marginBottom: 24, borderBottom: `1px solid ${c.border}` }}>
            {[{ id: "runs", label: "Runs", icon: Play }, { id: "golden-sets", label: "Golden Sets", icon: Target }].map((tab) => (
              <button key={tab.id} onClick={() => { setActiveTab(tab.id); setCurrentView("list"); }} style={{
                display: "flex", alignItems: "center", gap: 6, padding: "10px 20px",
                border: "none", background: "none", fontSize: 14, fontWeight: 500,
                fontFamily: fontSans, cursor: "pointer", marginBottom: -1,
                color: activeTab === tab.id ? c.foreground : c.mutedForeground,
                borderBottom: activeTab === tab.id ? `2px solid ${c.foreground}` : "2px solid transparent",
              }}><tab.icon size={14} />{tab.label}</button>
            ))}
          </div>
          {renderContent()}
        </div>
      </div>
    </div>
  );
}
