"use client";

import { useEffect, useMemo, useState } from "react";
import { clientApiCall } from "@/lib/client-api";
import { FileText, Loader2 } from "lucide-react";
import FileActions from "../components/file-actions";

interface ReportFile {
  name: string;
  size: number;
  modified: string; // ISO string
}

interface GenerateResponse {
  success: boolean;
  filename?: string;
  error?: string;
}

export default function ReportsPage() {
  // Data
  const [reports, setReports] = useState<ReportFile[]>([]);

  // UI state
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<null | "expirations" | "vacancies">(null);

  // Feedback
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Delete
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [confirmingFile, setConfirmingFile] = useState<string | null>(null);

  // Helpers copied from Rosters page for consistency
  const formatDate = (isoString: string) => {
    if (!isoString) return "—";
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const humanSize = (bytes: number) => {
    if (bytes == null || isNaN(bytes as any)) return "-";
    const thresh = 1024;
    if (bytes < thresh) return `${bytes} B`;
    const units = ["KB", "MB", "GB", "TB"] as const;
    let u = -1;
    let b = bytes;
    do {
      b /= thresh;
      ++u;
    } while (b >= thresh && u < units.length - 1);
    return `${b.toFixed(1)} ${units[u]}`;
  };

  // Alerts auto-dismiss
  useEffect(() => {
    if (success) {
      const t = setTimeout(() => setSuccess(null), 5000);
      return () => clearTimeout(t);
    }
  }, [success]);
  useEffect(() => {
    if (error) {
      const t = setTimeout(() => setError(null), 6000);
      return () => clearTimeout(t);
    }
  }, [error]);

  // Click-away cancel for delete confirm
  useEffect(() => {
    if (!confirmingFile) return;
    const handler = () => setConfirmingFile(null);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [confirmingFile]);

  // Initial load
  useEffect(() => {
    fetchReports();
  }, []);

  async function fetchReports() {
    try {
      setLoading(true);
      setError(null);
      const data = await clientApiCall<{ files: ReportFile[] }>("/api/v1/reports/list");
      const files = Array.isArray(data?.files) ? data.files.slice() : [];
      files.sort((a, b) => new Date(b.modified).getTime() - new Date(a.modified).getTime());
      setReports(files);
    } catch (e: any) {
      setError(e?.message || "Failed to load reports list");
      setReports([]);
    } finally {
      setLoading(false);
    }
  }

  async function generateExpirations() {
    try {
      setGenerating("expirations");
      setError(null);
      setSuccess(null);
      const resp = await clientApiCall<GenerateResponse>(
        "/api/v1/reports/generate/expirations",
        { method: "POST" }
      );
      if (resp?.success) {
        setSuccess(`Expirations report generated: ${resp.filename || "file created"}`);
        await fetchReports();
      } else {
        setError(resp?.error || "Failed to generate expirations report");
      }
    } catch (e: any) {
      setError(e?.message || "Failed to generate expirations report");
    } finally {
      setGenerating(null);
    }
  }

  async function generateVacancies() {
    try {
      setGenerating("vacancies");
      setError(null);
      setSuccess(null);
      const resp = await clientApiCall<GenerateResponse>(
        "/api/v1/reports/generate/vacancies",
        { method: "POST" }
      );
      if (resp?.success) {
        setSuccess(`Vacancies report generated: ${resp.filename || "file created"}`);
        await fetchReports();
      } else {
        setError(resp?.error || "Failed to generate vacancies report");
      }
    } catch (e: any) {
      setError(e?.message || "Failed to generate vacancies report");
    } finally {
      setGenerating(null);
    }
  }

  async function deleteReport(filename: string) {
    try {
      setDeletingFile(filename);
      setError(null);
      setSuccess(null);
      await clientApiCall(`/api/v1/reports/${encodeURIComponent(filename)}`, { method: "DELETE" });
      setSuccess("Report deleted successfully");
      await fetchReports();
    } catch (e: any) {
      // Handle 204/no content and other errors gracefully; clientApiCall should throw only on HTTP errors
      setError(e?.message || "Failed to delete report");
    } finally {
      setDeletingFile(null);
      setConfirmingFile(null);
    }
  }

  // Derived
  const hasFiles = reports.length > 0;

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {/* Alerts */}
        {success && (
          <div className="mb-4 rounded-md bg-green-50 border border-green-200 text-green-800 px-4 py-3">{success}</div>
        )}
        {error && (
          <div className="mb-4 rounded-md bg-red-50 border border-red-200 text-red-800 px-4 py-3">{error}</div>
        )}

        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-gray-900">Reports</h1>
          <p className="text-gray-600">Generate and manage roster reports</p>
        </div>

        {/* Generate section */}
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Generate</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Expirations */}
            <div className="border rounded-lg p-4">
              <h3 className="font-medium text-gray-900 mb-2">Expirations report</h3>
              <div className="flex items-end gap-3">
                <button
                  onClick={generateExpirations}
                  disabled={generating !== null}
                  className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium px-4 py-2 rounded-md transition"
                >
                  {generating === "expirations" ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
                  Generate Expirations Report
                </button>
              </div>
            </div>

            {/* Vacancies */}
            <div className="border rounded-lg p-4">
              <h3 className="font-medium text-gray-900 mb-2">Vacancies report</h3>
              <div className="flex items-end gap-3">
                <button
                  onClick={generateVacancies}
                  disabled={generating !== null}
                  className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium px-4 py-2 rounded-md transition"
                >
                  {generating === "vacancies" ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
                  Generate Vacancies Report
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Files list */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Files</h2>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12 text-gray-500">
              <Loader2 className="h-6 w-6 animate-spin mr-2" /> Loading...
            </div>
          ) : !hasFiles ? (
            <div className="py-12 text-center text-gray-600">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-gray-100 mb-3">
                <FileText className="h-6 w-6 text-gray-400" />
              </div>
              <div>No report files found</div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Filename</th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Date Modified</th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Size</th>
                    <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {reports.map((f) => (
                    <tr key={f.name} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-900">{f.name}</td>
                      <td className="px-4 py-3 text-gray-900">{formatDate(f.modified)}</td>
                      <td className="px-4 py-3 text-gray-900">{humanSize(f.size)}</td>
                      <td className="px-4 py-3 text-right">
                        <div className="inline-flex items-center gap-4">
                          <FileActions
                            viewHref={`/api/proxy/api/v1/reports/download/${encodeURIComponent(f.name)}`}
                            isConfirming={confirmingFile === f.name}
                            onRequestDelete={() => setConfirmingFile(f.name)}
                            onConfirmDelete={() => deleteReport(f.name)}
                            onCancel={() => setConfirmingFile(null)}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
