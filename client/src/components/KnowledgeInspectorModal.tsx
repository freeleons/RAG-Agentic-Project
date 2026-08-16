import React, { useEffect, useState, useRef } from "react";
import { fetchKnowledgeDocuments, fetchKnowledgeDocumentBlob } from "../api";
import { KnowledgeDocument } from "../types";
import { MarkdownRenderer } from "./MarkdownRenderer";

interface KnowledgeInspectorModalProps {
  onClose: () => void;
}

type FileFilterType = "all" | "pdf" | "markdown" | "text";

export const KnowledgeInspectorModal: React.FC<KnowledgeInspectorModalProps> = ({ onClose }) => {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterType, setFilterType] = useState<FileFilterType>("all");

  // Real estate & layout controls
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isFocusMode, setIsFocusMode] = useState(false);

  // PDF blob state
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  // Markdown view mode: "formatted" | "raw"
  const [mdViewMode, setMdViewMode] = useState<"formatted" | "raw">("formatted");

  // Copy status feedback
  const [copied, setCopied] = useState(false);

  // Track active blob url to revoke on unmount/change
  const activeBlobUrlRef = useRef<string | null>(null);

  useEffect(() => {
    fetchKnowledgeDocuments()
      .then((docs) => {
        setDocuments(docs);
        if (docs.length > 0) setSelectedDoc(docs[0]);
      })
      .catch((err) => console.error("Failed to fetch knowledge documents:", err))
      .finally(() => setLoading(false));
  }, []);

  // Whenever selectedDoc changes, if it's a PDF, fetch its blob
  useEffect(() => {
    // Revoke previous blob if any
    if (activeBlobUrlRef.current) {
      URL.revokeObjectURL(activeBlobUrlRef.current);
      activeBlobUrlRef.current = null;
      setPdfBlobUrl(null);
    }
    setPdfError(null);

    if (!selectedDoc) return;

    const isPdf =
      selectedDoc.file_type === "pdf" ||
      selectedDoc.filename.toLowerCase().endsWith(".pdf");

    if (isPdf) {
      setPdfLoading(true);
      fetchKnowledgeDocumentBlob(selectedDoc.filename)
        .then((blob) => {
          const url = URL.createObjectURL(blob);
          activeBlobUrlRef.current = url;
          setPdfBlobUrl(url);
        })
        .catch((err) => {
          console.error("Failed to load PDF blob:", err);
          setPdfError("Failed to load PDF preview. You can try downloading the file directly.");
        })
        .finally(() => setPdfLoading(false));
    }

    return () => {
      if (activeBlobUrlRef.current) {
        URL.revokeObjectURL(activeBlobUrlRef.current);
        activeBlobUrlRef.current = null;
      }
    };
  }, [selectedDoc]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getDocType = (doc: KnowledgeDocument): "pdf" | "markdown" | "text" => {
    if (doc.file_type) return doc.file_type;
    const lower = doc.filename.toLowerCase();
    if (lower.endsWith(".pdf")) return "pdf";
    if (lower.endsWith(".md")) return "markdown";
    return "text";
  };

  const filteredDocs = documents.filter((d) => {
    const docType = getDocType(d);
    if (filterType !== "all" && docType !== filterType) return false;

    const query = searchTerm.toLowerCase();
    return (
      d.title.toLowerCase().includes(query) ||
      d.filename.toLowerCase().includes(query) ||
      (d.content && d.content.toLowerCase().includes(query))
    );
  });

  const pdfCount = documents.filter((d) => getDocType(d) === "pdf").length;
  const mdCount = documents.filter((d) => getDocType(d) === "markdown").length;
  const txtCount = documents.filter((d) => getDocType(d) === "text").length;

  const currentType = selectedDoc ? getDocType(selectedDoc) : null;

  return (
    <div className={`flex-1 flex flex-col h-full overflow-hidden bg-slate-50 dark:bg-slate-950/40 ${isFocusMode ? "p-1.5" : "p-3 md:p-4"}`}>
      {/* Top Header - Minimized or hidden in focus mode */}
      {!isFocusMode && (
        <div className="flex items-center justify-between mb-2.5 shrink-0">
          <div className="flex items-center space-x-3">
            <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center space-x-2">
              <span>📚 Policy Knowledge Base</span>
            </h2>
            <span className="hidden sm:inline-block text-slate-300 dark:text-slate-700">|</span>
            <p className="hidden sm:block text-xs text-slate-600 dark:text-slate-400 font-medium">
              Audited documents indexed into AnythingLLM Vector Store &amp; RAG engine.
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 border border-slate-200 dark:border-slate-700"
              title={sidebarOpen ? "Hide document list for wider viewing area" : "Show document list"}
            >
              <span>{sidebarOpen ? "◀ Hide Sidebar" : "▶ Show Docs"}</span>
            </button>
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-700 text-xs font-bold transition cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Return to Workbench ✕
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center text-xs text-slate-500 gap-3">
          <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <span>Loading knowledge base documents...</span>
        </div>
      ) : (
        <div className="flex-1 flex gap-3 md:gap-4 overflow-hidden min-h-0">
          {/* Document List Sidebar */}
          {sidebarOpen && !isFocusMode && (
            <div className="w-72 sm:w-80 md:w-84 flex flex-col bg-white dark:bg-slate-900/70 border border-slate-200 dark:border-slate-800 p-3.5 rounded-2xl space-y-2.5 overflow-hidden shadow-xs shrink-0 transition-all duration-200">
              {/* Search Input */}
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search documents or content..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 rounded-xl text-xs bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <span className="absolute left-2.5 top-2 text-xs text-slate-400">🔍</span>
              </div>

              {/* Filter Pills */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 text-[11px] font-medium custom-scrollbar">
                <button
                  onClick={() => setFilterType("all")}
                  className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap cursor-pointer ${
                    filterType === "all"
                      ? "bg-blue-600 text-white font-bold shadow-xs"
                      : "bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
                  }`}
                >
                  All ({documents.length})
                </button>
                <button
                  onClick={() => setFilterType("pdf")}
                  className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap cursor-pointer ${
                    filterType === "pdf"
                      ? "bg-rose-600 text-white font-bold shadow-xs"
                      : "bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
                  }`}
                >
                  PDF ({pdfCount})
                </button>
                <button
                  onClick={() => setFilterType("markdown")}
                  className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap cursor-pointer ${
                    filterType === "markdown"
                      ? "bg-indigo-600 text-white font-bold shadow-xs"
                      : "bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
                  }`}
                >
                  MD ({mdCount})
                </button>
                {txtCount > 0 && (
                  <button
                    onClick={() => setFilterType("text")}
                    className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap cursor-pointer ${
                      filterType === "text"
                        ? "bg-emerald-600 text-white font-bold shadow-xs"
                        : "bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
                    }`}
                  >
                    TXT ({txtCount})
                  </button>
                )}
              </div>

              {/* Document Items List */}
              <div className="flex-1 overflow-y-auto custom-scrollbar space-y-1.5 pr-0.5">
                {filteredDocs.length === 0 ? (
                  <div className="p-4 text-center text-xs text-slate-400">
                    No documents found matching "{searchTerm}"
                  </div>
                ) : (
                  filteredDocs.map((doc) => {
                    const docType = getDocType(doc);
                    const isSelected = selectedDoc?.filename === doc.filename;

                    let typeBadge = (
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                        TXT
                      </span>
                    );
                    if (docType === "pdf") {
                      typeBadge = (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-rose-100 dark:bg-rose-950/60 text-rose-700 dark:text-rose-400 border border-rose-300 dark:border-rose-800/60">
                          PDF
                        </span>
                      );
                    } else if (docType === "markdown") {
                      typeBadge = (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-400 border border-indigo-300 dark:border-indigo-800/60">
                          MD
                        </span>
                      );
                    }

                    return (
                      <div
                        key={doc.filename}
                        onClick={() => setSelectedDoc(doc)}
                        className={`p-2.5 rounded-xl border text-xs cursor-pointer transition ${
                          isSelected
                            ? "bg-blue-50 dark:bg-blue-500/10 border-blue-500 text-blue-900 dark:text-white font-bold shadow-xs ring-1 ring-blue-500/30"
                            : "bg-slate-50/50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-300 hover:border-blue-400"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-1.5 mb-1">
                          <div className="font-bold line-clamp-2 leading-snug flex-1">{doc.title}</div>
                          {typeBadge}
                        </div>
                        <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 font-mono">
                          <span className="truncate max-w-[130px] text-blue-700 dark:text-blue-400 font-medium">
                            {doc.filename}
                          </span>
                          <span>{Math.round(doc.size_bytes / 1024)} KB</span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

          {/* Document Content Inspector / Viewer Panel */}
          <div className="flex-1 flex flex-col bg-white dark:bg-slate-900/70 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-xs min-h-0">
            {selectedDoc ? (
              <div className="flex-1 flex flex-col overflow-hidden min-h-0">
                {/* Document Top Bar */}
                <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-2.5 shrink-0 bg-slate-50/80 dark:bg-slate-900/90">
                  <div className="flex items-center space-x-2.5 min-w-0">
                    {!sidebarOpen && !isFocusMode && (
                      <button
                        onClick={() => setSidebarOpen(true)}
                        className="px-2 py-1 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800 hover:bg-blue-100 text-xs font-semibold transition cursor-pointer flex items-center gap-1 shrink-0"
                        title="Show document list"
                      >
                        <span>📑 Docs ({documents.length})</span>
                      </button>
                    )}
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-mono font-bold text-blue-700 dark:text-blue-400 truncate max-w-[200px] sm:max-w-[320px]">
                          {selectedDoc.filename}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono shrink-0">
                          ({(selectedDoc.size_bytes / 1024).toFixed(1)} KB)
                        </span>
                      </div>
                      <h3 className="text-sm sm:text-base font-bold text-slate-900 dark:text-white truncate max-w-[260px] sm:max-w-[420px] md:max-w-[550px]">
                        {selectedDoc.title}
                      </h3>
                    </div>
                  </div>

                  {/* Actions Toolbar */}
                  <div className="flex items-center gap-2 shrink-0">
                    {/* Markdown Formatted / Raw Switcher */}
                    {currentType === "markdown" && (
                      <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-xl text-xs">
                        <button
                          onClick={() => setMdViewMode("formatted")}
                          className={`px-2.5 py-1 rounded-lg font-bold transition cursor-pointer ${
                            mdViewMode === "formatted"
                              ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-xs"
                              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                          }`}
                        >
                          ✨ Formatted
                        </button>
                        <button
                          onClick={() => setMdViewMode("raw")}
                          className={`px-2.5 py-1 rounded-lg font-bold transition cursor-pointer ${
                            mdViewMode === "raw"
                              ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-xs"
                              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                          }`}
                        >
                          📄 Raw Source
                        </button>
                      </div>
                    )}

                    {/* PDF Action Buttons */}
                    {currentType === "pdf" && pdfBlobUrl && (
                      <>
                        <a
                          href={pdfBlobUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-2.5 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-bold transition flex items-center gap-1.5"
                          title="Open PDF in external browser tab"
                        >
                          <span>↗</span>
                          <span className="hidden sm:inline">Open in New Tab</span>
                        </a>
                        <a
                          href={pdfBlobUrl}
                          download={selectedDoc.filename}
                          className="px-2.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
                          title="Download document file"
                        >
                          <span>⬇</span>
                          <span className="hidden sm:inline">Download PDF</span>
                        </a>
                      </>
                    )}

                    {/* Copy Content Button for text/md */}
                    {currentType !== "pdf" && (
                      <button
                        onClick={() => handleCopy(selectedDoc.content)}
                        className="px-2.5 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-bold transition flex items-center gap-1.5 cursor-pointer"
                      >
                        <span>{copied ? "✓" : "📋"}</span>
                        <span>{copied ? "Copied!" : "Copy Text"}</span>
                      </button>
                    )}

                    {/* Focus Mode / Fullscreen Toggle */}
                    <button
                      onClick={() => setIsFocusMode(!isFocusMode)}
                      className={`px-2.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer ${
                        isFocusMode
                          ? "bg-amber-500 hover:bg-amber-600 text-white shadow-xs"
                          : "bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200"
                      }`}
                      title={isFocusMode ? "Exit full real estate focus mode" : "Expand viewer to maximum full-screen real estate"}
                    >
                      <span>{isFocusMode ? "⤡" : "⤢"}</span>
                      <span className="hidden md:inline">{isFocusMode ? "Exit Focus" : "Focus Mode"}</span>
                    </button>

                    <span className="text-xs px-2 py-1 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 font-bold flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                      <span className="hidden lg:inline">RAG Indexed</span>
                    </span>

                    {/* Close / Return button when in focus mode */}
                    {isFocusMode && (
                      <button
                        onClick={onClose}
                        className="px-2.5 py-1.5 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-700 text-xs font-bold transition cursor-pointer"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                </div>

                {/* Render Body */}
                <div className="flex-1 overflow-hidden min-h-0 flex flex-col bg-slate-100 dark:bg-slate-950">
                  {/* PDF Viewer - Edge-to-edge full canvas */}
                  {currentType === "pdf" && (
                    <div className="flex-1 flex flex-col overflow-hidden min-h-0 w-full h-full">
                      {pdfLoading ? (
                        <div className="flex-1 flex flex-col items-center justify-center text-xs text-slate-500 gap-3">
                          <div className="w-8 h-8 border-3 border-rose-500 border-t-transparent rounded-full animate-spin"></div>
                          <span>Streaming PDF document...</span>
                        </div>
                      ) : pdfError ? (
                        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-3">
                          <div className="text-3xl">⚠️</div>
                          <p className="text-xs text-rose-500 font-bold">{pdfError}</p>
                        </div>
                      ) : pdfBlobUrl ? (
                        <iframe
                          src={pdfBlobUrl}
                          title={selectedDoc.title}
                          className="w-full h-full border-0 bg-white"
                        />
                      ) : (
                        <div className="flex-1 flex items-center justify-center text-xs text-slate-400">
                          Preparing PDF preview...
                        </div>
                      )}
                    </div>
                  )}

                  {/* Markdown Viewer */}
                  {currentType === "markdown" && (
                    <div className="flex-1 overflow-y-auto custom-scrollbar p-4 md:p-6">
                      {mdViewMode === "formatted" ? (
                        <div className="max-w-5xl mx-auto bg-white dark:bg-slate-900/90 p-6 md:p-8 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-xs">
                          <MarkdownRenderer content={selectedDoc.content} />
                        </div>
                      ) : (
                        <div className="max-w-5xl mx-auto rounded-xl overflow-hidden border border-slate-800 bg-slate-950 text-slate-200 shadow-xs">
                          <div className="px-4 py-2 bg-slate-900 border-b border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
                            <span>Markdown Raw Source ({selectedDoc.content.length} chars)</span>
                            <button
                              onClick={() => handleCopy(selectedDoc.content)}
                              className="text-blue-400 hover:text-blue-300 transition cursor-pointer"
                            >
                              {copied ? "Copied!" : "Copy"}
                            </button>
                          </div>
                          <pre className="p-4 text-xs font-mono leading-relaxed whitespace-pre-wrap">
                            {selectedDoc.content}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Plain Text Viewer */}
                  {currentType === "text" && (
                    <div className="flex-1 flex flex-col overflow-hidden min-h-0 p-4 space-y-2">
                      <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 font-mono px-1">
                        <span>Lines: {selectedDoc.content.split("\n").length}</span>
                        <span>Words: {selectedDoc.content.split(/\s+/).filter(Boolean).length}</span>
                        <span>Characters: {selectedDoc.content.length}</span>
                      </div>
                      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 md:p-6 bg-white dark:bg-slate-900/90 rounded-xl border border-slate-200 dark:border-slate-800 shadow-xs">
                        <pre className="font-sans text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap font-medium">
                          {selectedDoc.content}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-xs text-slate-500 gap-2">
                <span className="text-3xl">📄</span>
                <span>Select a document from the left list to inspect its contents.</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
