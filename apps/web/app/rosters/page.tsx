"use client";

import { useEffect, useMemo, useState } from "react";
import { clientApiCall } from "@/lib/client-api";
import { FileText, Loader2 } from "lucide-react";
import FileActions from "../components/file-actions";

interface RosterFile {
  name: string;
  size: number;
  modified: string;
}

interface GenerateResponse {
  success: boolean;
  filename?: string;
  type?: string;
  error?: string;
}

export default function RostersPage() {
  const [rosters, setRosters] = useState<RosterFile[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<"long" | "short" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);

  // Helpers
  const formatDate = (isoString: string) => {
    const d = new Date(isoString);
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
    const units = ["KB", "MB", "GB", "TB"];
    let u = -1;
    let b = bytes;
    do {
      b /= thresh;
      ++u;
    } while (b >= thresh && u < units.length - 1);
    return `${b.toFixed(1)} ${units[u]}`;
  };

  // Auto-dismiss alerts after 5 seconds
  useEffect(() => {
    if (success) {
      const t = setTimeout(() => setSuccess(null), 5000);
      return () => clearTimeout(t);
    }
  }, [success]);
  useEffect(() => {
    if (error) {
      const t = setTimeout(() => setError(null), 5000);
      return () => clearTimeout(t);
    }
  }, [error]);

  // Click-away to cancel delete confirm
  useEffect(() => {
    if (!deletingFile) return;
    const handler = () => setDeletingFile(null);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [deletingFile]);

  // Fetch on mount
  useEffect(() => {
    fetchRosters();
  }, []);

  const fetchRosters = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await clientApiCall<{ files: RosterFile[] }>("/api/v1/rosters/list");
      const files = Array.isArray(data?.files) ? data.files : [];
      files.sort((a, b) => new Date(b.modified).getTime() - new Date(a.modified).getTime());
      setRosters(files);
    } catch (e: any) {
      setError(e?.message || "Failed to load rosters");
    } finally {
      setLoading(false);
    }
  };

  const generateRoster = async (type: "long" | "short") => {
    try {
      setGenerating(type);
      setError(null);
      setSuccess(null);
      const resp = await clientApiCall<GenerateResponse>(
        `/api/v1/rosters/generate?roster_type=${type}`,
        { method: "POST" }
      );
      if (resp?.success) {
        setSuccess(`Generated ${type === "long" ? "Long" : "Short"} Roster: ${resp.filename}`);
        await fetchRosters();
      } else {
        setError(resp?.error || "Failed to generate roster");
      }
    } catch (e: any) {
      setError(e?.message || "Failed to generate roster");
    } finally {
      setGenerating(null);
    }
  };

  const viewRoster = (filename: string) => {
    window.open(`/api/proxy/api/v1/rosters/download/${encodeURIComponent(filename)}`, "_blank");
  };


  const confirmDelete = async (filename: string) => {
    setError(null);
    setSuccess(null);
    
    try {
      const url = `/api/proxy/api/v1/rosters/${filename}`;
      
      const response = await fetch(url, {
        method: 'DELETE',
      });
      
      if (!response.ok) {
        const data = await response.json().catch(() => ({ error: 'Failed to delete' }));
        throw new Error(data.error || 'Failed to delete roster');
      }
      
      setSuccess('Roster deleted successfully');
      setDeletingFile(null);
      
      // Refresh the roster list
      await fetchRosters();
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      console.error('Delete error:', err);
      setError(err.message || 'Failed to delete roster');
      setDeletingFile(null);
    }
  };

  const content = useMemo(() => {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-500">Loading rosters...</span>
        </div>
      );
    }

    if (!rosters.length) {
      return (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <FileText className="h-12 w-12 text-gray-400 mb-4" />
          <p className="text-gray-500">No rosters generated yet</p>
          <p className="text-sm text-gray-400 mt-1">Click a button above to generate your first roster</p>
        </div>
      );
    }

    return (
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Filename</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date Modified</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {rosters.map((f) => (
              <tr key={f.name} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{f.name}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatDate(f.modified)}</td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <div className="flex items-center justify-end gap-4" onClick={(e) => e.stopPropagation()}>
                    <FileActions
                      viewHref={`/api/proxy/api/v1/rosters/download/${encodeURIComponent(f.name)}`}
                      isConfirming={deletingFile === f.name}
                      onRequestDelete={() => setDeletingFile(f.name)}
                      onConfirmDelete={() => confirmDelete(f.name)}
                      onCancel={() => setDeletingFile(null)}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }, [loading, rosters, deletingFile]);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Roster Management</h1>
          <p className="mt-2 text-gray-600">Generate and manage community rosters</p>
        </div>

        {/* Success/Error Messages */}
        {success && (
          <div className="mb-6 rounded-md border border-green-200 bg-green-50 p-4">
            <p className="text-green-800">{success}</p>
          </div>
        )}

        {error && (
          <div className="mb-6 rounded-md border border-red-200 bg-red-50 p-4">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Generation Section */}
        <div className="mb-8 bg-white rounded-lg shadow p-6">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Generate Roster</h2>
            <p className="text-sm text-gray-600">Choose the roster format to generate</p>
          </div>
          <div className="flex flex-col sm:flex-row gap-4">
            <button
              onClick={() => generateRoster("long")}
              disabled={generating !== null}
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-70"
            >
              {generating === "long" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Generate Long Form Roster
            </button>
            <button
              onClick={() => generateRoster("short")}
              disabled={generating !== null}
              className="flex-1 inline-flex items-center justify-center gap-2 rounded-md px-4 py-2 font-medium text-indigo-600 bg-white border border-indigo-200 hover:bg-indigo-50 disabled:opacity-70"
            >
              {generating === "short" && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Generate Short Form Roster
            </button>
          </div>
        </div>

        {/* File List */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 pt-6">
            <h2 className="text-lg font-semibold text-gray-900">Generated Rosters</h2>
            <p className="text-sm text-gray-600 mb-4">View or delete previously generated rosters</p>
          </div>
          <div className="px-6 pb-6">{content}</div>
        </div>
      </div>
    </div>
  );
}
