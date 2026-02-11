import { useState, useEffect, useRef } from "react";

const MOCK_CHUNKS = [
  {
    id: 1,
    score: 0.91,
    page: 14,
    content:
      "In Q3 2024, Acorn REIT Fund delivered a total return of 12.3%, driven primarily by strong performance in the industrial and logistics sector. The fund's NAV per unit increased from $14.82 to $16.64 during the quarter.",
  },
  {
    id: 2,
    score: 0.87,
    page: 16,
    content:
      "Against the MSCI US REIT Index benchmark return of 10.2%, the fund outperformed by 210 basis points. This marks the third consecutive quarter of benchmark-beating performance.",
  },
  {
    id: 3,
    score: 0.79,
    page: 22,
    content:
      "Occupancy rates across the portfolio remained stable at 96.4%, with industrial properties achieving 98.1% occupancy. Weighted average lease expiry (WALE) stands at 5.2 years.",
  },
  {
    id: 4,
    score: 0.74,
    page: 31,
    content:
      "Distribution per unit for Q3 was $0.38, representing a 4.2% increase over the prior quarter. The annualized distribution yield based on the closing price of $15.90 is 9.6%.",
  },
  {
    id: 5,
    score: 0.68,
    page: 8,
    content:
      "The fund completed the acquisition of two logistics facilities in the Dallas-Fort Worth metropolitan area for a combined $42.3 million, funded through a combination of debt and existing cash reserves.",
  },
];

const MOCK_ANSWER_TOKENS = `The Acorn REIT Fund delivered a strong Q3 2024, achieving a total return of 12.3% with NAV per unit rising from $14.82 to $16.64 [1]. This result outperformed the MSCI US REIT Index benchmark by 210 basis points, continuing a three-quarter streak of above-benchmark performance [2].

Portfolio fundamentals remain solid with occupancy at 96.4% overall, and industrial properties notably reaching 98.1% [3]. The fund also increased its distribution to $0.38 per unit, a 4.2% quarter-over-quarter increase, translating to an annualized yield of 9.6% [4].

On the growth side, the fund deployed capital into two Dallas-Fort Worth logistics facilities for $42.3 million [5], consistent with its strategy of expanding industrial exposure in high-demand markets.`;

// ── Icons ──
function SearchIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}
function SlidersIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="4" x2="4" y1="21" y2="14" /><line x1="4" x2="4" y1="10" y2="3" /><line x1="12" x2="12" y1="21" y2="12" /><line x1="12" x2="12" y1="8" y2="3" /><line x1="20" x2="20" y1="21" y2="16" /><line x1="20" x2="20" y1="12" y2="3" /><line x1="2" x2="6" y1="14" y2="14" /><line x1="10" x2="14" y1="8" y2="8" /><line x1="18" x2="22" y1="16" y2="16" />
    </svg>
  );
}
function SparklesIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.582a.5.5 0 0 1 0 .963L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
      <path d="M20 3v4" /><path d="M22 5h-4" />
    </svg>
  );
}
function FileTextIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" /><path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="M10 9H8" /><path d="M16 13H8" /><path d="M16 17H8" />
    </svg>
  );
}
function PlayIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="6 3 20 12 6 21 6 3" />
    </svg>
  );
}
function ClockIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
function ChevronIcon({ size = 16, direction = "down" }) {
  const rotation = direction === "up" ? 180 : 0;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: `rotate(${rotation}deg)` }}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}
function CheckIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}
function CopyIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2" /><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  );
}
function StopIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="16" height="16" x="4" y="4" rx="2" />
    </svg>
  );
}
function InfoIcon({ size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="M12 16v-4" /><path d="M12 8h.01" />
    </svg>
  );
}
function SettingsIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" /><circle cx="12" cy="12" r="3" />
    </svg>
  );
}
function HomeIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8" /><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}
function FolderIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
    </svg>
  );
}
function DatabaseIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5V19A9 3 0 0 0 21 19V5" /><path d="M3 12A9 3 0 0 0 21 12" />
    </svg>
  );
}
function BarChartIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" x2="12" y1="20" y2="10" /><line x1="18" x2="18" y1="20" y2="4" /><line x1="6" x2="6" y1="20" y2="16" />
    </svg>
  );
}

// ── Tooltip ──
function Tooltip({ children, text }) {
  const [show, setShow] = useState(false);
  return (
    <span style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
      onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span style={{
          position: "absolute", bottom: "calc(100% + 6px)", left: "50%", transform: "translateX(-50%)",
          background: "#18181b", color: "#fafafa", fontSize: 12, padding: "4px 8px", borderRadius: 6,
          whiteSpace: "nowrap", zIndex: 50, pointerEvents: "none",
        }}>{text}</span>
      )}
    </span>
  );
}

// ── Select dropdown ──
function Select({ value, onChange, options, style }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);
  const selected = options.find((o) => o.value === value);
  return (
    <div ref={ref} style={{ position: "relative", ...style }}>
      <button onClick={() => setOpen(!open)} style={{
        width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "6px 10px", border: "1px solid #e4e4e7", borderRadius: 6, background: "white",
        fontSize: 13, cursor: "pointer", color: "#09090b", height: 34,
      }}>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{selected?.label}</span>
        <ChevronIcon size={14} direction={open ? "up" : "down"} />
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, background: "white",
          border: "1px solid #e4e4e7", borderRadius: 6, zIndex: 50, boxShadow: "0 4px 6px -1px rgba(0,0,0,.1)",
          maxHeight: 200, overflowY: "auto",
        }}>
          {options.map((o) => (
            <div key={o.value} onClick={() => { onChange(o.value); setOpen(false); }}
              style={{
                padding: "6px 10px", fontSize: 13, cursor: "pointer", display: "flex",
                alignItems: "center", gap: 6,
                background: o.value === value ? "#f4f4f5" : "transparent",
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = "#f4f4f5"}
              onMouseLeave={(e) => e.currentTarget.style.background = o.value === value ? "#f4f4f5" : "transparent"}>
              <span style={{ width: 14, flexShrink: 0 }}>{o.value === value && <CheckIcon size={12} />}</span>
              <span>{o.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Slider ──
function Slider({ min, max, step, value, onChange, leftLabel, rightLabel }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))}
        style={{
          width: "100%", height: 6, appearance: "none", background: `linear-gradient(to right, #18181b ${pct}%, #e4e4e7 ${pct}%)`,
          borderRadius: 3, outline: "none", cursor: "pointer",
        }}
      />
      {(leftLabel || rightLabel) && (
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#a1a1aa", marginTop: 2 }}>
          <span>{leftLabel}</span><span>{rightLabel}</span>
        </div>
      )}
    </div>
  );
}

// ── Toggle group (search type style) ──
function ToggleGroup({ options, value, onChange }) {
  return (
    <div style={{ display: "flex", border: "1px solid #e4e4e7", borderRadius: 6, overflow: "hidden" }}>
      {options.map((o) => (
        <button key={o.value} onClick={() => onChange(o.value)}
          style={{
            flex: 1, padding: "5px 10px", fontSize: 13, border: "none", cursor: "pointer",
            background: value === o.value ? "#18181b" : "white",
            color: value === o.value ? "white" : "#71717a",
            fontWeight: value === o.value ? 500 : 400,
            borderRight: o !== options[options.length - 1] ? "1px solid #e4e4e7" : "none",
          }}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ── Citation renderer ──
function renderAnswerWithCitations(text, highlightedChunk, onCitationClick) {
  const parts = [];
  const regex = /\[(\d+)\]/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<span key={`t-${lastIndex}`}>{text.slice(lastIndex, match.index)}</span>);
    }
    const num = parseInt(match[1]);
    parts.push(
      <button key={`c-${match.index}`} onClick={() => onCitationClick(num)}
        style={{
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          background: highlightedChunk === num ? "#18181b" : "#f4f4f5",
          color: highlightedChunk === num ? "white" : "#18181b",
          border: "none", borderRadius: 4, fontSize: 11, fontWeight: 600,
          padding: "1px 5px", cursor: "pointer", verticalAlign: "super",
          marginLeft: 1, marginRight: 1, lineHeight: 1,
          transition: "all 0.15s ease",
        }}>
        {num}
      </button>
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) parts.push(<span key={`t-${lastIndex}`}>{text.slice(lastIndex)}</span>);
  return parts;
}

// ── Score bar ──
function ScoreBar({ score }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width: 48, height: 4, background: "#e4e4e7", borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${score * 100}%`, height: "100%", background: "#18181b", borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: 12, color: "#71717a", fontVariantNumeric: "tabular-nums" }}>{score.toFixed(2)}</span>
    </div>
  );
}

// ── Main Component ──
export default function AnswerPlaygroundWireframe() {
  // Retrieval params
  const [searchType, setSearchType] = useState("hybrid");
  const [topK, setTopK] = useState(5);
  const [threshold, setThreshold] = useState(0.0);

  // Mode & LLM params
  const [mode, setMode] = useState("answer");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4o");
  const [temperature, setTemperature] = useState(0.0);
  const [instructions, setInstructions] = useState("");

  // Query & results
  const [query, setQuery] = useState("");
  const [phase, setPhase] = useState("idle"); // idle | retrieving | generating | done
  const [displayedAnswer, setDisplayedAnswer] = useState("");
  const [highlightedChunk, setHighlightedChunk] = useState(null);
  const [copied, setCopied] = useState(false);

  const chunkRefs = useRef({});
  const streamRef = useRef(null);
  const answerPanelRef = useRef(null);

  const modelOptions = {
    openai: [
      { value: "gpt-4o", label: "GPT-4o" },
      { value: "gpt-4o-mini", label: "GPT-4o Mini" },
      { value: "gpt-4.1", label: "GPT-4.1" },
    ],
    anthropic: [
      { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
      { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
    ],
    ollama: [
      { value: "llama3", label: "Llama 3" },
      { value: "mistral", label: "Mistral" },
    ],
  };

  const handleProviderChange = (p) => {
    setProvider(p);
    setModel(modelOptions[p][0].value);
  };

  const simulateStream = () => {
    if (!query.trim()) return;
    setPhase("retrieving");
    setDisplayedAnswer("");
    setHighlightedChunk(null);
    setCopied(false);

    setTimeout(() => {
      if (mode === "retrieval") {
        setPhase("done");
        return;
      }
      setPhase("generating");
      let i = 0;
      const tokens = MOCK_ANSWER_TOKENS.split(/(?<=\s)/);
      streamRef.current = setInterval(() => {
        if (i < tokens.length) {
          setDisplayedAnswer((prev) => prev + tokens[i]);
          i++;
        } else {
          clearInterval(streamRef.current);
          setPhase("done");
        }
      }, 25);
    }, 800);
  };

  const handleStop = () => {
    if (streamRef.current) clearInterval(streamRef.current);
    setPhase("done");
  };

  const handleCitationClick = (num) => {
    setHighlightedChunk(num === highlightedChunk ? null : num);
    if (chunkRefs.current[num]) {
      chunkRefs.current[num].scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(displayedAnswer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      simulateStream();
    }
  };

  // ── Sidebar ──
  const Sidebar = () => (
    <div style={{
      width: 220, background: "#fafafa", borderRight: "1px solid #e4e4e7",
      display: "flex", flexDirection: "column", flexShrink: 0, height: "100%",
    }}>
      <div style={{ padding: "16px 16px 12px", borderBottom: "1px solid #e4e4e7" }}>
        <span style={{ fontWeight: 700, fontSize: 15, color: "#09090b" }}>RAG Admin</span>
      </div>
      <div style={{ padding: "10px 12px", borderBottom: "1px solid #e4e4e7" }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 8, padding: "6px 8px",
          background: "#f4f4f5", borderRadius: 6, fontSize: 13, color: "#09090b",
        }}>
          <FolderIcon size={14} />
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>Acorn IREIT Financi…</span>
          <ChevronIcon size={12} />
        </div>
      </div>
      <nav style={{ padding: "8px 12px", flex: 1 }}>
        {[
          { icon: <HomeIcon size={16} />, label: "Home" },
          { icon: <FolderIcon size={16} />, label: "Projects" },
          { icon: <FileTextIcon size={16} />, label: "Documents" },
          { icon: <DatabaseIcon size={16} />, label: "Index", active: true },
          { icon: <BarChartIcon size={16} />, label: "Evaluation" },
          { icon: <SettingsIcon size={16} />, label: "Settings" },
        ].map((item) => (
          <div key={item.label} style={{
            display: "flex", alignItems: "center", gap: 10, padding: "7px 8px",
            borderRadius: 6, fontSize: 13, color: item.active ? "#09090b" : "#71717a",
            fontWeight: item.active ? 500 : 400,
            background: item.active ? "#f4f4f5" : "transparent",
            cursor: "pointer", marginBottom: 1,
          }}>
            {item.icon}
            {item.label}
          </div>
        ))}
      </nav>
      <div style={{ padding: "12px 16px", borderTop: "1px solid #e4e4e7", fontSize: 12, color: "#71717a" }}>
        asa.nyaga@gmail.com
      </div>
    </div>
  );

  // ── Param label ──
  const ParamLabel = ({ children, tooltip }) => (
    <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13, fontWeight: 500, color: "#09090b", marginBottom: 6 }}>
      {children}
      {tooltip && (
        <Tooltip text={tooltip}>
          <span style={{ color: "#a1a1aa", cursor: "help", display: "inline-flex" }}><InfoIcon size={13} /></span>
        </Tooltip>
      )}
    </div>
  );

  // ── Section divider ──
  const SectionHeader = ({ icon, children }) => (
    <div style={{
      display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 600,
      textTransform: "uppercase", letterSpacing: "0.05em", color: "#71717a",
      marginTop: 20, marginBottom: 12, paddingBottom: 6, borderBottom: "1px solid #f4f4f5",
    }}>
      {icon}
      {children}
    </div>
  );

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif', color: "#09090b", background: "white" }}>
      <Sidebar />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "12px 24px", borderBottom: "1px solid #e4e4e7", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#71717a" }}>
          <FileTextIcon size={14} />
          <span>Index Details</span>
        </div>

        {/* Breadcrumb + status */}
        <div style={{ padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
            <span style={{ color: "#71717a", cursor: "pointer" }}>← Indexes</span>
            <span style={{ color: "#d4d4d8" }}>/</span>
            <span style={{ fontWeight: 500 }}>Acorn REIT Documents</span>
          </div>
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12,
            background: "#f0fdf4", color: "#16a34a", padding: "3px 10px", borderRadius: 20, fontWeight: 500,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#16a34a" }} />
            Ready
          </span>
        </div>

        {/* Index info card */}
        <div style={{ margin: "0 24px", padding: "16px 20px", border: "1px solid #e4e4e7", borderRadius: 8 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <h1 style={{ fontSize: 20, fontWeight: 600, margin: 0 }}>Acorn REIT Documents</h1>
            <button style={{
              display: "flex", alignItems: "center", gap: 6, padding: "6px 12px",
              border: "1px solid #e4e4e7", borderRadius: 6, background: "white",
              fontSize: 13, cursor: "pointer", color: "#71717a",
            }}>
              <SettingsIcon size={14} /> Settings
            </button>
          </div>
          <div style={{ display: "flex", gap: 24, fontSize: 13, color: "#71717a" }}>
            <span><strong style={{ color: "#09090b" }}>1</strong> DOCUMENTS</span>
            <span><strong style={{ color: "#09090b" }}>842</strong> CHUNKS</span>
            <span><strong style={{ color: "#09090b" }}>99</strong> AVG TOKENS</span>
            <span>text-embedding-3-small MODEL</span>
            <span><strong style={{ color: "#09090b" }}>1,536</strong> DIMENSIONS</span>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 0, padding: "0 24px", marginTop: 16, borderBottom: "1px solid #e4e4e7" }}>
          {[
            { id: "content", label: "Content", icon: <FileTextIcon size={14} /> },
            { id: "playground", label: "Playground", icon: <PlayIcon size={14} /> },
          ].map((tab) => (
            <button key={tab.id} style={{
              display: "flex", alignItems: "center", gap: 6, padding: "8px 16px",
              border: "none", background: "none", cursor: "pointer", fontSize: 13,
              color: tab.id === "playground" ? "#09090b" : "#71717a",
              fontWeight: tab.id === "playground" ? 500 : 400,
              borderBottom: tab.id === "playground" ? "2px solid #18181b" : "2px solid transparent",
              marginBottom: -1,
            }}>
              {tab.icon} {tab.label}
            </button>
          ))}
        </div>

        {/* Playground content */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden", padding: 24, gap: 24 }}>
          {/* Left panel: Parameters */}
          <div style={{ width: 260, flexShrink: 0, overflowY: "auto", paddingRight: 8 }}>
            {/* Mode toggle */}
            <SectionHeader icon={<SlidersIcon size={12} />}>Mode</SectionHeader>
            <ToggleGroup
              options={[
                { value: "retrieval", label: "Retrieval" },
                { value: "answer", label: "Answer" },
              ]}
              value={mode}
              onChange={setMode}
            />

            {/* Retrieval params */}
            <SectionHeader icon={<SearchIcon size={12} />}>Retrieval</SectionHeader>

            <ParamLabel tooltip="Vector similarity, keyword matching, or combined">Search Type</ParamLabel>
            <ToggleGroup
              options={[
                { value: "semantic", label: "Semantic" },
                { value: "keyword", label: "Keyword" },
                { value: "hybrid", label: "Hybrid" },
              ]}
              value={searchType}
              onChange={setSearchType}
            />

            <div style={{ marginTop: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <ParamLabel tooltip="Number of chunks to retrieve">Top-K</ParamLabel>
                <span style={{ fontSize: 13, fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>{topK}</span>
              </div>
              <Slider min={1} max={20} step={1} value={topK} onChange={setTopK} leftLabel="1" rightLabel="20" />
            </div>

            <div style={{ marginTop: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <ParamLabel tooltip="Minimum similarity score">Threshold</ParamLabel>
                <span style={{ fontSize: 13, fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>{threshold.toFixed(1)}</span>
              </div>
              <Slider min={0} max={1} step={0.1} value={threshold} onChange={setThreshold} leftLabel="0.0 all" rightLabel="1.0 strict" />
            </div>

            {/* LLM params (only in answer mode) */}
            {mode === "answer" && (
              <>
                <SectionHeader icon={<SparklesIcon size={12} />}>Generation</SectionHeader>

                <ParamLabel>Provider</ParamLabel>
                <Select
                  value={provider}
                  onChange={handleProviderChange}
                  options={[
                    { value: "openai", label: "OpenAI" },
                    { value: "anthropic", label: "Anthropic" },
                    { value: "ollama", label: "Ollama" },
                  ]}
                />

                <div style={{ marginTop: 12 }}>
                  <ParamLabel>Model</ParamLabel>
                  <Select value={model} onChange={setModel} options={modelOptions[provider]} />
                </div>

                <div style={{ marginTop: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <ParamLabel tooltip="Higher values produce more creative responses">Temperature</ParamLabel>
                    <span style={{ fontSize: 13, fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>{temperature.toFixed(1)}</span>
                  </div>
                  <Slider min={0} max={1} step={0.1} value={temperature} onChange={setTemperature} leftLabel="0.0 precise" rightLabel="1.0 creative" />
                </div>

                <div style={{ marginTop: 12 }}>
                  <ParamLabel tooltip="Optional instructions that shape the answer style">Instructions</ParamLabel>
                  <textarea
                    value={instructions}
                    onChange={(e) => setInstructions(e.target.value)}
                    placeholder="e.g., Answer as a financial analyst. Be concise."
                    style={{
                      width: "100%", minHeight: 64, padding: "8px 10px", border: "1px solid #e4e4e7",
                      borderRadius: 6, fontSize: 13, resize: "vertical", fontFamily: "inherit",
                      outline: "none", color: "#09090b", boxSizing: "border-box",
                    }}
                    onFocus={(e) => e.target.style.borderColor = "#a1a1aa"}
                    onBlur={(e) => e.target.style.borderColor = "#e4e4e7"}
                  />
                </div>
              </>
            )}
          </div>

          {/* Right panel: Query + Results */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
            {/* Query input */}
            <div style={{ display: "flex", gap: 8, marginBottom: 16, flexShrink: 0 }}>
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="What would your users ask? Try a natural language query..."
                rows={2}
                style={{
                  flex: 1, padding: "10px 14px", border: "1px solid #e4e4e7", borderRadius: 8,
                  fontSize: 14, fontFamily: "inherit", resize: "none", outline: "none",
                  color: "#09090b", lineHeight: 1.5,
                }}
                onFocus={(e) => e.target.style.borderColor = "#18181b"}
                onBlur={(e) => e.target.style.borderColor = "#e4e4e7"}
              />
              <button onClick={phase === "generating" ? handleStop : simulateStream}
                style={{
                  display: "flex", alignItems: "center", gap: 6, padding: "0 16px",
                  background: phase === "generating" ? "#fafafa" : "#18181b",
                  color: phase === "generating" ? "#09090b" : "white",
                  border: phase === "generating" ? "1px solid #e4e4e7" : "none",
                  borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: "pointer",
                  whiteSpace: "nowrap", flexShrink: 0,
                }}>
                {phase === "generating" ? <><StopIcon size={14} /> Stop</> : <><SearchIcon size={14} /> Search</>}
              </button>
            </div>

            {/* Results area */}
            <div style={{ flex: 1, overflowY: "auto", minHeight: 0 }} ref={answerPanelRef}>
              {phase === "idle" && (
                <div style={{
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                  height: "100%", color: "#a1a1aa", textAlign: "center", gap: 8,
                }}>
                  <div style={{ width: 48, height: 48, borderRadius: "50%", background: "#f4f4f5", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    {mode === "answer" ? <SparklesIcon size={22} /> : <SearchIcon size={22} />}
                  </div>
                  <p style={{ fontSize: 15, fontWeight: 500, color: "#71717a", margin: 0 }}>
                    {mode === "answer" ? "Run a query to test the full RAG pipeline" : "Run a query to test retrieval"}
                  </p>
                  <p style={{ fontSize: 13, maxWidth: 340, margin: 0 }}>
                    {mode === "answer"
                      ? "Type a question to see retrieved chunks and a generated answer. Adjust parameters on the left to compare."
                      : "Type a question your users might ask and see which chunks come back. Adjust parameters on the left to compare."}
                  </p>
                </div>
              )}

              {phase === "retrieving" && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 16, color: "#71717a", fontSize: 13 }}>
                  <div style={{
                    width: 16, height: 16, border: "2px solid #e4e4e7", borderTopColor: "#18181b",
                    borderRadius: "50%", animation: "spin 0.8s linear infinite",
                  }} />
                  Retrieving chunks…
                  <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
                </div>
              )}

              {(phase === "generating" || phase === "done") && (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  {/* Answer panel (only in answer mode) */}
                  {mode === "answer" && (
                    <div style={{
                      border: "1px solid #e4e4e7", borderRadius: 8, overflow: "hidden",
                    }}>
                      <div style={{
                        display: "flex", alignItems: "center", justifyContent: "space-between",
                        padding: "8px 14px", background: "#fafafa", borderBottom: "1px solid #e4e4e7",
                      }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600, color: "#71717a", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                          <SparklesIcon size={13} />
                          Answer
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                          {phase === "generating" && (
                            <span style={{
                              fontSize: 11, color: "#71717a", display: "flex", alignItems: "center", gap: 4,
                            }}>
                              <div style={{
                                width: 6, height: 6, borderRadius: "50%", background: "#22c55e",
                                animation: "pulse 1.5s ease-in-out infinite",
                              }} />
                              Generating…
                              <style>{`@keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: 0.4 } }`}</style>
                            </span>
                          )}
                          {phase === "done" && displayedAnswer && (
                            <button onClick={handleCopy} style={{
                              display: "flex", alignItems: "center", gap: 4, padding: "3px 8px",
                              border: "1px solid #e4e4e7", borderRadius: 4, background: "white",
                              fontSize: 11, color: "#71717a", cursor: "pointer",
                            }}>
                              {copied ? <><CheckIcon size={12} /> Copied</> : <><CopyIcon size={12} /> Copy</>}
                            </button>
                          )}
                        </div>
                      </div>
                      <div style={{ padding: "14px 16px", fontSize: 14, lineHeight: 1.7, whiteSpace: "pre-wrap", minHeight: 60 }}>
                        {displayedAnswer
                          ? renderAnswerWithCitations(displayedAnswer, highlightedChunk, handleCitationClick)
                          : <span style={{ color: "#a1a1aa" }}>Waiting for response…</span>}
                      </div>
                      {/* Metrics bar */}
                      {phase === "done" && displayedAnswer && (
                        <div style={{
                          display: "flex", alignItems: "center", gap: 16, padding: "8px 16px",
                          borderTop: "1px solid #f4f4f5", background: "#fafafa", fontSize: 12, color: "#71717a",
                        }}>
                          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                            <ClockIcon size={13} /> 1.24s
                          </span>
                          <span>342 in → 189 out tokens</span>
                          <span style={{ marginLeft: "auto", fontSize: 11, color: "#a1a1aa" }}>
                            {modelOptions[provider].find(m => m.value === model)?.label} via {provider}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Chunks panel */}
                  <div>
                    <div style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      marginBottom: 10,
                    }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: "#71717a", textTransform: "uppercase", letterSpacing: "0.05em", display: "flex", alignItems: "center", gap: 6 }}>
                        <SearchIcon size={13} />
                        Retrieved Chunks
                        <span style={{ fontWeight: 400, textTransform: "none", letterSpacing: "normal" }}>({MOCK_CHUNKS.length} results)</span>
                      </span>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {MOCK_CHUNKS.map((chunk) => (
                        <div key={chunk.id}
                          ref={(el) => (chunkRefs.current[chunk.id] = el)}
                          style={{
                            border: highlightedChunk === chunk.id ? "1px solid #18181b" : "1px solid #e4e4e7",
                            borderRadius: 8, padding: "12px 14px", transition: "all 0.2s ease",
                            background: highlightedChunk === chunk.id ? "#fafafa" : "white",
                          }}>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <span style={{
                                display: "inline-flex", alignItems: "center", justifyContent: "center",
                                width: 22, height: 22, borderRadius: 4, fontSize: 12, fontWeight: 600,
                                background: highlightedChunk === chunk.id ? "#18181b" : "#f4f4f5",
                                color: highlightedChunk === chunk.id ? "white" : "#09090b",
                              }}>
                                {chunk.id}
                              </span>
                              <ScoreBar score={chunk.score} />
                            </div>
                            <span style={{ fontSize: 12, color: "#a1a1aa" }}>Page {chunk.page}</span>
                          </div>
                          <p style={{ fontSize: 13, lineHeight: 1.6, color: "#3f3f46", margin: 0 }}>
                            {chunk.content}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
