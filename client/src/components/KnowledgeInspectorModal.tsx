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
    <div className="flex-1 flex flex-col h-full overflow-hidden p-6 bg-slate-50 dark:bg-slate-950/40">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center space-x-2">
            <span>📚 Policy Knowledge Base</span>
          </h2>
          <p className="text-xs text-slate-600 dark:text-slate-400 font-medium">
            Audited PDF, Markdown, and text policy documents indexed into AnythingLLM Vector Store &amp; RAG engine.
          </p>
        </div>
        <button
          onClick={onClose}
          className="px-3.5 py-1.5 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-700 text-xs font-bold transition cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          Return to Workbench ✕
        </button>
      </div>

      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center text-xs text-slate-500 gap-3">
          <div className="w-8 h-8 border-3 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <span>Loading knowledge base documents...</span>
        </div>
      ) : (
        <div className="flex-1 flex gap-6 overflow-hidden min-h-0">
          {/* Document List Sidebar */}
          <div className="w-84 flex flex-col bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 p-4 rounded-2xl space-y-3 overflow-hidden shadow-xs shrink-0">
            {/* Search Input */}
            <div className="relative">
              <input
                type="text"
                placeholder="Search documents or content..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-2 rounded-xl text-xs bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="absolute left-2.5 top-2.5 text-xs text-slate-400">🔍</span>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-[11px] font-medium custom-scrollbar">
              <button
                onClick={() => setFilterType("all")}
                className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap ${
                  filterType === "all"
                    ? "bg-blue-600 text-white font-bold shadow-xs"
                    : "bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                All ({documents.length})
              </button>
              <button
                onClick={() => setFilterType("pdf")}
                className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap ${
                  filterType === "pdf"
                    ? "bg-rose-600 text-white font-bold shadow-xs"
                    : "bg-slate-100 dark:bg-slate-800/80 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
                }`}
              >
                PDF ({pdfCount})
              </button>
              <button
                onClick={() => setFilterType("markdown")}
                className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap ${
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
                  className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap ${
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
            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-0.5">
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
                      className={`p-3 rounded-xl border text-xs cursor-pointer transition ${
                        isSelected
                          ? "bg-blue-50 dark:bg-blue-500/10 border-blue-500 text-blue-900 dark:text-white font-bold shadow-xs ring-1 ring-blue-500/30"
                          : "bg-slate-50/50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-300 hover:border-blue-400"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-1.5 mb-1.5">
                        <div className="font-bold line-clamp-2 leading-snug flex-1">{doc.title}</div>
                        {typeBadge}
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 font-mono">
                        <span className="truncate max-w-[140px] text-blue-700 dark:text-blue-400 font-medium">
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

          {/* Document Content Inspector / Viewer Panel */}
          <div className="flex-1 flex flex-col bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl overflow-hidden shadow-xs min-h-0">
            {selectedDoc ? (
              <div className="flex-1 flex flex-col overflow-hidden min-h-0">
                {/* Document Top Bar */}
                <div className="pb-3 mb-4 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3 shrink-0">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold text-blue-700 dark:text-blue-400">
                        {selectedDoc.filename}
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        ({(selectedDoc.size_bytes / 1024).toFixed(1)} KB)
                      </span>
                    </div>
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                      {selectedDoc.title}
                    </h3>
                  </div>

                  {/* Actions Toolbar */}
                  <div className="flex items-center gap-2">
                    {/* Markdown Formatted / Raw Switcher */}
                    {currentType === "markdown" && (
                      <div className="flex items-center bg-slate-100 dark:bg-slate-800 p-0.5 rounded-xl text-xs">
                        <button
                          onClick={() => setMdViewMode("formatted")}
                          className={`px-3 py-1 rounded-lg font-bold transition cursor-pointer ${
                            mdViewMode === "formatted"
                              ? "bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-xs"
                              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                          }`}
                        >
                          ✨ Formatted
                        </button>
                        <button
                          onClick={() => setMdViewMode("raw")}
                          className={`px-3 py-1 rounded-lg font-bold transition cursor-pointer ${
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
                          className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-bold transition flex items-center gap-1.5"
                        >
                          <span>↗</span>
                          <span>Open in New Tab</span>
                        </a>
                        <a
                          href={pdfBlobUrl}
                          download={selectedDoc.filename}
                          className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
                        >
                          <span>⬇</span>
                          <span>Download PDF</span>
                        </a>
                      </>
                    )}

                    {/* Copy Content Button for text/md */}
                    {currentType !== "pdf" && (
                      <button
                        onClick={() => handleCopy(selectedDoc.content)}
                        className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-bold transition flex items-center gap-1.5 cursor-pointer"
                      >
                        <span>{copied ? "✓" : "📋"}</span>
                        <span>{copied ? "Copied!" : "Copy Text"}</span>
                      </button>
                    )}

                    <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 font-bold flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                      <span>RAG Indexed</span>
                    </span>
                  </div>
                </div>

                {/* Render Body */}
                <div className="flex-1 overflow-hidden min-h-0 flex flex-col">
                  {/* PDF Viewer */}
                  {currentType === "pdf" && (
                    <div className="flex-1 flex flex-col overflow-hidden min-h-0 bg-slate-100 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800">
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
                          className="w-full h-full rounded-xl border-0 bg-white"
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
                    <div className="flex-1 overflow-y-auto custom-scrollbar pr-2">
                      {mdViewMode === "formatted" ? (
                        <div className="bg-slate-50/50 dark:bg-slate-950/40 p-6 rounded-2xl border border-slate-100 dark:border-slate-800/80">
                          <MarkdownRenderer content={selectedDoc.content} />
                        </div>
                      ) : (
                        <div className="rounded-xl overflow-hidden border border-slate-800 bg-slate-950 text-slate-200">
                          <div className="px-4 py-2 bg-slate-900 border-b border-slate-800 text-[11px] font-mono text-slate-400 flex items-center justify-between">
                            <span>Markdown Raw Source ({selectedDoc.content.length} chars)</span>
                            <button
                              onClick={() => handleCopy(selectedDoc.content)}
                              className="text-blue-400 hover:text-blue-300 transition"
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
                    <div className="flex-1 flex flex-col overflow-hidden min-h-0 space-y-2">
                      <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 font-mono px-1">
                        <span>Lines: {selectedDoc.content.split("\n").length}</span>
                        <span>Words: {selectedDoc.content.split(/\s+/).filter(Boolean).length}</span>
                        <span>Characters: {selectedDoc.content.length}</span>
                      </div>
                      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800">
                        <pre className="font-sans text-xs text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap font-medium">
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
