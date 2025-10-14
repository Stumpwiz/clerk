"use client";

import { useState, useEffect } from "react";
import { letterApi, type LetterTemplate, type PDFListItem } from "@/lib/client-api";
import TemplateEditor from "./TemplateEditor";
import LetterGenerationForm from "./LetterGenerationForm";
import PDFList from "./PDFList";

export default function LetterManagement() {
  const [template, setTemplate] = useState<LetterTemplate | null>(null);
  const [pdfs, setPdfs] = useState<PDFListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  // Load template and PDFs
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError("");
      
      const [templateData, pdfData] = await Promise.all([
        letterApi.getTemplate(),
        letterApi.listPDFs(),
      ]);
      
      setTemplate(templateData);
      setPdfs(pdfData);
    } catch (err: any) {
      setError(err.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const handleTemplateUpdate = async (header: string, body: string) => {
    try {
      const updated = await letterApi.updateTemplate({ header, body });
      setTemplate(updated);
      return true;
    } catch (err: any) {
      throw new Error(err.message || "Failed to update template");
    }
  };

  const handleGenerate = async () => {
    // Refresh PDF list after generation
    const pdfData = await letterApi.listPDFs();
    setPdfs(pdfData);
  };

  const handleDelete = async (filename: string) => {
    try {
      await letterApi.deletePDF(filename);
      setPdfs(pdfs.filter(pdf => pdf.filename !== filename));
    } catch (err: any) {
      throw new Error(err.message || "Failed to delete PDF");
    }
  };

  if (loading) {
    return <div className="text-center py-12">Loading...</div>;
  }

  if (error) {
    return (
      <div className="rounded-lg bg-red-50 p-4">
        <p className="text-red-800">{error}</p>
        <button
          onClick={loadData}
          className="mt-2 text-red-600 hover:text-red-800 font-medium"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <LetterGenerationForm onGenerate={handleGenerate} />
      
      {template && (
        <TemplateEditor
          template={template}
          onUpdate={handleTemplateUpdate}
        />
      )}
      
      <PDFList pdfs={pdfs} onDelete={handleDelete} />
    </div>
  );
}
