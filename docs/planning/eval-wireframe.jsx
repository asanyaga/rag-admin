import { useState } from "react";
import {
  Plus, Play, ArrowLeft, FileText, Search, ChevronRight,
  CheckCircle2, XCircle, AlertCircle, BarChart3, GitCompare,
  Eye, Trash2, ChevronDown, ArrowUpDown, Target, Layers, Check
} from "lucide-react";

// ─── shadcn/ui default color tokens (zinc-based dark) ───
const c = {
  bg: "hsl(240 10% 3.9%)",           // zinc-950
  card: "hsl(240 10% 3.9%)",
  cardForeground: "hsl(0 0% 98%)",
  popover: "hsl(240 10% 3.9%)",
  popoverForeground: "hsl(0 0% 98%)",
  primary: "hsl(0 0% 98%)",
  primaryForeground: "hsl(240 5.9% 10%)",
  secondary: "hsl(240 3.7% 15.9%)",
  secondaryForeground: "hsl(0 0% 98%)",
  muted: "hsl(240 3.7% 15.9%)",
  mutedForeground: "hsl(240 5% 64.9%)",
  accent: "hsl(240 3.7% 15.9%)",
  accentForeground: "hsl(0 0% 98%)",
  destructive: "hsl(0 62.8% 30.6%)",
  border: "hsl(240 3.7% 15.9%)",
  input: "hsl(240 3.7% 15.9%)",
  ring: "hsl(240 4.9% 83.9%)",
  // Semantic
  green: "hsl(142 71% 45%)",
  greenMuted: "hsla(142,71%,45%,0.12)",
  red: "hsl(0 84% 60%)",
  redMuted: "hsla(0,84%,60%,0.12)",
  amber: "hsl(38 92% 50%)",
  amberMuted: "hsla(38,92%,50%,0.12)",
  blueMuted: "hsla(217,91%,60%,0.12)",
  blue: "hsl(217 91% 60%)",
};

const radius = "0.5rem";
const fontStack = "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
const monoStack = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace";

// ─── Base UI primitives (shadcn-style) ───
function Badge({ children, variant = "secondary" }) {
  const variants = {
    secondary: { background: c.secondary, color: c.secondaryForeground },
    outline: { background: "transparent", color: c.mutedForeground, border: `1px solid ${c.border}` },
    success: { background: c.greenMuted, color: c.green },
    destructive: { background: c.redMuted, color: c.red },
    warning: { background: c.amberMuted, color: c.amber },
    blue: { background: c.blueMuted, color: c.blue },
  };
  const v = variants[variant] || variants.secondary;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      fontSize: 12, fontWeight: 500, padding: "2px 10px",
      borderRadius: "9999px", lineHeight: 1.6, ...v,
    }}>
      {children}
    </span>
  );
}

function Button({ children, variant = "default", size = "default", onClick, disabled, style: sx }) {
  const base = {
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6,
    borderRadius: radius, fontWeight: 500, cursor: disabled ? "not-allowed" : "pointer",
    fontFamily: fontStack, transition: "background 0.15s, opacity 0.15s",
    opacity: disabled ? 0.5 : 1, border: "none", outline: "none",
    fontSize: size === "sm" ? 13 : 14,
    padding: size === "sm" ? "6px 12px" : size === "icon" ? "8px" : "8px 16px",
    height: size === "icon" ? 36 : "auto",
    width: size === "icon" ? 36 : "auto",
  };
  const variants = {
    default: { background: c.primary, color: c.primaryForeground },
    secondary: { background: c.secondary, color: c.secondaryForeground },
    outline: { background: "transparent", color: c.cardForeground, border: `1px solid ${c.border}` },
    ghost: { background: "transparent", color: c.cardForeground },
    destructive: { background: c.destructive, color: c.cardForeground },
    link: { background: "transparent", color: c.blue, padding: 0, textDecoration: "underline", textUnderlineOffset: 4 },
  };
  return (
    <button onClick={onClick} disabled={disabled} style={{ ...base, ...variants[variant], ...sx }}>
      {children}
    </button>
  );
}

function Card({ children, style: sx }) {
  return (
    <div style={{
      background: c.card, border: `1px solid ${c.border}`,
      borderRadius: radius, ...sx,
    }}>
      {children}
    </div>
  );
}

function CardHeader({ title, description, action }) {
  return (
    <div style={{ padding: "20px 24px 12px", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
      <div>
        <h3 style={{ fontSize: 16, fontWeight: 600, color: c.cardForeground, margin: 0 }}>{title}</h3>
        {description && <p style={{ fontSize: 14, color: c.mutedForeground, margin: "4px 0 0" }}>{description}</p>}
      </div>
      {action}
    </div>
  );
}

function Input({ value, placeholder, readOnly, style: sx }) {
  return (
    <div style={{
      background: "transparent", border: `1px solid ${c.input}`,
      borderRadius: radius, padding: "8px 12px",
      fontSize: 14, color: readOnly ? c.mutedForeground : c.cardForeground,
      fontFamily: fontStack, ...sx,
    }}>
      {value || <span style={{ color: c.mutedForeground }}>{placeholder}</span>}
    </div>
  );
}

function Label({ children }) {
  return (
    <label style={{ fontSize: 14, fontWeight: 500, color: c.cardForeground, display: "block", marginBottom: 6 }}>
      {children}
    </label>
  );
}

function Separator() {
  return <div style={{ height: 1, background: c.border, width: "100%" }} />;
}

// ─── Composite components ───
function MetricCard({ label, value, subtitle, variant = "default" }) {
  const colorMap = { default: c.cardForeground, success: c.green, warning: c.amber, blue: c.blue };
  return (
    <Card style={{ flex: 1, minWidth: 140 }}>
      <div style={{ padding: "16px 20px" }}>
        <div style={{ fontSize: 14, color: c.mutedForeground, marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 28, fontWeight: 700, color: colorMap[variant], fontFamily: monoStack }}>{value}</div>
        {subtitle && <div style={{ fontSize: 13, color: c.mutedForeground, marginTop: 2 }}>{subtitle}</div>}
      </div>
    </Card>
  );
}

function StatusBadge({ status }) {
  const map = {
    completed: { variant: "success", label: "Completed" },
    running: { variant: "blue", label: "Running" },
    failed: { variant: "destructive", label: "Failed" },
    draft: { variant: "outline", label: "Draft" },
  };
  const s = map[status] || map.draft;
  return <Badge variant={s.variant}>{s.label}</Badge>;
}

function SectionHeader({ title, description, action }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: c.cardForeground, margin: 0 }}>{title}</h2>
        {description && <p style={{ fontSize: 14, color: c.mutedForeground, margin: "4px 0 0" }}>{description}</p>}
      </div>
      {action}
    </div>
  );
}

function Select({ icon: Icon, value, subtitle, children, open, onToggle }) {
  return (
    <div style={{ position: "relative" }}>
      <div
        onClick={onToggle}
        style={{
          background: "transparent",
          border: `1px solid ${c.input}`,
          borderRadius: radius,
          padding: "8px 12px",
          fontSize: 14,
          color: c.cardForeground,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "pointer",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {Icon && <Icon size={14} color={c.mutedForeground} />}
          {value}
        </div>
        <ChevronDown size={14} color={c.mutedForeground} style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }} />
      </div>
      {subtitle && <p style={{ fontSize: 13, color: c.mutedForeground, margin: "4px 0 0" }}>{subtitle}</p>}
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 50,
          background: c.popover, border: `1px solid ${c.border}`, borderRadius: radius,
          padding: 4, boxShadow: "0 8px 30px rgba(0,0,0,0.4)",
        }}>
          {children}
        </div>
      )}
    </div>
  );
}

function SelectItem({ children, selected, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: "8px 12px", borderRadius: "calc(0.5rem - 4px)", cursor: "pointer",
        fontSize: 14, color: c.cardForeground, display: "flex", alignItems: "center", justifyContent: "space-between",
        background: selected ? c.accent : "transparent",
      }}
      onMouseEnter={e => !selected && (e.currentTarget.style.background = c.accent)}
      onMouseLeave={e => !selected && (e.currentTarget.style.background = "transparent")}
    >
      <div>{children}</div>
      {selected && <Check size={14} color={c.mutedForeground} />}
    </div>
  );
}

// ─── Screen: Golden Sets List ───
function GoldenSetsListView({ onCreateNew, onSelect }) {
  const goldenSets = [
    { id: 1, name: "Financial Queries v1", queries: 12, docs: 3, created: "2025-01-15", status: "completed" },
    { id: 2, name: "Policy Questions", queries: 8, docs: 2, created: "2025-01-20", status: "draft" },
    { id: 3, name: "Revenue Deep Dive", queries: 24, docs: 5, created: "2025-02-01", status: "completed" },
  ];

  return (
    <div>
      <SectionHeader
        title="Golden Sets"
        description="Ground truth query-relevance pairs for evaluating retrieval quality"
        action={<Button onClick={onCreateNew}><Plus size={14} /> New Golden Set</Button>}
      />
      <Card>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${c.border}` }}>
                {["Name", "Queries", "Status", ""].map((h, i) => (
                  <th key={i} style={{
                    padding: "12px 16px", textAlign: "left",
                    fontSize: 14, fontWeight: 500, color: c.mutedForeground,
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {goldenSets.map(gs => (
                <tr
                  key={gs.id}
                  onClick={() => onSelect(gs)}
                  style={{ borderBottom: `1px solid ${c.border}`, cursor: "pointer" }}
                  onMouseEnter={e => e.currentTarget.style.background = c.muted}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                >
                  <td style={{ padding: "12px 16px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Target size={14} color={c.mutedForeground} />
                      <span style={{ fontWeight: 500, color: c.cardForeground }}>{gs.name}</span>
                      <span style={{ color: c.mutedForeground, fontSize: 13 }}>· {gs.docs} docs</span>
                    </div>
                  </td>
                  <td style={{ padding: "12px 16px", color: c.mutedForeground, fontFamily: monoStack, fontSize: 13 }}>{gs.queries} queries</td>
                  <td style={{ padding: "12px 16px" }}><StatusBadge status={gs.status} /></td>
                  <td style={{ padding: "12px 16px" }}><ChevronRight size={14} color={c.mutedForeground} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ─── Screen: Golden Set Editor ───
function GoldenSetEditorView({ onBack }) {
  const [selectedQuery, setSelectedQuery] = useState(0);

  const queries = [
    { query: "What was revenue in 2024?", sources: [{ doc: "FY2025 Annual Report.pdf", pages: [45] }] },
    { query: "What is the refund policy for enterprise clients?", sources: [{ doc: "Enterprise Agreement v3.pdf", pages: [12, 13] }] },
    { query: "How did operating costs change year-over-year?", sources: [{ doc: "FY2025 Annual Report.pdf", pages: [23, 45] }, { doc: "Q4 Board Deck.pdf", pages: [8] }] },
  ];
  const q = queries[selectedQuery];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: c.cardForeground, margin: 0 }}>Financial Queries v1</h2>
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: 0 }}>12 queries · 3 documents · Created Jan 15</p>
        </div>
        <Button><Plus size={14} /> Add Query</Button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 16 }}>
        <Card>
          <div style={{ padding: "12px 16px", borderBottom: `1px solid ${c.border}` }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: c.mutedForeground }}>Queries</span>
          </div>
          {queries.map((q, i) => (
            <div
              key={i}
              onClick={() => setSelectedQuery(i)}
              style={{
                padding: "12px 16px", borderBottom: `1px solid ${c.border}`, cursor: "pointer",
                background: selectedQuery === i ? c.accent : "transparent",
                borderLeft: selectedQuery === i ? `2px solid ${c.ring}` : "2px solid transparent",
              }}
              onMouseEnter={e => selectedQuery !== i && (e.currentTarget.style.background = c.muted)}
              onMouseLeave={e => selectedQuery !== i && (e.currentTarget.style.background = "transparent")}
            >
              <div style={{ fontSize: 14, color: c.cardForeground, marginBottom: 4, fontWeight: selectedQuery === i ? 500 : 400 }}>{q.query}</div>
              <div style={{ fontSize: 13, color: c.mutedForeground }}>
                {q.sources.length} doc{q.sources.length > 1 ? "s" : ""} · {q.sources.reduce((a, s) => a + s.pages.length, 0)} pages
              </div>
            </div>
          ))}
        </Card>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <Card>
            <div style={{ padding: 16 }}>
              <Label>Query</Label>
              <Input value={q.query} />
            </div>
          </Card>

          <Card>
            <div style={{ padding: "12px 16px", borderBottom: `1px solid ${c.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 14, fontWeight: 500, color: c.mutedForeground }}>Relevant Sources</span>
              <Button variant="outline" size="sm"><Plus size={13} /> Add Source</Button>
            </div>
            {q.sources.map((src, i) => (
              <div key={i} style={{ padding: "12px 16px", borderBottom: `1px solid ${c.border}`, display: "flex", alignItems: "center", gap: 12 }}>
                <FileText size={16} color={c.mutedForeground} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, color: c.cardForeground, fontWeight: 500 }}>{src.doc}</div>
                  <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                    {src.pages.map(p => (
                      <Badge key={p} variant="secondary">p.{p}</Badge>
                    ))}
                  </div>
                </div>
                <Button variant="ghost" size="icon"><Trash2 size={14} /></Button>
              </div>
            ))}
          </Card>

          <Card>
            <div style={{
              height: 260, display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", color: c.mutedForeground, gap: 8,
            }}>
              <FileText size={32} strokeWidth={1} />
              <div style={{ fontSize: 14, fontWeight: 500 }}>PDF Viewer</div>
              <div style={{ fontSize: 13, color: c.mutedForeground }}>Click a document above to preview · Click pages to mark as relevant</div>
              <Badge variant="outline" style={{ marginTop: 4 }}>Reuses existing react-pdf viewer component</Badge>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ─── Screen: Evaluation Runs List ───
function EvalRunsListView({ onNewRun, onSelectRun, onCompare }) {
  const runs = [
    { id: "run_001", name: "Run #1", goldenSet: "Financial Queries v1", index: "FY2025 — 512 tokens", config: "hybrid · k=5 · rrf=0.6", status: "completed", precision: 0.72, recall: 0.83, f1: 0.77, date: "Feb 5, 14:32" },
    { id: "run_002", name: "Run #2", goldenSet: "Financial Queries v1", index: "FY2025 — 256 tokens", config: "hybrid · k=5 · rrf=0.6", status: "completed", precision: 0.65, recall: 0.91, f1: 0.76, date: "Feb 5, 15:10" },
    { id: "run_003", name: "Run #3", goldenSet: "Financial Queries v1", index: "FY2025 — 512 tokens", config: "vector · k=10", status: "completed", precision: 0.58, recall: 0.67, f1: 0.62, date: "Feb 6, 09:45" },
    { id: "run_004", name: "Run #4", goldenSet: "Financial Queries v1", index: "FY2025 — 512 tokens", config: "hybrid · k=5 · rrf=0.8", status: "running", precision: null, recall: null, f1: null, date: "Feb 9, 11:20" },
  ];

  const [selected, setSelected] = useState([]);
  const toggleSelect = (id) => setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : prev.length < 2 ? [...prev, id] : prev);

  return (
    <div>
      <SectionHeader
        title="Evaluation Runs"
        description="Compare retrieval performance across indexes and configurations"
        action={
          <div style={{ display: "flex", gap: 8 }}>
            {selected.length === 2 && <Button variant="outline" onClick={onCompare}><GitCompare size={14} /> Compare Selected</Button>}
            <Button onClick={onNewRun}><Play size={14} /> New Run</Button>
          </div>
        }
      />

      {selected.length === 1 && (
        <Card style={{ padding: "10px 16px", marginBottom: 12, borderColor: c.ring }}>
          <span style={{ fontSize: 13, color: c.mutedForeground }}>Select one more run to compare</span>
        </Card>
      )}

      <Card>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${c.border}` }}>
                {["", "Run", "Index", "Config", "P@k", "R@k", "F1", "Status"].map((h, i) => (
                  <th key={i} style={{ padding: "12px 16px", textAlign: "left", fontSize: 14, fontWeight: 500, color: c.mutedForeground, whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map(run => (
                <tr
                  key={run.id}
                  style={{
                    borderBottom: `1px solid ${c.border}`,
                    background: selected.includes(run.id) ? c.accent : "transparent",
                  }}
                  onMouseEnter={e => !selected.includes(run.id) && (e.currentTarget.style.background = c.muted)}
                  onMouseLeave={e => !selected.includes(run.id) && (e.currentTarget.style.background = selected.includes(run.id) ? c.accent : "transparent")}
                >
                  <td style={{ padding: "12px 16px", width: 32 }}>
                    <input type="checkbox" checked={selected.includes(run.id)} onChange={() => toggleSelect(run.id)} disabled={run.status !== "completed"}
                      style={{ accentColor: "hsl(240 4.9% 83.9%)", width: 16, height: 16, borderRadius: 4, cursor: "pointer" }} />
                  </td>
                  <td style={{ padding: "12px 16px", cursor: "pointer" }} onClick={() => onSelectRun(run)}>
                    <div style={{ fontWeight: 500, color: c.cardForeground }}>{run.name}</div>
                    <div style={{ fontSize: 13, color: c.mutedForeground }}>{run.date}</div>
                  </td>
                  <td style={{ padding: "12px 16px", color: c.mutedForeground, fontSize: 13 }}>{run.index}</td>
                  <td style={{ padding: "12px 16px", fontFamily: monoStack, fontSize: 13, color: c.mutedForeground }}>{run.config}</td>
                  <td style={{ padding: "12px 16px", fontFamily: monoStack, fontWeight: 600, color: run.precision ? c.cardForeground : c.mutedForeground }}>
                    {run.precision?.toFixed(2) ?? "—"}
                  </td>
                  <td style={{ padding: "12px 16px", fontFamily: monoStack, fontWeight: 600, color: run.recall ? c.cardForeground : c.mutedForeground }}>
                    {run.recall?.toFixed(2) ?? "—"}
                  </td>
                  <td style={{ padding: "12px 16px", fontFamily: monoStack, fontWeight: 600, color: run.f1 ? c.cardForeground : c.mutedForeground }}>
                    {run.f1?.toFixed(2) ?? "—"}
                  </td>
                  <td style={{ padding: "12px 16px" }}><StatusBadge status={run.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ─── Screen: New Run Configuration ───
function NewRunConfigView({ onBack, onExecute, onCreateGoldenSet }) {
  const [gsOpen, setGsOpen] = useState(false);
  const [selectedGs, setSelectedGs] = useState("Financial Queries v1");
  const [idxOpen, setIdxOpen] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState("FY2025 — 512 tokens");
  const [searchMode, setSearchMode] = useState("Hybrid");

  const goldenSets = [
    { name: "Financial Queries v1", meta: "12 queries · 3 docs" },
    { name: "Policy Questions", meta: "8 queries · 2 docs" },
    { name: "Revenue Deep Dive", meta: "24 queries · 5 docs" },
  ];

  const indexes = [
    { name: "FY2025 — 512 tokens", meta: "text-embedding-3-small · hybrid" },
    { name: "FY2025 — 256 tokens", meta: "text-embedding-3-small · hybrid" },
    { name: "FY2025 — 1024 tokens", meta: "text-embedding-3-large · vector" },
  ];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: c.cardForeground, margin: 0 }}>Configure Evaluation Run</h2>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, maxWidth: 800 }}>
        {/* Golden Set */}
        <Card>
          <div style={{ padding: 20 }}>
            <Label>Golden Set</Label>
            <Select
              icon={Target}
              value={selectedGs}
              subtitle={goldenSets.find(g => g.name === selectedGs)?.meta}
              open={gsOpen}
              onToggle={() => { setGsOpen(!gsOpen); setIdxOpen(false); }}
            >
              {goldenSets.map(gs => (
                <SelectItem key={gs.name} selected={gs.name === selectedGs} onClick={() => { setSelectedGs(gs.name); setGsOpen(false); }}>
                  <div>
                    <div style={{ fontWeight: 500 }}>{gs.name}</div>
                    <div style={{ fontSize: 13, color: c.mutedForeground }}>{gs.meta}</div>
                  </div>
                </SelectItem>
              ))}
              <Separator />
              <div
                onClick={() => { setGsOpen(false); onCreateGoldenSet?.(); }}
                style={{
                  padding: "8px 12px", borderRadius: "calc(0.5rem - 4px)", cursor: "pointer",
                  fontSize: 14, color: c.mutedForeground, display: "flex", alignItems: "center", gap: 8,
                }}
                onMouseEnter={e => e.currentTarget.style.background = c.accent}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <Plus size={14} />
                <span>Create new golden set</span>
              </div>
            </Select>
          </div>
        </Card>

        {/* Index */}
        <Card>
          <div style={{ padding: 20 }}>
            <Label>Index</Label>
            <Select
              icon={Layers}
              value={selectedIdx}
              subtitle={indexes.find(x => x.name === selectedIdx)?.meta}
              open={idxOpen}
              onToggle={() => { setIdxOpen(!idxOpen); setGsOpen(false); }}
            >
              {indexes.map(idx => (
                <SelectItem key={idx.name} selected={idx.name === selectedIdx} onClick={() => { setSelectedIdx(idx.name); setIdxOpen(false); }}>
                  <div>
                    <div style={{ fontWeight: 500 }}>{idx.name}</div>
                    <div style={{ fontSize: 13, color: c.mutedForeground }}>{idx.meta}</div>
                  </div>
                </SelectItem>
              ))}
            </Select>
          </div>
        </Card>

        {/* Retrieval Config */}
        <Card>
          <div style={{ padding: 20 }}>
            <Label>Retrieval Configuration</Label>
            <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 4 }}>
              <div>
                <div style={{ fontSize: 14, color: c.mutedForeground, marginBottom: 6 }}>Search Mode</div>
                <div style={{ display: "flex", gap: 0, border: `1px solid ${c.border}`, borderRadius: radius, overflow: "hidden" }}>
                  {["Vector", "BM25", "Hybrid"].map(mode => (
                    <button
                      key={mode}
                      onClick={() => setSearchMode(mode)}
                      style={{
                        flex: 1, padding: "8px 16px", border: "none", cursor: "pointer",
                        fontSize: 13, fontFamily: fontStack, fontWeight: 500,
                        background: searchMode === mode ? c.primary : "transparent",
                        color: searchMode === mode ? c.primaryForeground : c.mutedForeground,
                        transition: "all 0.15s",
                      }}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <div style={{ fontSize: 14, color: c.mutedForeground, marginBottom: 6 }}>Top K</div>
                  <Input value="5" style={{ fontFamily: monoStack }} />
                </div>
                <div>
                  <div style={{ fontSize: 14, color: c.mutedForeground, marginBottom: 6 }}>RRF Weight</div>
                  <Input value="0.6" style={{ fontFamily: monoStack }} />
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Run Name */}
        <Card>
          <div style={{ padding: 20 }}>
            <Label>Run Name <span style={{ fontWeight: 400, color: c.mutedForeground }}>(optional)</span></Label>
            <Input placeholder="Auto: Run #4 — hybrid · k=5 · rrf=0.6" />
            <p style={{ fontSize: 13, color: c.mutedForeground, marginTop: 6 }}>A descriptive name helps when comparing runs later</p>
          </div>
        </Card>
      </div>

      <div style={{ marginTop: 24, display: "flex", gap: 8 }}>
        <Button onClick={onExecute}><Play size={14} /> Run Evaluation</Button>
        <Button variant="outline" onClick={onBack}>Cancel</Button>
      </div>
    </div>
  );
}

// ─── Screen: Run Results Detail ───
function RunResultsView({ onBack }) {
  const [expandedQuery, setExpandedQuery] = useState(0);

  const queryResults = [
    {
      query: "What was revenue in 2024?", precision: 0.60, recall: 1.0, f1: 0.75,
      retrieved: [
        { rank: 1, doc: "FY2025 Annual Report.pdf", page: 12, relevant: false, snippet: "Our revenue 2025 performance (USD 4.2B) exceeded 2024 targets..." },
        { rank: 2, doc: "FY2025 Annual Report.pdf", page: 2, relevant: false, snippet: "This annual report covers fiscal year ending December 2025..." },
        { rank: 3, doc: "FY2025 Annual Report.pdf", page: 45, relevant: true, snippet: "Revenue comparison: 2023: $3.1B, 2024: $3.8B, 2025: $4.2B..." },
        { rank: 4, doc: "Q4 Board Deck.pdf", page: 8, relevant: false, snippet: "Q4 revenue targets were met across all business units..." },
        { rank: 5, doc: "FY2025 Annual Report.pdf", page: 46, relevant: false, snippet: "Revenue by segment: Enterprise $2.1B, SMB $1.2B..." },
      ],
      expected: [{ doc: "FY2025 Annual Report.pdf", pages: [45] }],
    },
    {
      query: "What is the refund policy for enterprise clients?", precision: 0.80, recall: 1.0, f1: 0.89,
      retrieved: [
        { rank: 1, doc: "Enterprise Agreement v3.pdf", page: 12, relevant: true, snippet: "Section 4.2: Refund Policy. Enterprise clients are entitled to..." },
        { rank: 2, doc: "Enterprise Agreement v3.pdf", page: 13, relevant: true, snippet: "...pro-rated refunds within 30 days of service termination..." },
        { rank: 3, doc: "FY2025 Annual Report.pdf", page: 78, relevant: false, snippet: "Customer retention metrics improved with revised refund..." },
        { rank: 4, doc: "Enterprise Agreement v3.pdf", page: 14, relevant: false, snippet: "Section 4.3: Service Level Agreements..." },
        { rank: 5, doc: "Enterprise Agreement v3.pdf", page: 12, relevant: true, snippet: "Refund processing timelines vary by payment method..." },
      ],
      expected: [{ doc: "Enterprise Agreement v3.pdf", pages: [12, 13] }],
    },
    {
      query: "How did operating costs change year-over-year?", precision: 0.40, recall: 0.50, f1: 0.44,
      retrieved: [
        { rank: 1, doc: "FY2025 Annual Report.pdf", page: 67, relevant: false, snippet: "Total operating expenses for FY2025 were $2.8B..." },
        { rank: 2, doc: "FY2025 Annual Report.pdf", page: 3, relevant: false, snippet: "Key financial highlights: Revenue growth 10.5%..." },
        { rank: 3, doc: "FY2025 Annual Report.pdf", page: 23, relevant: true, snippet: "Year-over-year operating cost analysis shows 8.2% increase..." },
        { rank: 4, doc: "FY2025 Annual Report.pdf", page: 68, relevant: false, snippet: "Depreciation and amortization totaled $340M..." },
        { rank: 5, doc: "Q4 Board Deck.pdf", page: 3, relevant: false, snippet: "Operating efficiency metrics dashboard..." },
      ],
      expected: [{ doc: "FY2025 Annual Report.pdf", pages: [23, 45] }, { doc: "Q4 Board Deck.pdf", pages: [8] }],
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: c.cardForeground, margin: 0 }}>Run #1</h2>
          <p style={{ fontSize: 13, color: c.mutedForeground, margin: 0 }}>
            Financial Queries v1 · FY2025 — 512 tokens · hybrid · k=5 · rrf=0.6 · Feb 5, 14:32
          </p>
        </div>
        <StatusBadge status="completed" />
      </div>

      <div style={{ display: "flex", gap: 12, marginBottom: 24 }}>
        <MetricCard label="Precision@5" value="0.72" subtitle="Avg across 12 queries" />
        <MetricCard label="Recall@5" value="0.83" subtitle="Avg across 12 queries" variant="success" />
        <MetricCard label="F1@5" value="0.77" subtitle="Harmonic mean" variant="warning" />
        <MetricCard label="Queries" value="12" subtitle="3 below threshold" variant="blue" />
      </div>

      <SectionHeader title="Per-Query Results" description="Click a query to see retrieved chunks vs. expected sources" />

      <Card>
        {queryResults.map((qr, i) => (
          <div key={i}>
            <div
              onClick={() => setExpandedQuery(expandedQuery === i ? -1 : i)}
              style={{
                display: "grid", gridTemplateColumns: "2fr 0.6fr 0.6fr 0.6fr 24px",
                padding: "14px 16px", borderBottom: `1px solid ${c.border}`, cursor: "pointer",
                alignItems: "center", background: expandedQuery === i ? c.muted : "transparent",
              }}
              onMouseEnter={e => e.currentTarget.style.background = c.muted}
              onMouseLeave={e => expandedQuery !== i && (e.currentTarget.style.background = "transparent")}
            >
              <div style={{ fontSize: 14, color: c.cardForeground, fontWeight: 500 }}>{qr.query}</div>
              <div style={{ fontFamily: monoStack, fontSize: 13, color: c.mutedForeground }}>P: {qr.precision.toFixed(2)}</div>
              <div style={{ fontFamily: monoStack, fontSize: 13, color: c.mutedForeground }}>R: {qr.recall.toFixed(2)}</div>
              <div style={{
                fontFamily: monoStack, fontSize: 13, fontWeight: 600,
                color: qr.f1 >= 0.7 ? c.green : qr.f1 >= 0.5 ? c.amber : c.red,
              }}>F1: {qr.f1.toFixed(2)}</div>
              <ChevronDown size={14} color={c.mutedForeground} style={{ transform: expandedQuery === i ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }} />
            </div>

            {expandedQuery === i && (
              <div style={{ padding: 16, background: c.bg, borderBottom: `1px solid ${c.border}` }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: c.mutedForeground, marginBottom: 10 }}>Retrieved (top {qr.retrieved.length})</div>
                    {qr.retrieved.map((chunk, j) => (
                      <div key={j} style={{
                        display: "flex", gap: 10, padding: "10px 12px", marginBottom: 6,
                        borderRadius: radius, border: `1px solid ${chunk.relevant ? c.green + "44" : c.border}`,
                        background: chunk.relevant ? c.greenMuted : "transparent",
                      }}>
                        <div style={{
                          width: 24, height: 24, borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center",
                          background: c.muted, fontSize: 12, fontFamily: monoStack, color: c.mutedForeground, flexShrink: 0,
                        }}>{chunk.rank}</div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4, flexWrap: "wrap" }}>
                            <span style={{ fontSize: 13, fontWeight: 500, color: c.cardForeground }}>{chunk.doc}</span>
                            <Badge variant="secondary">p.{chunk.page}</Badge>
                            {chunk.relevant ? <CheckCircle2 size={13} color={c.green} /> : <XCircle size={13} color={c.mutedForeground} />}
                          </div>
                          <div style={{ fontSize: 13, color: c.mutedForeground, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{chunk.snippet}</div>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div>
                    <div style={{ fontSize: 14, fontWeight: 500, color: c.mutedForeground, marginBottom: 10 }}>Expected (Golden Set)</div>
                    {qr.expected.map((exp, j) => (
                      <div key={j} style={{ padding: "10px 12px", marginBottom: 6, borderRadius: radius, border: `1px solid ${c.border}` }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                          <FileText size={14} color={c.mutedForeground} />
                          <span style={{ fontSize: 13, fontWeight: 500, color: c.cardForeground }}>{exp.doc}</span>
                        </div>
                        <div style={{ display: "flex", gap: 6 }}>
                          {exp.pages.map(p => {
                            const found = qr.retrieved.some(r => r.doc === exp.doc && r.page === p && r.relevant);
                            return <Badge key={p} variant={found ? "success" : "destructive"}>p.{p} {found ? "✓" : "✗"}</Badge>;
                          })}
                        </div>
                      </div>
                    ))}

                    <Card style={{ marginTop: 12 }}>
                      <div style={{ padding: "12px 16px" }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: c.mutedForeground, marginBottom: 6 }}>Observation</div>
                        <div style={{ fontSize: 14, color: c.mutedForeground, lineHeight: 1.5 }}>
                          {qr.f1 >= 0.7
                            ? "Good retrieval — relevant sources were found in the top results."
                            : "Relevant page appeared at rank " + (qr.retrieved.findIndex(r => r.relevant) + 1) + ". Semantic similarity to other mentions may be ranking non-ideal chunks higher."
                          }
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

// ─── Screen: Run Comparison ───
function RunComparisonView({ onBack }) {
  const runs = [
    { name: "Run #1", index: "512 tokens", config: "hybrid · k=5 · rrf=0.6", precision: 0.72, recall: 0.83, f1: 0.77 },
    { name: "Run #2", index: "256 tokens", config: "hybrid · k=5 · rrf=0.6", precision: 0.65, recall: 0.91, f1: 0.76 },
  ];

  const queryComparisons = [
    { query: "What was revenue in 2024?", run1: { p: 0.60, r: 1.0, f1: 0.75 }, run2: { p: 0.40, r: 1.0, f1: 0.57 } },
    { query: "Refund policy for enterprise?", run1: { p: 0.80, r: 1.0, f1: 0.89 }, run2: { p: 0.80, r: 1.0, f1: 0.89 } },
    { query: "Operating costs YoY?", run1: { p: 0.40, r: 0.50, f1: 0.44 }, run2: { p: 0.60, r: 0.75, f1: 0.67 } },
  ];

  const delta = (a, b) => {
    const d = b - a;
    if (Math.abs(d) < 0.005) return <span style={{ color: c.mutedForeground }}>—</span>;
    return <span style={{ color: d > 0 ? c.green : c.red, fontFamily: monoStack, fontSize: 13 }}>{d > 0 ? "+" : ""}{d.toFixed(2)}</span>;
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
        <Button variant="ghost" size="icon" onClick={onBack}><ArrowLeft size={16} /></Button>
        <h2 style={{ fontSize: 18, fontWeight: 600, color: c.cardForeground, margin: 0 }}>Compare Runs</h2>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
        {runs.map((run, i) => (
          <Card key={i}>
            <div style={{ padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: c.cardForeground }}>{run.name}</div>
                  <div style={{ fontSize: 13, color: c.mutedForeground }}>{run.index} · {run.config}</div>
                </div>
                <Badge variant={i === 0 ? "secondary" : "warning"}>{i === 0 ? "Baseline" : "Challenger"}</Badge>
              </div>
              <div style={{ display: "flex", gap: 16 }}>
                {[
                  { label: "P@k", value: run.precision },
                  { label: "R@k", value: run.recall },
                  { label: "F1", value: run.f1 },
                ].map(m => (
                  <div key={m.label} style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, color: c.mutedForeground, marginBottom: 2 }}>{m.label}</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: c.cardForeground, fontFamily: monoStack }}>{m.value.toFixed(2)}</div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>

      <SectionHeader title="Per-Query Comparison" description="Delta shows change from baseline → challenger" />
      <Card>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${c.border}` }}>
                {["Query", "P@k (1)", "P@k (2)", "R@k (1)", "R@k (2)", "F1 (1)", "F1 (2)", "Δ F1"].map((h, i) => (
                  <th key={i} style={{ padding: "12px 16px", textAlign: "left", fontSize: 14, fontWeight: 500, color: c.mutedForeground, whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {queryComparisons.map((qc, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${c.border}` }}>
                  <td style={{ padding: "12px 16px", fontWeight: 500, color: c.cardForeground }}>{qc.query}</td>
                  <td style={{ padding: "12px 16px", fontFamily: monoStack, color: c.mutedForeground }}>{qc.run1.p.toFixed(2)}</td>
                  <td style={{ padding: "12px 16px", fontFamily: monoStack, color: c.mutedForeground }}>{qc.run2.p.toFixed(2)}</td>
                  <td style={{ padding: "12px 16px", fontFamily: monoStack, color: c.mutedForeground }}>{qc.run1.r.toFixed(2)}</td>
                  <td style={{ padding: "12px 16px", fontFamily: monoStack, color: c.mutedForeground }}>{qc.run2.r.toFixed(2)}</td>
                  <td style={{ padding: "12px 16px", fontFamily: monoStack, color: c.cardForeground }}>{qc.run1.f1.toFixed(2)}</td>
                  <td style={{ padding: "12px 16px", fontFamily: monoStack, color: c.cardForeground }}>{qc.run2.f1.toFixed(2)}</td>
                  <td style={{ padding: "12px 16px" }}>{delta(qc.run1.f1, qc.run2.f1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card style={{ marginTop: 16 }}>
        <div style={{ padding: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: c.mutedForeground, marginBottom: 8 }}>Summary</div>
          <div style={{ fontSize: 14, color: c.mutedForeground, lineHeight: 1.6 }}>
            Smaller chunk size (256 tokens) improved recall (+0.08) but decreased precision (−0.07) with negligible F1 change (−0.01). The 256-token index retrieves more relevant pages but also more noise. Consider this tradeoff based on whether recall or precision matters more for your use case.
          </div>
        </div>
      </Card>
    </div>
  );
}

// ─── Main App Shell ───
export default function EvalWireframe() {
  const [activeTab, setActiveTab] = useState("runs");
  const [currentView, setCurrentView] = useState("list");

  const renderContent = () => {
    if (activeTab === "golden-sets") {
      if (currentView === "gs-editor") return <GoldenSetEditorView onBack={() => setCurrentView("list")} />;
      return <GoldenSetsListView onCreateNew={() => setCurrentView("gs-editor")} onSelect={() => setCurrentView("gs-editor")} />;
    }
    switch (currentView) {
      case "new-run":
        return <NewRunConfigView onBack={() => setCurrentView("list")} onExecute={() => setCurrentView("run-results")} onCreateGoldenSet={() => { setActiveTab("golden-sets"); setCurrentView("gs-editor"); }} />;
      case "run-results":
        return <RunResultsView onBack={() => setCurrentView("list")} />;
      case "comparison":
        return <RunComparisonView onBack={() => setCurrentView("list")} />;
      default:
        return <EvalRunsListView onNewRun={() => setCurrentView("new-run")} onSelectRun={() => setCurrentView("run-results")} onCompare={() => setCurrentView("comparison")} />;
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: c.bg, fontFamily: fontStack, color: c.cardForeground }}>
      {/* Breadcrumb */}
      <div style={{ borderBottom: `1px solid ${c.border}`, padding: "12px 24px", display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
        <span style={{ color: c.mutedForeground }}>Projects</span>
        <ChevronRight size={12} color={c.mutedForeground} />
        <span style={{ color: c.mutedForeground }}>FY2025 Analysis</span>
        <ChevronRight size={12} color={c.mutedForeground} />
        <span style={{ color: c.cardForeground, fontWeight: 500 }}>Evaluation</span>
      </div>

      <div style={{ display: "flex" }}>
        {/* Sidebar */}
        <div style={{ width: 200, borderRight: `1px solid ${c.border}`, padding: "20px 0", minHeight: "calc(100vh - 44px)" }}>
          <div style={{ padding: "0 16px", marginBottom: 20 }}>
            <div style={{ fontSize: 13, color: c.mutedForeground, marginBottom: 2 }}>Project</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: c.cardForeground }}>FY2025 Analysis</div>
          </div>
          {[
            { id: "documents", label: "Documents", icon: FileText, active: false },
            { id: "indexes", label: "Indexes", icon: Layers, active: false },
            { id: "eval", label: "Evaluation", icon: BarChart3, active: true },
          ].map(item => (
            <div key={item.id} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 16px", fontSize: 14,
              color: item.active ? c.cardForeground : c.mutedForeground,
              background: item.active ? c.accent : "transparent",
              borderLeft: item.active ? `2px solid ${c.ring}` : "2px solid transparent",
              cursor: "pointer", fontWeight: item.active ? 500 : 400,
            }}>
              <item.icon size={16} />
              {item.label}
            </div>
          ))}
        </div>

        {/* Main */}
        <div style={{ flex: 1, padding: 24 }}>
          <div style={{ display: "flex", gap: 0, marginBottom: 24, borderBottom: `1px solid ${c.border}` }}>
            {[
              { id: "runs", label: "Runs", icon: Play },
              { id: "golden-sets", label: "Golden Sets", icon: Target },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => { setActiveTab(tab.id); setCurrentView("list"); }}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "10px 20px", border: "none", background: "none",
                  color: activeTab === tab.id ? c.cardForeground : c.mutedForeground,
                  borderBottom: activeTab === tab.id ? `2px solid ${c.cardForeground}` : "2px solid transparent",
                  cursor: "pointer", fontSize: 14, fontWeight: 500, fontFamily: fontStack, marginBottom: -1,
                }}
              >
                <tab.icon size={14} />
                {tab.label}
              </button>
            ))}
          </div>
          {renderContent()}
        </div>
      </div>
    </div>
  );
}