import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { KnowledgeInspectorModal } from "../components/KnowledgeInspectorModal";
import * as api from "../api";
import { KnowledgeDocument } from "../types";

const mockDocs: KnowledgeDocument[] = [
  {
    filename: "policies.md",
    title: "ApexCare HR Policies",
    category: "HR & Benefits",
    size_bytes: 5373,
    file_type: "markdown",
    mime_type: "text/markdown",
    content: "# ApexCare HR Policies\n\n## 1. WEX FSA\n* Healthcare FSA Limit: $3,200\n\n| Plan | Limit |\n|---|---|\n| Health | $3200 |\n\n> Note: Use-it-or-lose-it rule applies.",
  },
  {
    filename: "guidelines.pdf",
    title: "Benefits Enrollment Guide",
    category: "HR & Benefits",
    size_bytes: 449542,
    file_type: "pdf",
    mime_type: "application/pdf",
    content: "Official policy document (PDF).",
  },
  {
    filename: "contact_info.txt",
    title: "HR Contact Info",
    category: "HR & Benefits",
    size_bytes: 120,
    file_type: "text",
    mime_type: "text/plain",
    content: "HR Department: hr@apexcare.internal\nPhone: 555-0199",
  },
];

describe("KnowledgeInspectorModal", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.URL.createObjectURL = vi.fn(() => "blob:http://localhost/mock-blob-uuid");
    window.URL.revokeObjectURL = vi.fn();
  });

  it("renders knowledge documents and displays formatted markdown", async () => {
    vi.spyOn(api, "fetchKnowledgeDocuments").mockResolvedValue(mockDocs);

    render(<KnowledgeInspectorModal onClose={vi.fn()} />);

    expect(screen.getByText(/Loading knowledge base documents/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText("ApexCare HR Policies").length).toBeGreaterThan(0);
    });

    // Check filter pills
    expect(screen.getByText(/All \(3\)/i)).toBeInTheDocument();
    expect(screen.getByText(/PDF \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText(/MD \(1\)/i)).toBeInTheDocument();

    // Check formatted markdown rendering: heading, list item, and blockquote
    expect(screen.getByText(/Healthcare FSA Limit: \$3,200/i)).toBeInTheDocument();
    expect(screen.getByText(/Use-it-or-lose-it rule applies/i)).toBeInTheDocument();

    // Check table headers
    expect(screen.getByText("Plan")).toBeInTheDocument();
    expect(screen.getByText("Limit")).toBeInTheDocument();
  });

  it("allows switching between Formatted and Raw Markdown views", async () => {
    vi.spyOn(api, "fetchKnowledgeDocuments").mockResolvedValue(mockDocs);

    render(<KnowledgeInspectorModal onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getAllByText("ApexCare HR Policies").length).toBeGreaterThan(0);
    });

    // Click Raw Source
    const rawBtn = screen.getByRole("button", { name: /Raw Source/i });
    fireEvent.click(rawBtn);

    expect(screen.getByText(/Markdown Raw Source/i)).toBeInTheDocument();

    // Click Formatted
    const formattedBtn = screen.getByRole("button", { name: /Formatted/i });
    fireEvent.click(formattedBtn);

    expect(screen.queryByText(/Markdown Raw Source/i)).not.toBeInTheDocument();
  });

  it("fetches PDF blob and renders iframe preview when PDF is selected", async () => {
    vi.spyOn(api, "fetchKnowledgeDocuments").mockResolvedValue(mockDocs);
    const mockBlob = new Blob(["mock-pdf-content"], { type: "application/pdf" });
    vi.spyOn(api, "fetchKnowledgeDocumentBlob").mockResolvedValue(mockBlob);

    render(<KnowledgeInspectorModal onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getAllByText("Benefits Enrollment Guide").length).toBeGreaterThan(0);
    });

    // Select PDF from the list
    const pdfDocItems = screen.getAllByText("Benefits Enrollment Guide");
    fireEvent.click(pdfDocItems[0]);

    await waitFor(() => {
      expect(api.fetchKnowledgeDocumentBlob).toHaveBeenCalledWith("guidelines.pdf");
      const iframe = screen.getByTitle("Benefits Enrollment Guide");
      expect(iframe).toBeInTheDocument();
      expect(iframe).toHaveAttribute("src", "blob:http://localhost/mock-blob-uuid");
    });

    // Check download button & open in new tab
    expect(screen.getByRole("link", { name: /Download PDF/i })).toHaveAttribute(
      "href",
      "blob:http://localhost/mock-blob-uuid"
    );
    expect(screen.getByRole("link", { name: /Open in New Tab/i })).toHaveAttribute(
      "href",
      "blob:http://localhost/mock-blob-uuid"
    );
  });

  it("renders plain text documents with word and line count metrics", async () => {
    vi.spyOn(api, "fetchKnowledgeDocuments").mockResolvedValue(mockDocs);

    render(<KnowledgeInspectorModal onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getAllByText("HR Contact Info").length).toBeGreaterThan(0);
    });

    // Select plain text doc
    const txtItems = screen.getAllByText("HR Contact Info");
    fireEvent.click(txtItems[0]);

    await waitFor(() => {
      expect(screen.getByText(/Lines: 2/i)).toBeInTheDocument();
      expect(screen.getByText(/hr@apexcare.internal/i)).toBeInTheDocument();
    });
  });

  it("filters documents by search query and type filter pills", async () => {
    vi.spyOn(api, "fetchKnowledgeDocuments").mockResolvedValue(mockDocs);

    render(<KnowledgeInspectorModal onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getAllByText("ApexCare HR Policies").length).toBeGreaterThan(0);
    });

    // Filter by PDF pill
    const pdfPill = screen.getByRole("button", { name: /PDF \(1\)/i });
    fireEvent.click(pdfPill);

    // Sidebar should have guidelines.pdf
    expect(screen.getByText("guidelines.pdf")).toBeInTheDocument();

    // Search query with no match
    const searchInput = screen.getByPlaceholderText(/Search documents/i);
    fireEvent.change(searchInput, { target: { value: "nonexistent" } });

    expect(screen.getByText(/No documents found matching "nonexistent"/i)).toBeInTheDocument();
  });

  it("supports collapsing sidebar and entering full-focus mode for maximum real estate", async () => {
    vi.spyOn(api, "fetchKnowledgeDocuments").mockResolvedValue(mockDocs);

    render(<KnowledgeInspectorModal onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getAllByText("ApexCare HR Policies").length).toBeGreaterThan(0);
    });

    // Sidebar is initially visible with Hide Sidebar button
    const hideSidebarBtn = screen.getByRole("button", { name: /Hide Sidebar/i });
    expect(hideSidebarBtn).toBeInTheDocument();

    // Toggle hide sidebar
    fireEvent.click(hideSidebarBtn);

    // Docs expand button appears
    const showDocsBtn = screen.getByRole("button", { name: /Docs \(3\)/i });
    expect(showDocsBtn).toBeInTheDocument();

    // Expand sidebar again
    fireEvent.click(showDocsBtn);
    expect(screen.getByRole("button", { name: /Hide Sidebar/i })).toBeInTheDocument();

    // Toggle Focus Mode
    const focusBtn = screen.getByRole("button", { name: /Focus Mode/i });
    fireEvent.click(focusBtn);

    // Top banner is hidden in focus mode, Exit Focus button is present
    expect(screen.getByRole("button", { name: /Exit Focus/i })).toBeInTheDocument();
    expect(screen.queryByText("📚 Policy Knowledge Base")).not.toBeInTheDocument();

    // Exit Focus Mode
    fireEvent.click(screen.getByRole("button", { name: /Exit Focus/i }));
    expect(screen.getByText("📚 Policy Knowledge Base")).toBeInTheDocument();
  });
});

