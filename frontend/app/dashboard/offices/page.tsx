"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import { api } from "@/lib/api";
import { type Body, type Office } from "@/lib/types";
import { Plus, Edit2, Trash2, CircleHelp } from "lucide-react";
import { Toast } from "@/components/toast";

interface OfficeFormData {
  title: string;
  office_precedence: number;
}

export default function BodiesOfficesPage() {
  const PRECEDENCE_HELP_TEXT =
    "This field sets where the office sorts when the roster is created. For example, to set the Treasurer to appear after the Secretary, set Treasurer precedence to 3 and Secretary precedence to 4. To insert a new office of Past Chair to appear between Vice Chair and Treasurer, set that new office's precedence to 2.5.";

  const [bodies, setBodies] = useState<Body[]>([]);
  const [offices, setOffices] = useState<Office[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selection state
  const [selectedBodyId, setSelectedBodyId] = useState<number | null>(null);

  // Offices panel state
  const [showCreateOffice, setShowCreateOffice] = useState(false);
  const [editingOfficeId, setEditingOfficeId] = useState<number | null>(null);
  const [officeFormData, setOfficeFormData] = useState<OfficeFormData>({
    title: "",
    office_precedence: 0,
  });
  const [officeSaving, setOfficeSaving] = useState(false);
  const [isPrecedenceHelpOpen, setIsPrecedenceHelpOpen] = useState(false);
  const precedenceHelpHeaderButtonRef = useRef<HTMLButtonElement | null>(null);
  const precedenceHelpPopoverRef = useRef<HTMLDivElement | null>(null);

  // Toast state
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (!isPrecedenceHelpOpen) return;

    const handleMouseDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        precedenceHelpHeaderButtonRef.current?.contains(target) ||
        precedenceHelpPopoverRef.current?.contains(target)
      ) {
        return;
      }
      setIsPrecedenceHelpOpen(false);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsPrecedenceHelpOpen(false);
      }
    };

    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isPrecedenceHelpOpen]);

  useEffect(() => {
    if (isPrecedenceHelpOpen) {
      precedenceHelpPopoverRef.current?.focus();
    }
  }, [isPrecedenceHelpOpen]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [bodiesData, officesData] = await Promise.all([
        api.getBodies(),
        api.getOffices(),
      ]);

      // Sort bodies alphabetically by name
      const sortedBodies = bodiesData.sort((a, b) => 
        a.name.localeCompare(b.name)
      );

      setBodies(sortedBodies);
      setOffices(officesData);

      // Auto-select first body if none selected
      if (!selectedBodyId && sortedBodies.length > 0) {
        setSelectedBodyId(sortedBodies[0].body_id);
      }

      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  // Filter offices for selected body
  const officesForSelectedBody = useMemo(() => {
    if (!selectedBodyId) return [];
    return offices
      .filter((o) => o.office_body_id === selectedBodyId)
      .sort((a, b) => (a.office_precedence || 0) - (b.office_precedence || 0));
  }, [offices, selectedBodyId]);

  // Office CRUD handlers
  const handleCreateOffice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedBodyId) return;
    if (!officeFormData.title.trim()) {
      setToast({ message: "Office title is required", type: "error" });
      return;
    }

    try {
      setOfficeSaving(true);
      await api.createOffice({
        ...officeFormData,
        office_body_id: selectedBodyId,
      });
      setToast({ message: "Office created successfully!", type: "success" });
      setShowCreateOffice(false);
      setOfficeFormData({ title: "", office_precedence: 0 });
      await loadData();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to create office",
        type: "error",
      });
    } finally {
      setOfficeSaving(false);
    }
  };

  const handleEditOffice = (office: Office) => {
    setEditingOfficeId(office.office_id);
    setOfficeFormData({
      title: office.title || "",
      office_precedence: office.office_precedence || 0,
    });
  };

  const handleSaveOffice = async (officeId: number) => {
    if (!officeFormData.title.trim()) {
      setToast({ message: "Office title is required", type: "error" });
      return;
    }

    try {
      setOfficeSaving(true);
      await api.updateOffice(officeId, officeFormData);
      setToast({ message: "Office updated successfully!", type: "success" });
      setEditingOfficeId(null);
      await loadData();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to update office",
        type: "error",
      });
    } finally {
      setOfficeSaving(false);
    }
  };

  const handleDeleteOffice = async (officeId: number) => {
    if (!confirm("Are you sure you want to delete this office?")) return;

    try {
      await api.deleteOffice(officeId);
      setToast({ message: "Office deleted successfully!", type: "success" });
      await loadData();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to delete office",
        type: "error",
      });
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
        Error: {error}
      </div>
    );
  }

  return (
    <div className="px-4 sm:px-0">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Offices</h1>
        <p className="mt-2 text-sm text-gray-700">
          Select a body and manage its offices
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Panel: Bodies */}
        <div className="md:col-span-1">
          <div className="bg-white rounded-lg shadow">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Bodies</h2>
            </div>

            <div className="p-4">
              {/* Bodies List */}
              {bodies.length === 0 ? (
                <div className="text-center py-6 text-gray-500">No bodies found</div>
              ) : (
                <ul className="divide-y divide-gray-200">
                  {bodies.map((body) => (
                    <li key={body.body_id}>
                      <button
                        onClick={() => setSelectedBodyId(body.body_id)}
                        className={`w-full text-left px-3 py-3 hover:bg-gray-50 transition-colors ${
                          selectedBodyId === body.body_id
                            ? "bg-blue-50 border-l-4 border-blue-500"
                            : ""
                        }`}
                      >
                        <div className="font-medium text-gray-900">{body.name}</div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>

        {/* Right Panel: Offices */}
        <div className="md:col-span-2">
          <div className="bg-white rounded-lg shadow">
            <div className="p-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Offices</h2>
                <button
                  onClick={() => setShowCreateOffice(!showCreateOffice)}
                  disabled={!selectedBodyId}
                  className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Plus className="w-4 h-4 mr-1" />
                  Add Office
                </button>
              </div>
            </div>

            <div className="p-4">
              {!selectedBodyId ? (
                <div className="text-center py-12 text-gray-500">
                  Select a body on the left to manage its offices
                </div>
              ) : (
                <>
                  {/* Create Office Form */}
                  {showCreateOffice && (
                    <form onSubmit={handleCreateOffice} className="mb-4 p-3 border border-gray-200 rounded-md bg-gray-50">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Title *
                          </label>
                          <input
                            type="text"
                            value={officeFormData.title}
                            onChange={(e) => setOfficeFormData({ ...officeFormData, title: e.target.value })}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                            required
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Precedence *
                          </label>
                          <input
                            type="number"
                            value={officeFormData.office_precedence}
                            onChange={(e) => setOfficeFormData({ ...officeFormData, office_precedence: e.target.value === "" ? 0 : parseFloat(e.target.value) })}
                            step="0.1"
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                            required
                          />
                        </div>
                      </div>
                      <div className="mt-3 flex gap-2">
                        <button
                          type="submit"
                          disabled={officeSaving}
                          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-md disabled:opacity-50"
                        >
                          {officeSaving ? "Saving..." : "Save"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setShowCreateOffice(false);
                            setOfficeFormData({ title: "", office_precedence: 0 });
                          }}
                          className="px-3 py-1.5 bg-gray-200 hover:bg-gray-300 text-gray-800 text-sm font-medium rounded-md"
                        >
                          Cancel
                        </button>
                      </div>
                    </form>
                  )}

                  {/* Offices Table */}
                  {officesForSelectedBody.length === 0 ? (
                    <div className="text-center py-6 text-gray-500">
                      No offices for this body
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Title
                            </th>
                            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                              <div className="relative inline-flex items-center gap-1">
                                <span>Precedence</span>
                                <button
                                  type="button"
                                  ref={precedenceHelpHeaderButtonRef}
                                  aria-label="Help: Precedence"
                                  aria-expanded={isPrecedenceHelpOpen}
                                  aria-controls="precedence-help-popover"
                                  aria-haspopup="dialog"
                                  onClick={() => setIsPrecedenceHelpOpen((open) => !open)}
                                  onKeyDown={(event) => {
                                    if (event.key === "Enter" || event.key === " ") {
                                      event.preventDefault();
                                      setIsPrecedenceHelpOpen((open) => !open);
                                    }
                                  }}
                                  className="inline-flex items-center justify-center text-gray-500 hover:text-gray-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 rounded ms-1 align-middle"
                                >
                                  <CircleHelp className="w-4 h-4" />
                                </button>
                                {isPrecedenceHelpOpen && (
                                  <div
                                    ref={precedenceHelpPopoverRef}
                                    id="precedence-help-popover"
                                    tabIndex={-1}
                                    className="absolute left-0 top-full mt-2 w-96 max-w-[24rem] text-sm leading-snug text-gray-700 bg-white border border-gray-200 rounded-lg shadow-lg p-3 z-50 normal-case"
                                    role="dialog"
                                    aria-live="polite"
                                  >
                                    {PRECEDENCE_HELP_TEXT}
                                  </div>
                                )}
                              </div>
                            </th>
                            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                              Actions
                            </th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {officesForSelectedBody.map((office) => (
                            <tr key={office.office_id} className="hover:bg-gray-50">
                              <td className="px-4 py-3">
                                {editingOfficeId === office.office_id ? (
                                  <input
                                    type="text"
                                    value={officeFormData.title}
                                    onChange={(e) => setOfficeFormData({ ...officeFormData, title: e.target.value })}
                                    className="w-full px-2 py-1 border border-gray-300 rounded text-gray-900"
                                  />
                                ) : (
                                  <span className="text-gray-900">{office.title}</span>
                                )}
                              </td>
                              <td className="px-4 py-3">
                                {editingOfficeId === office.office_id ? (
                                  <input
                                    type="number"
                                    value={officeFormData.office_precedence}
                                    onChange={(e) => setOfficeFormData({ ...officeFormData, office_precedence: e.target.value === "" ? 0 : parseFloat(e.target.value) })}
                                    step="0.1"
                                    className="w-32 px-2 py-1 border border-gray-300 rounded text-gray-900"
                                  />
                                ) : (
                                  <span className="text-gray-900">{office.office_precedence}</span>
                                )}
                              </td>
                              <td className="px-4 py-3 text-right">
                                {editingOfficeId === office.office_id ? (
                                  <div className="inline-flex items-center gap-2">
                                    <button
                                      onClick={() => handleSaveOffice(office.office_id)}
                                      disabled={officeSaving}
                                      className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded disabled:opacity-50"
                                    >
                                      {officeSaving ? "Saving..." : "Save"}
                                    </button>
                                    <button
                                      onClick={() => setEditingOfficeId(null)}
                                      className="px-3 py-1 bg-gray-200 hover:bg-gray-300 text-gray-800 text-sm rounded"
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                ) : (
                                  <div className="inline-flex items-center gap-2">
                                    <button
                                      onClick={() => handleEditOffice(office)}
                                      className="text-blue-600 hover:text-blue-900"
                                      title="Edit"
                                    >
                                      <Edit2 className="w-4 h-4" />
                                    </button>
                                    <button
                                      onClick={() => handleDeleteOffice(office.office_id)}
                                      className="text-red-600 hover:text-red-900"
                                      title="Delete"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </button>
                                  </div>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Toast Notification */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
}
