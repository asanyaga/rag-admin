import { useState, useRef } from "react";

// ─── Mock Data ───────────────────────────────────────────────────────────────

const mockIndex = {
  name: "Acorn REIT Documents",
  status: "ready",
  description: "Information Memorandum for Acorn Capital Partners LLP — Restricted Public Offer of Acorn Student Accommodation I-REIT",
  config: {
    chunkingStrategy: "Fixed Size",
    chunkSize: 512,
    chunkOverlap: 50,
    embeddingProvider: "OpenAI",
    embeddingModel: "text-embedding-3-small",
    dimensions: 1536,
  },
  stats: { documents: 1, chunks: 842, avgTokens: 95 },
};

const mockDocuments = [
  { id: 1, name: "ACPL-IM.pdf", status: "processed", chunks: 842, pages: 87, uploadedAt: "2025-01-15", size: "4.2 MB" },
];

const mockChunks = Array.from({ length: 20 }, (_, i) => ({
  id: i,
  content: [
    "[Page 1] Information Memorandum for Acorn Capital Partners LLP Issued in relation to the Restricted Public Offer of Acorn Student Accommodation I-REIT...",
    "Partners Limited Liability Partnership and is to be reviewed by those who are interested in investing in the Acorn Income Real Estate Investment Trust...",
    "[Page 2] Information Memorandum – ACPL Page | i IMPORTANT NOTICE THIS DOCUMENT IS IMPORTANT FOR CONSIDERING WHAT...",
    "subscription of the units in the Acorn Income Real Estate Investment Trust (the \"Units\"). The Acorn Income Real Estate Investment Trust...",
    "Investment Trusts) (Collective Investment Schemes) Regulations, 2013 (the \"Regulations\") This Offering Memorandum is issued to pro...",
    "Your investment in Units and as a security holder in the Acorn I-REIT is as an equity investor (\"Security Holder\"). Distributions of incom...",
    "rights to distributions and the Issuer's rights to the assets of the Acorn I-REIT will rank after the liabilities to creditors and pari passu t...",
    "admitted into the regulatory sandbox, a capital markets aggregator, regulated by the CMA for a period of one (1) year to enable retail...",
    "addition, the Authority has approved this Information Memorandum. The approval by the Authority is not a recommendation nor a st...",
    "consistent with this Information Memorandum or any other information supplied in connection with the Issuer, the REIT Manager or t...",
  ][i % 10],
  tokens: 80 + Math.floor(Math.random() * 40),
  chars: 400 + Math.floor(Math.random() * 60),
  document: "ACPL-IM.pdf",
  page: Math.floor(i / 10) + 1,
}));

const mockPlaygroundResults = [
  { rank: 1, score: 0.94, content: "Your investment in Units and as a security holder in the Acorn I-REIT is as an equity investor (\"Security Holder\"). Distributions of income will be made to Security Holders in proportion to the number of Units held. The I-REIT targets a distribution yield of 7-8% per annum on invested capital.", tokens: 103, document: "ACPL-IM.pdf", page: 5, chunkId: 5 },
  { rank: 2, score: 0.89, content: "subscription of the units in the Acorn Income Real Estate Investment Trust (the \"Units\"). The Acorn Income Real Estate Investment Trust is established as a collective investment scheme under the Capital Markets (Collective Investment Schemes) Regulations.", tokens: 100, document: "ACPL-IM.pdf", page: 3, chunkId: 3 },
  { rank: 3, score: 0.82, content: "rights to distributions and the Issuer's rights to the assets of the Acorn I-REIT will rank after the liabilities to creditors and pari passu with the rights of other Security Holders. Investors should be aware of the risk factors detailed in Section 8.", tokens: 96, document: "ACPL-IM.pdf", page: 6, chunkId: 6 },
  { rank: 4, score: 0.71, content: "Investment Trusts) (Collective Investment Schemes) Regulations, 2013 (the \"Regulations\") This Offering Memorandum is issued to provide information to prospective investors about the structure, objectives, and risks of investing in the I-REIT.", tokens: 105, document: "ACPL-IM.pdf", page: 4, chunkId: 4 },
  { rank: 5, score: 0.63, content: "admitted into the regulatory sandbox, a capital markets aggregator, regulated by the CMA for a period of one (1) year to enable retail and institutional investors to participate in income-generating real estate investments.", tokens: 92, document: "ACPL-IM.pdf", page: 7, chunkId: 7 },
];

// ─── Icons (Lucide-style) ────────────────────────────────────────────────────

const I = {
  ArrowLeft: (p) => <svg {...p} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5"/><polyline points="12 19 5 12 12 5"/></svg>,
  FileText: (p) => <svg {...p} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/></svg>,
  Play: (p) => <svg {...p} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
  Search: (p) => <svg {...p} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>,
  Settings: (p) => <svg {...p} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  Upload: (p) => <svg {...p} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>,
  Trash2: (p) => <svg {...p} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>,
  ChevronDown: (p) => <svg {...p} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>,
  ThumbsUp: (p) => <svg {...p} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>,
  ThumbsDown: (p) => <svg {...p} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>,
  Pencil: (p) => <svg {...p} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>,
  Check: (p) => <svg {...p} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>,
  Info: (p) => <svg {...p} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>,
  Clock: (p) => <svg {...p} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
  Loader2: (p) => <svg {...p} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>,
  SlidersHorizontal: (p) => <svg {...p} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="21" y1="4" x2="14" y2="4"/><line x1="10" y1="4" x2="3" y2="4"/><line x1="21" y1="12" x2="12" y2="12"/><line x1="8" y1="12" x2="3" y2="12"/><line x1="21" y1="20" x2="16" y2="20"/><line x1="12" y1="20" x2="3" y2="20"/><line x1="14" y1="1" x2="14" y2="7"/><line x1="8" y1="9" x2="8" y2="15"/><line x1="16" y1="17" x2="16" y2="23"/></svg>,
  X: (p) => <svg {...p} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

const cn = (...classes) => classes.filter(Boolean).join(" ");

function Tooltip({ text, children }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-flex items-center"
      onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 rounded-md bg-zinc-900 px-3 py-1.5 text-xs text-zinc-100 shadow-md" style={{ whiteSpace: "nowrap" }}>
          {text}
        </span>
      )}
    </span>
  );
}

function Badge({ children, variant = "default" }) {
  const v = {
    default: "bg-zinc-100 text-zinc-700 border-zinc-200",
    success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  };
  return <span className={cn("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium", v[variant])}>{children}</span>;
}

function ScoreBar({ score }) {
  const pct = score * 100;
  const bar = score >= 0.85 ? "bg-emerald-500" : score >= 0.7 ? "bg-yellow-500" : score >= 0.5 ? "bg-orange-500" : "bg-red-500";
  const txt = score >= 0.85 ? "text-emerald-600" : score >= 0.7 ? "text-yellow-600" : score >= 0.5 ? "text-orange-600" : "text-red-600";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all duration-500", bar)} style={{ width: `${pct}%` }} />
      </div>
      <span className={cn("text-xs font-mono font-semibold", txt)}>{score.toFixed(2)}</span>
    </div>
  );
}

// ─── Main ────────────────────────────────────────────────────────────────────

export default function IndexDetailsPage() {
  const [activeSection, setActiveSection] = useState("content");
  const [expandedDoc, setExpandedDoc] = useState(null);
  const [selectedChunk, setSelectedChunk] = useState(null);
  const [showConfig, setShowConfig] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [indexName, setIndexName] = useState(mockIndex.name);
  const [editingDesc, setEditingDesc] = useState(false);
  const [indexDesc, setIndexDesc] = useState(mockIndex.description);

  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState("hybrid");
  const [topK, setTopK] = useState(5);
  const [threshold, setThreshold] = useState(0.0);
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [queryHistory, setQueryHistory] = useState([]);
  const [expandedResult, setExpandedResult] = useState(null);
  const [votes, setVotes] = useState({});
  const queryRef = useRef(null);

  const runSearch = () => {
    if (!query.trim()) return;
    setIsSearching(true);
    setExpandedResult(null);
    setVotes({});
    setTimeout(() => {
      setResults(mockPlaygroundResults.slice(0, topK).filter(r => r.score >= threshold));
      setIsSearching(false);
      if (!queryHistory.includes(query.trim())) {
        setQueryHistory(prev => [query.trim(), ...prev].slice(0, 8));
      }
    }, 800);
  };

  const tabs = [
    { id: "content", label: "Content", icon: I.FileText },
    { id: "playground", label: "Playground", icon: I.Play },
  ];

  return (
    <div className="min-h-screen bg-white text-zinc-900">

      {/* ══════ Breadcrumb ══════ */}
      <div className="border-b border-zinc-200 px-6 py-3 flex items-center gap-2 sticky top-0 z-50 bg-white">
        <button className="p-1 rounded-md hover:bg-zinc-100 text-zinc-400 hover:text-zinc-600 transition-colors">
          <I.ArrowLeft />
        </button>
        <span className="text-sm text-zinc-400">Indexes</span>
        <span className="text-zinc-300">/</span>
        <span className="text-sm font-medium text-zinc-700">{indexName}</span>
        <div className="ml-auto">
          <Badge variant="success">● Ready</Badge>
        </div>
      </div>

      {/* ══════ Index Header ══════ */}
      <div className="mx-6 mt-5 p-5 rounded-lg border border-zinc-200">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            {editingName ? (
              <div className="flex items-center gap-2">
                <input value={indexName} onChange={e => setIndexName(e.target.value)}
                  onBlur={() => setEditingName(false)}
                  onKeyDown={e => e.key === "Enter" && setEditingName(false)}
                  autoFocus
                  className="text-xl font-semibold bg-zinc-50 border border-zinc-300 rounded-md px-2 py-1 outline-none focus:ring-2 focus:ring-zinc-900 focus:border-transparent w-96" />
                <button onClick={() => setEditingName(false)}
                  className="p-1.5 rounded-md bg-zinc-900 text-white hover:bg-zinc-800 transition-colors">
                  <I.Check />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 group">
                <h1 className="text-xl font-semibold">{indexName}</h1>
                <button onClick={() => setEditingName(true)}
                  className="p-1 rounded-md text-zinc-300 hover:text-zinc-500 opacity-0 group-hover:opacity-100 transition-all">
                  <I.Pencil />
                </button>
              </div>
            )}
            {editingDesc ? (
              <textarea value={indexDesc} onChange={e => setIndexDesc(e.target.value)}
                onBlur={() => setEditingDesc(false)} autoFocus rows={2}
                className="mt-1.5 text-sm text-zinc-500 bg-zinc-50 border border-zinc-300 rounded-md px-2 py-1.5 outline-none focus:ring-2 focus:ring-zinc-900 focus:border-transparent w-full resize-vertical leading-relaxed" />
            ) : (
              <p onClick={() => setEditingDesc(true)}
                className="mt-1.5 text-sm text-zinc-500 cursor-pointer hover:text-zinc-600 transition-colors max-w-xl leading-relaxed">
                {indexDesc || <span className="italic text-zinc-400">Add a description...</span>}
              </p>
            )}
          </div>
          <button onClick={() => setShowConfig(!showConfig)}
            className={cn("flex items-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors",
              showConfig ? "bg-zinc-100 border-zinc-300 text-zinc-700" : "border-zinc-200 text-zinc-500 hover:bg-zinc-50")}>
            <I.Settings /> Settings
          </button>
        </div>

        <div className="flex items-center gap-6 flex-wrap">
          {[
            { label: "Documents", value: mockIndex.stats.documents },
            { label: "Chunks", value: mockIndex.stats.chunks.toLocaleString() },
            { label: "Avg Tokens", value: mockIndex.stats.avgTokens },
            { label: "Model", value: mockIndex.config.embeddingModel },
            { label: "Dimensions", value: mockIndex.config.dimensions.toLocaleString() },
          ].map(s => (
            <div key={s.label} className="flex items-baseline gap-1.5">
              <span className="text-sm font-semibold font-mono text-zinc-800">{s.value}</span>
              <span className="text-xs text-zinc-400 uppercase tracking-wide">{s.label}</span>
            </div>
          ))}
        </div>

        {showConfig && (
          <div className="mt-4 pt-4 border-t border-zinc-200 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
            {Object.entries(mockIndex.config).map(([key, value]) => (
              <div key={key}>
                <div className="text-[10px] text-zinc-400 uppercase tracking-wider mb-1">{key.replace(/([A-Z])/g, " $1").trim()}</div>
                <div className="text-sm font-mono text-zinc-700">{value}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ══════ Tabs ══════ */}
      <div className="mx-6 mt-5 flex gap-1 border-b border-zinc-200">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveSection(tab.id)}
            className={cn(
              "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors",
              activeSection === tab.id ? "border-zinc-900 text-zinc-900" : "border-transparent text-zinc-400 hover:text-zinc-600"
            )}>
            <tab.icon /> {tab.label}
          </button>
        ))}
      </div>

      {/* ══════ CONTENT ══════ */}
      {activeSection === "content" && (
        <div className="flex mx-6 mt-4 mb-6 gap-4">
          <div className="flex-1 flex flex-col min-w-0">
            {/* Documents */}
            <div className="rounded-t-lg border border-zinc-200 border-b-0">
              <div className="px-4 py-3 flex items-center justify-between border-b border-zinc-200">
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Documents ({mockDocuments.length})</h3>
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-zinc-200 text-xs font-medium text-zinc-600 hover:bg-zinc-50 transition-colors">
                  <I.Upload /> Add Document
                </button>
              </div>
              {mockDocuments.map(doc => (
                <div key={doc.id}>
                  <div onClick={() => setExpandedDoc(expandedDoc === doc.id ? null : doc.id)}
                    className={cn("px-4 py-3 flex items-center gap-3 cursor-pointer transition-colors",
                      expandedDoc === doc.id ? "bg-zinc-50" : "hover:bg-zinc-50")}>
                    <span className={cn("transition-transform text-zinc-400", expandedDoc === doc.id ? "rotate-0" : "-rotate-90")}>
                      <I.ChevronDown />
                    </span>
                    <I.FileText className="text-zinc-400" />
                    <span className="text-sm font-medium flex-1">{doc.name}</span>
                    <span className="text-xs text-zinc-400 font-mono">{doc.chunks} chunks</span>
                    <span className="text-xs text-zinc-400">{doc.size}</span>
                    <span className="text-xs text-zinc-400">{doc.uploadedAt}</span>
                    <button className="p-1 rounded text-zinc-300 hover:text-red-500 transition-colors" onClick={e => e.stopPropagation()}>
                      <I.Trash2 />
                    </button>
                  </div>
                  {expandedDoc === doc.id && (
                    <div className="px-4 py-2 pl-14 text-xs text-zinc-400 flex gap-5 bg-zinc-50 border-t border-zinc-100">
                      <span>Pages: {doc.pages}</span>
                      <span>Status: <span className="text-emerald-600 font-medium">{doc.status}</span></span>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Chunks */}
            <div className="rounded-b-lg border border-zinc-200 flex-1 flex flex-col overflow-hidden">
              <div className="px-4 py-3 flex items-center justify-between border-b border-zinc-200">
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Chunks ({mockIndex.stats.chunks})</h3>
                <div className="flex items-center gap-1.5 bg-zinc-50 border border-zinc-200 rounded-md px-2.5 py-1.5">
                  <I.Search className="text-zinc-400" />
                  <input placeholder="Search chunks..." className="bg-transparent border-none outline-none text-sm text-zinc-700 placeholder:text-zinc-400 w-44" />
                </div>
              </div>
              <div className="overflow-auto flex-1" style={{ maxHeight: 420 }}>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="sticky top-0 bg-zinc-50 z-10">
                      {["#", "Content Preview", "Tokens", "Chars", "Source"].map(h => (
                        <th key={h} className="text-left px-4 py-2 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider border-b border-zinc-200">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {mockChunks.map(chunk => (
                      <tr key={chunk.id}
                        onClick={() => setSelectedChunk(selectedChunk?.id === chunk.id ? null : chunk)}
                        className={cn("cursor-pointer transition-colors border-b border-zinc-100 last:border-b-0",
                          selectedChunk?.id === chunk.id ? "bg-zinc-100" : "hover:bg-zinc-50")}>
                        <td className="px-4 py-2.5 text-zinc-400 font-mono text-xs w-10">{chunk.id}</td>
                        <td className="px-4 py-2.5 text-zinc-600 max-w-md truncate">{chunk.content}</td>
                        <td className="px-4 py-2.5 text-zinc-400 font-mono text-xs w-16">{chunk.tokens}</td>
                        <td className="px-4 py-2.5 text-zinc-400 font-mono text-xs w-16">{chunk.chars}</td>
                        <td className="px-4 py-2.5 text-zinc-400 text-xs w-24">{chunk.document}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Chunk detail */}
          {selectedChunk && (
            <div className="w-80 rounded-lg border border-zinc-200 p-5 self-start sticky top-20">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold">Chunk #{selectedChunk.id}</h3>
                <button onClick={() => setSelectedChunk(null)} className="p-1 rounded-md text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 transition-colors">
                  <I.X />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-4">
                {[
                  { l: "Tokens", v: selectedChunk.tokens },
                  { l: "Chars", v: selectedChunk.chars },
                  { l: "Page", v: selectedChunk.page },
                  { l: "Source", v: selectedChunk.document },
                ].map(m => (
                  <div key={m.l}>
                    <div className="text-[10px] text-zinc-400 uppercase tracking-wider mb-0.5">{m.l}</div>
                    <div className="text-sm font-mono text-zinc-700">{m.v}</div>
                  </div>
                ))}
              </div>
              <div className="text-[10px] text-zinc-400 uppercase tracking-wider mb-1.5">Full Content</div>
              <div className="bg-zinc-50 rounded-md p-3 text-sm text-zinc-600 leading-relaxed border border-zinc-100 max-h-64 overflow-auto">
                {selectedChunk.content}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════ PLAYGROUND ══════ */}
      {activeSection === "playground" && (
        <div className="flex mx-6 mt-4 mb-6 gap-4">

          {/* Left sidebar: Parameters + History */}
          <div className="w-64 flex flex-col gap-3 flex-shrink-0">

            <div className="rounded-lg border border-zinc-200 p-4">
              <div className="flex items-center gap-1.5 mb-4">
                <I.SlidersHorizontal className="text-zinc-400" />
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Parameters</h3>
              </div>

              {/* Search Type */}
              <div className="mb-4">
                <div className="flex items-center gap-1 mb-2">
                  <span className="text-xs text-zinc-600 font-medium">Search Type</span>
                  <Tooltip text="Semantic = conceptual similarity. Keyword = exact match. Hybrid = both.">
                    <I.Info className="text-zinc-300 cursor-help" />
                  </Tooltip>
                </div>
                <div className="flex gap-0.5 bg-zinc-100 rounded-md p-0.5">
                  {["semantic", "keyword", "hybrid"].map(type => (
                    <button key={type} onClick={() => setSearchType(type)}
                      className={cn("flex-1 py-1.5 rounded text-xs font-medium capitalize transition-all",
                        searchType === type ? "bg-white text-zinc-900 shadow-sm" : "text-zinc-400 hover:text-zinc-600")}>
                      {type}
                    </button>
                  ))}
                </div>
              </div>

              {/* Top K */}
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-zinc-600 font-medium">Top-K</span>
                    <Tooltip text="Number of chunks to return.">
                      <I.Info className="text-zinc-300 cursor-help" />
                    </Tooltip>
                  </div>
                  <span className="text-xs font-mono font-semibold text-zinc-800 bg-zinc-100 px-1.5 py-0.5 rounded">{topK}</span>
                </div>
                <input type="range" min={1} max={20} value={topK} onChange={e => setTopK(Number(e.target.value))}
                  className="w-full accent-zinc-900 h-1.5 cursor-pointer" />
                <div className="flex justify-between text-[10px] text-zinc-400 mt-0.5"><span>1</span><span>20</span></div>
              </div>

              {/* Threshold */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-zinc-600 font-medium">Threshold</span>
                    <Tooltip text="Minimum similarity score. Higher = stricter.">
                      <I.Info className="text-zinc-300 cursor-help" />
                    </Tooltip>
                  </div>
                  <span className="text-xs font-mono font-semibold text-zinc-800 bg-zinc-100 px-1.5 py-0.5 rounded">{threshold.toFixed(1)}</span>
                </div>
                <input type="range" min={0} max={1} step={0.1} value={threshold} onChange={e => setThreshold(Number(e.target.value))}
                  className="w-full accent-zinc-900 h-1.5 cursor-pointer" />
                <div className="flex justify-between text-[10px] text-zinc-400 mt-0.5"><span>0.0 all</span><span>1.0 strict</span></div>
              </div>
            </div>

            {/* History */}
            {queryHistory.length > 0 && (
              <div className="rounded-lg border border-zinc-200 p-4">
                <div className="flex items-center gap-1.5 mb-3">
                  <I.Clock className="text-zinc-400" />
                  <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">History</h3>
                </div>
                <div className="flex flex-col gap-0.5">
                  {queryHistory.map((q, i) => (
                    <button key={i} onClick={() => { setQuery(q); queryRef.current?.focus(); }}
                      className="text-left px-2 py-1.5 rounded-md text-xs text-zinc-500 hover:bg-zinc-50 hover:text-zinc-700 transition-colors truncate">
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right main: Query bar on top → Results below */}
          <div className="flex-1 min-w-0 flex flex-col gap-3">

            {/* Query bar */}
            <div className="rounded-lg border border-zinc-200 p-4">
              <div className="flex gap-3">
                <textarea
                  ref={queryRef}
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runSearch(); } }}
                  placeholder="What would your users ask? Try a natural language query..."
                  rows={2}
                  className="flex-1 bg-zinc-50 border border-zinc-200 rounded-md px-3 py-2.5 text-sm text-zinc-800 placeholder:text-zinc-400 outline-none focus:ring-2 focus:ring-zinc-900 focus:border-transparent resize-none leading-relaxed"
                />
                <button onClick={runSearch} disabled={!query.trim() || isSearching}
                  className={cn("px-5 rounded-md text-sm font-medium flex items-center gap-2 transition-all self-stretch",
                    query.trim() && !isSearching ? "bg-zinc-900 text-white hover:bg-zinc-800" : "bg-zinc-100 text-zinc-400 cursor-not-allowed")}>
                  {isSearching ? <><I.Loader2 className="animate-spin" /> Running...</> : <><I.Search /> Search</>}
                </button>
              </div>
              {results.length > 0 && (
                <div className="flex items-center justify-between mt-3 pt-3 border-t border-zinc-100">
                  <span className="text-xs text-zinc-400">
                    {results.length} result{results.length !== 1 ? "s" : ""} for "<span className="text-zinc-600 font-medium">{queryHistory[0]}</span>"
                  </span>
                  <span className="text-xs text-zinc-400">{searchType} · top-{topK} · threshold ≥ {threshold.toFixed(1)}</span>
                </div>
              )}
            </div>

            {/* Results */}
            {results.length === 0 && !isSearching ? (
              <div className="flex-1 flex flex-col items-center justify-center py-20 text-center">
                <div className="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center mb-4">
                  <I.Search className="text-zinc-400" />
                </div>
                <div className="text-sm font-medium text-zinc-500 mb-1">Run a query to test retrieval</div>
                <div className="text-xs text-zinc-400 max-w-xs leading-relaxed">
                  Type a question your users might ask and see which chunks come back. Adjust parameters on the left to compare.
                </div>
              </div>
            ) : isSearching ? (
              <div className="flex-1 flex flex-col items-center justify-center py-20">
                <I.Loader2 className="text-zinc-400 animate-spin mb-3" style={{ width: 24, height: 24 }} />
                <div className="text-sm text-zinc-500">Searching {mockIndex.stats.chunks.toLocaleString()} chunks...</div>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {results.map(result => (
                  <div key={result.rank} className="rounded-lg border border-zinc-200 hover:border-zinc-300 transition-colors">
                    <div className="p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <span className="w-7 h-7 rounded-md bg-zinc-100 text-zinc-600 text-xs font-mono font-bold flex items-center justify-center">
                            {result.rank}
                          </span>
                          <ScoreBar score={result.score} />
                        </div>
                        <div className="flex gap-0.5">
                          <button onClick={() => setVotes(v => ({ ...v, [result.rank]: v[result.rank] === "up" ? null : "up" }))}
                            className={cn("p-1.5 rounded-md transition-colors",
                              votes[result.rank] === "up" ? "bg-emerald-50 text-emerald-600" : "text-zinc-300 hover:text-zinc-500 hover:bg-zinc-50")}>
                            <I.ThumbsUp />
                          </button>
                          <button onClick={() => setVotes(v => ({ ...v, [result.rank]: v[result.rank] === "down" ? null : "down" }))}
                            className={cn("p-1.5 rounded-md transition-colors",
                              votes[result.rank] === "down" ? "bg-red-50 text-red-500" : "text-zinc-300 hover:text-zinc-500 hover:bg-zinc-50")}>
                            <I.ThumbsDown />
                          </button>
                        </div>
                      </div>

                      <p className={cn("text-sm text-zinc-600 leading-relaxed mb-2",
                        expandedResult !== result.rank && "line-clamp-3")}>
                        {result.content}
                      </p>
                      {result.content.length > 140 && (
                        <button onClick={() => setExpandedResult(expandedResult === result.rank ? null : result.rank)}
                          className="text-xs font-medium text-zinc-400 hover:text-zinc-600 transition-colors mb-3">
                          {expandedResult === result.rank ? "Show less" : "Show full chunk →"}
                        </button>
                      )}

                      <div className="flex items-center gap-4 pt-3 border-t border-zinc-100 text-xs text-zinc-400">
                        <span className="flex items-center gap-1"><I.FileText className="w-3 h-3" /> {result.document}</span>
                        <span>Page {result.page}</span>
                        <span>Chunk #{result.chunkId}</span>
                        <span>{result.tokens} tokens</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <style>{`
        .line-clamp-3 { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .animate-spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}
