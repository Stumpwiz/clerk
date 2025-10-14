"use client";

import { useState } from "react";
import type { LetterTemplate } from "@/lib/client-api";

interface Props {
  template: LetterTemplate;
  onUpdate: (header: string, body: string) => Promise<boolean>;
}

export default function TemplateEditor({ template, onUpdate }: Props) {
  const [header, setHeader] = useState(template.header);
  const [body, setBody] = useState(template.body);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [expanded, setExpanded] = useState(false);

  const handleSave = async () => {
    try {
      setSaving(true);
      setMessage(null);
      
      await onUpdate(header, body);
      
      setMessage({ type: "success", text: "Template saved successfully" });
      setTimeout(() => setMessage(null), 3000);
    } catch (err: any) {
      setMessage({ type: "error", text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = header !== template.header || body !== template.body;

  return (
    <div className="rounded-lg bg-white shadow">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-6 text-left"
      >
        <h2 className="text-xl font-semibold text-gray-900">
          📝 Edit LaTeX Template
        </h2>
        <span className="text-gray-500">
          {expanded ? "▼ Collapse" : "▶ Expand"}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-gray-200 p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Header (Document Setup & Packages)
            </label>
            <textarea
              value={header}
              onChange={(e) => setHeader(e.target.value)}
              rows={8}
              className="w-full rounded-lg border border-gray-300 p-3 font-mono text-sm text-gray-900 bg-gray-50 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:bg-white"
              placeholder="\\documentclass{letter}..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Body (Letter Content)
            </label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={18}
              className="w-full rounded-lg border border-gray-300 p-3 font-mono text-sm text-gray-900 bg-gray-50 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 focus:bg-white"
              placeholder="\\begin{document}..."
            />
            <p className="mt-1 text-xs text-gray-500">
              Use placeholders: \names (addressee), \salutation (greeting), \apartment (unit number)
            </p>
          </div>

          <div className="flex items-center justify-between">
            <div>
              {message && (
                <span
                  className={`text-sm font-medium ${
                    message.type === "success" ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {message.type === "success" ? "✅" : "❌"} {message.text}
                </span>
              )}
            </div>

            <button
              onClick={handleSave}
              disabled={!hasChanges || saving}
              className="rounded-lg bg-blue-600 px-6 py-2 text-white font-semibold hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? "Saving..." : "Save Template"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
