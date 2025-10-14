"use client";

import { useState } from "react";
import { letterApi, type PDFListItem } from "@/lib/client-api";

interface Props {
  pdfs: PDFListItem[];
  onDelete: (filename: string) => Promise<void>;
}

export default function PDFList({ pdfs, onDelete }: Props) {
  const [deleting, setDeleting] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const handleDelete = async (filename: string) => {
    try {
      setDeleting(filename);
      await onDelete(filename);
      setConfirmDelete(null);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setDeleting(null);
    }
  };

  const formatDate = (isoDate: string) => {
    return new Date(isoDate).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="rounded-lg bg-white shadow p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">
        📄 Generated Letters ({pdfs.length})
      </h2>

      {pdfs.length === 0 ? (
        <p className="text-gray-500 text-center py-8">
          No letters generated yet. Use the form above to create one.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-900">
                  Filename
                </th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-900">
                  Created
                </th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-900">
                  Size
                </th>
                <th className="px-4 py-3 text-right text-sm font-semibold text-gray-900">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {pdfs.map((pdf) => (
                <tr key={pdf.filename} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {pdf.filename}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {formatDate(pdf.created)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {formatSize(pdf.size)}
                  </td>
                  <td className="px-4 py-3 text-sm text-right space-x-2">
                    <a
                      href={letterApi.getPDFUrl(pdf.filename)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center text-blue-600 hover:text-blue-800 font-medium"
                    >
                      View
                    </a>
                    
                    {confirmDelete === pdf.filename ? (
                      <>
                        <button
                          onClick={() => handleDelete(pdf.filename)}
                          disabled={deleting === pdf.filename}
                          className="text-red-600 hover:text-red-800 font-medium"
                        >
                          {deleting === pdf.filename ? "Deleting..." : "Confirm"}
                        </button>
                        <button
                          onClick={() => setConfirmDelete(null)}
                          className="text-gray-600 hover:text-gray-800 font-medium"
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => setConfirmDelete(pdf.filename)}
                        className="text-red-600 hover:text-red-800 font-medium"
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
