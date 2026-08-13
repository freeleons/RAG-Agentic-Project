import React, { useEffect, useState } from "react";
import { fetchKnowledgeDocuments } from "../api";
import { KnowledgeDocument } from "../types";

interface KnowledgeInspectorModalProps {
  onClose: () => void;
}

export const KnowledgeInspectorModal: React.FC<KnowledgeInspectorModalProps> = ({ onClose }) => {
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  useEffect(() => {
    fetchKnowledgeDocuments()
      .then((docs) => {
        setDocuments(docs);
        if (docs.length > 0) setSelectedDoc(docs[0]);
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const filteredDocs = documents.filter(
    (d) =>
      d.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.filename.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden p-6 bg-slate-50 dark:bg-slate-950/40">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center space-x-2">
            <span>Policy Knowledge Base</span>
          </h2>
          <p className="text-xs text-slate-600 dark:text-slate-400 font-medium">
            Audited PDF policy documents indexed into AnythingLLM Vector Store.
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
        <div className="flex-1 flex items-center justify-center text-xs text-slate-500">
          Loading knowledge base documents...
        </div>
      ) : (
        <div className="flex-1 flex gap-6 overflow-hidden">
          {/* Document List Sidebar */}
          <div className="w-80 flex flex-col bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 p-4 rounded-2xl space-y-3 overflow-hidden shadow-xs">
            <input
              type="text"
              placeholder="Search documents..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 rounded-xl text-xs bg-slate-100 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-slate-900 dark:text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />

            <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2">
              {filteredDocs.map((doc) => (
                <div
                  key={doc.filename}
                  onClick={() => setSelectedDoc(doc)}
                  className={`p-3 rounded-xl border text-xs cursor-pointer transition ${selectedDoc?.filename === doc.filename
                      ? "bg-blue-50 dark:bg-blue-500/10 border-blue-500 text-blue-900 dark:text-white font-bold shadow-xs"
                      : "bg-slate-50/50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-300 hover:border-blue-400"
                    }`}
                >
                  <div className="font-bold line-clamp-1 mb-1">{doc.title}</div>
                  <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 font-mono">
                    <span className="text-blue-700 dark:text-blue-400 font-bold">{doc.filename}</span>
                    <span>{Math.round(doc.size_bytes / 1024)} KB</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Document Content Inspector Panel */}
          <div className="flex-1 bg-white dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl overflow-y-auto custom-scrollbar shadow-xs">
            {selectedDoc ? (
              <div className="space-y-4">
                <div className="pb-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                  <div>
                    <span className="text-xs font-mono font-bold text-blue-700 dark:text-blue-400">{selectedDoc.filename}</span>
                    <h3 className="text-lg font-bold text-slate-900 dark:text-white">{selectedDoc.title}</h3>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 font-bold">
                    Indexed in RAG Engine
                  </span>
                </div>

                <pre className="font-sans text-xs text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap font-medium">
                  {selectedDoc.content}
                </pre>
              </div>
            ) : (
              <div className="text-center p-8 text-xs text-slate-500">
                Select a document from the left list to inspect its contents.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
