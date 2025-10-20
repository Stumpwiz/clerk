"use client";

import { useEffect, useMemo, useState } from "react";
import { clientApiCall } from "@/lib/client-api";
import { Loader2 } from "lucide-react";

// Types
interface Body {
  body_id: number;
  name: string;
  mission?: string | null;
  body_precedence: number;
}

interface Office {
  office_id: number;
  title: string;
  office_precedence: number;
  office_body_id: number;
}

// Editable helpers
interface EditableBody {
  name: string;
  mission: string;
  body_precedence: string; // keep as string for inputs, validate as number
}

interface EditableOffice {
  title: string;
  office_precedence: string; // string for input
}

function toEditableBody(b?: Partial<Body>): EditableBody {
  return {
    name: (b?.name ?? "").toString(),
    mission: (b?.mission ?? "").toString(),
    body_precedence: (b?.body_precedence ?? "").toString(),
  };
}

function toEditableOffice(o?: Partial<Office>): EditableOffice {
  return {
    title: (o?.title ?? "").toString(),
    office_precedence: (o?.office_precedence ?? "").toString(),
  };
}

export default function BodiesOfficesPage() {
  // Data
  const [bodies, setBodies] = useState<Body[]>([]);
  const [offices, setOffices] = useState<Office[]>([]);

  // Status & alerts
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  // Selection
  const [selectedBodyId, setSelectedBodyId] = useState<number | null>(null);

  // Filter/search
  const [bodyQuery, setBodyQuery] = useState("");

  // Bodies panel state
  const [showCreateBody, setShowCreateBody] = useState(false);
  const [createBodySaving, setCreateBodySaving] = useState(false);
  const [createBodyForm, setCreateBodyForm] = useState<EditableBody>(toEditableBody());

  const [editingBodyId, setEditingBodyId] = useState<number | null>(null);
  const [editBodySavingId, setEditBodySavingId] = useState<number | null>(null);
  const [editBodyForm, setEditBodyForm] = useState<EditableBody>(toEditableBody());

  const [confirmDeleteBodyId, setConfirmDeleteBodyId] = useState<number | null>(null);
  const [deletingBodyId, setDeletingBodyId] = useState<number | null>(null);

  // Offices panel state
  const [showCreateOffice, setShowCreateOffice] = useState(false);
  const [createOfficeSaving, setCreateOfficeSaving] = useState(false);
  const [createOfficeForm, setCreateOfficeForm] = useState<EditableOffice>(toEditableOffice());

  const [editingOfficeId, setEditingOfficeId] = useState<number | null>(null);
  const [editOfficeSavingId, setEditOfficeSavingId] = useState<number | null>(null);
  const [editOfficeForm, setEditOfficeForm] = useState<EditableOffice>(toEditableOffice());

  const [confirmDeleteOfficeId, setConfirmDeleteOfficeId] = useState<number | null>(null);
  const [deletingOfficeId, setDeletingOfficeId] = useState<number | null>(null);

  // Auto-dismiss alerts
  useEffect(() => {
    if (success) {
      const t = setTimeout(() => setSuccess(null), 4000);
      return () => clearTimeout(t);
    }
  }, [success]);
  useEffect(() => {
    if (error) {
      const t = setTimeout(() => setError(null), 5000);
      return () => clearTimeout(t);
    }
  }, [error]);
  useEffect(() => {
    if (info) {
      const t = setTimeout(() => setInfo(null), 4000);
      return () => clearTimeout(t);
    }
  }, [info]);

  // Click-away cancel for delete confirms
  useEffect(() => {
    if (!confirmDeleteBodyId && !confirmDeleteOfficeId) return;
    const handler = () => {
      setConfirmDeleteBodyId(null);
      setConfirmDeleteOfficeId(null);
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [confirmDeleteBodyId, confirmDeleteOfficeId]);

  // Load data
  useEffect(() => {
    fetchAll();
  }, []);

  async function fetchAll() {
    try {
      setLoading(true);
      setError(null);
      const [b, o] = await Promise.all([
        clientApiCall<Body[]>("/api/v1/bodies"),
        clientApiCall<Office[]>("/api/v1/offices"),
      ]);
      const sortedBodies = (Array.isArray(b) ? b : []).slice().sort((x, y) => {
        const p = (x.body_precedence ?? 0) - (y.body_precedence ?? 0);
        if (p !== 0) return p;
        return (x.name || "").localeCompare(y.name || "");
      });
      setBodies(sortedBodies);
      setOffices(Array.isArray(o) ? o : []);

      if (selectedBodyId != null) {
        const stillExists = sortedBodies.some((bb) => bb.body_id === selectedBodyId);
        if (!stillExists) {
          setSelectedBodyId(null);
          setInfo("Selected body was deleted. Selection cleared.");
        }
      }
    } catch (e: any) {
      setError(e?.message || "Failed to load bodies and offices");
    } finally {
      setLoading(false);
    }
  }

  // Derived
  const filteredBodies = useMemo(() => {
    const q = bodyQuery.trim().toLowerCase();
    const list = bodies;
    if (!q) return list;
    return list.filter((b) => (b.name || "").toLowerCase().includes(q));
  }, [bodies, bodyQuery]);

  const officesForSelected = useMemo(() => {
    if (selectedBodyId == null) return [] as Office[];
    const list = offices.filter((o) => o.office_body_id === selectedBodyId);
    return list.sort((a, b) => {
      const p = (a.office_precedence ?? 0) - (b.office_precedence ?? 0);
      if (p !== 0) return p;
      return (a.title || "").localeCompare(b.title || "");
    });
  }, [offices, selectedBodyId]);

  // Validation helpers
  function validateBody(form: EditableBody): { ok: boolean; message?: string } {
    const name = form.name.trim();
    const mission = form.mission.trim();
    const precStr = form.body_precedence.trim();
    if (!name) return { ok: false, message: "Body name is required" };
    if (name.length > 45) return { ok: false, message: "Name must be at most 45 characters" };
    if (mission.length > 512) return { ok: false, message: "Mission must be at most 512 characters" };
    if (!precStr) return { ok: false, message: "Precedence is required" };
    const prec = Number(precStr);
    if (Number.isNaN(prec)) return { ok: false, message: "Precedence must be a number" };
    return { ok: true };
  }

  function bodyPayload(form: EditableBody) {
    const prec = Number(form.body_precedence.trim());
    return {
      name: form.name.trim(),
      mission: form.mission.trim() || null,
      body_precedence: prec,
    };
  }

  function validateOffice(form: EditableOffice): { ok: boolean; message?: string } {
    const title = form.title.trim();
    const precStr = form.office_precedence.trim();
    if (!title) return { ok: false, message: "Office title is required" };
    if (title.length > 45) return { ok: false, message: "Title must be at most 45 characters" };
    if (!precStr) return { ok: false, message: "Precedence is required" };
    const prec = Number(precStr);
    if (Number.isNaN(prec)) return { ok: false, message: "Precedence must be a number" };
    return { ok: true };
  }

  function officePayload(form: EditableOffice, office_body_id: number) {
    const prec = Number(form.office_precedence.trim());
    return {
      title: form.title.trim(),
      office_precedence: prec,
      office_body_id,
    };
  }

  // Bodies CRUD
  async function createBody() {
    const v = validateBody(createBodyForm);
    if (!v.ok) {
      setError(v.message || "Invalid body form");
      return;
    }
    try {
      setCreateBodySaving(true);
      setError(null);
      setSuccess(null);
      const resp = await clientApiCall<Body>("/api/v1/bodies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bodyPayload(createBodyForm)),
      });
      setSuccess("Body created successfully");
      setShowCreateBody(false);
      setCreateBodyForm(toEditableBody());
      await fetchAll();
      // Select the created body
      if (resp?.body_id) setSelectedBodyId(resp.body_id);
    } catch (e: any) {
      setError(e?.message || "Failed to create body");
    } finally {
      setCreateBodySaving(false);
    }
  }

  function beginEditBody(b: Body) {
    setEditingBodyId(b.body_id);
    setEditBodyForm(toEditableBody(b));
  }
  function cancelEditBody() {
    setEditingBodyId(null);
    setEditBodyForm(toEditableBody());
  }
  async function saveEditBody(id: number) {
    const v = validateBody(editBodyForm);
    if (!v.ok) {
      setError(v.message || "Invalid body form");
      return;
    }
    try {
      setEditBodySavingId(id);
      setError(null);
      setSuccess(null);
      await clientApiCall<Body>(`/api/v1/bodies/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bodyPayload(editBodyForm)),
      });
      setSuccess("Body updated successfully");
      setEditingBodyId(null);
      await fetchAll();
      // keep selection
      setSelectedBodyId((prev) => (prev === null ? id : prev));
    } catch (e: any) {
      setError(e?.message || "Failed to update body");
    } finally {
      setEditBodySavingId(null);
    }
  }

  async function deleteBody(id: number) {
    try {
      setDeletingBodyId(id);
      setError(null);
      setSuccess(null);
      await clientApiCall(`/api/v1/bodies/${id}`, { method: "DELETE" });
      setSuccess("Body deleted successfully");
      setConfirmDeleteBodyId(null);
      if (selectedBodyId === id) {
        setSelectedBodyId(null);
        setInfo("Selected body was deleted. Selection cleared.");
      }
      await fetchAll();
    } catch (e: any) {
      const msg = e?.message || "Failed to delete body";
      const friendly = /constraint|offices|foreign key|still has/i.test(msg)
        ? "This body cannot be deleted because it still has offices."
        : msg;
      setError(friendly);
    } finally {
      setDeletingBodyId(null);
    }
  }

  // Offices CRUD
  async function createOffice() {
    if (selectedBodyId == null) return;
    const v = validateOffice(createOfficeForm);
    if (!v.ok) {
      setError(v.message || "Invalid office form");
      return;
    }
    try {
      setCreateOfficeSaving(true);
      setError(null);
      setSuccess(null);
      await clientApiCall<Office>("/api/v1/offices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(officePayload(createOfficeForm, selectedBodyId)),
      });
      setSuccess("Office created successfully");
      setShowCreateOffice(false);
      setCreateOfficeForm(toEditableOffice());
      await fetchAll();
    } catch (e: any) {
      setError(e?.message || "Failed to create office");
    } finally {
      setCreateOfficeSaving(false);
    }
  }

  function beginEditOffice(o: Office) {
    setEditingOfficeId(o.office_id);
    setEditOfficeForm(toEditableOffice(o));
  }
  function cancelEditOffice() {
    setEditingOfficeId(null);
    setEditOfficeForm(toEditableOffice());
  }
  async function saveEditOffice(id: number) {
    const v = validateOffice(editOfficeForm);
    if (!v.ok) {
      setError(v.message || "Invalid office form");
      return;
    }
    try {
      setEditOfficeSavingId(id);
      setError(null);
      setSuccess(null);
      await clientApiCall<Office>(`/api/v1/offices/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: editOfficeForm.title.trim(),
          office_precedence: Number(editOfficeForm.office_precedence.trim()),
        }),
      });
      setSuccess("Office updated successfully");
      setEditingOfficeId(null);
      await fetchAll();
    } catch (e: any) {
      setError(e?.message || "Failed to update office");
    } finally {
      setEditOfficeSavingId(null);
    }
  }

  async function deleteOffice(id: number) {
    try {
      setDeletingOfficeId(id);
      setError(null);
      setSuccess(null);
      await clientApiCall(`/api/v1/offices/${id}`, { method: "DELETE" });
      setSuccess("Office deleted successfully");
      setConfirmDeleteOfficeId(null);
      await fetchAll();
    } catch (e: any) {
      const msg = e?.message || "Failed to delete office";
      const friendly = /constraint|term|assigned|foreign key/i.test(msg)
        ? "This office cannot be deleted because it has assigned terms."
        : msg;
      setError(friendly);
    } finally {
      setDeletingOfficeId(null);
    }
  }

  // Quick reorder: adjust precedence and persist
  async function nudgeOffice(id: number, delta: number) {
    const target = offices.find((o) => o.office_id === id);
    if (!target) return;
    const newPrec = (target.office_precedence ?? 0) + delta;
    // Optimistic: update local first
    setOffices((prev) => prev.map((o) => (o.office_id === id ? { ...o, office_precedence: newPrec } : o)));
    try {
      await clientApiCall<Office>(`/api/v1/offices/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ office_precedence: newPrec }),
      });
      setSuccess("Office order updated");
      // refresh to normalize ordering
      await fetchAll();
    } catch (e: any) {
      setError(e?.message || "Failed to reorder office");
      // revert by refetch
      await fetchAll();
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Bodies & Offices</h1>
          <p className="text-gray-600">Manage bodies and the positions within them</p>
        </div>

        {/* Alerts */}
        {success && (
          <div className="mb-4 rounded-md bg-green-50 border border-green-200 text-green-800 px-4 py-3" role="status">{success}</div>
        )}
        {info && (
          <div className="mb-4 rounded-md bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3" role="status">{info}</div>
        )}
        {error && (
          <div className="mb-4 rounded-md bg-red-50 border border-red-200 text-red-800 px-4 py-3" role="alert">{error}</div>
        )}

        {/* Panels */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Bodies (approx 35%) */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">Bodies</h2>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setShowCreateBody((s) => !s); }}
                  className="inline-flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white font-medium px-3 py-1.5 rounded-md"
                >
                  Create Body
                </button>
              </div>

              {/* Search */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="body-search">Search bodies</label>
                <input
                  id="body-search"
                  type="text"
                  value={bodyQuery}
                  onChange={(e) => setBodyQuery(e.target.value)}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Type to filter by name"
                />
              </div>

              {/* Create body form */}
              {showCreateBody && (
                <div className="mb-6 border border-gray-200 rounded-md p-4">
                  <div className="grid grid-cols-1 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Name<span className="text-red-500">*</span></label>
                      <input
                        value={createBodyForm.name}
                        onChange={(e) => setCreateBodyForm({ ...createBodyForm, name: e.target.value })}
                        maxLength={45}
                        className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Mission</label>
                      <textarea
                        value={createBodyForm.mission}
                        onChange={(e) => setCreateBodyForm({ ...createBodyForm, mission: e.target.value })}
                        maxLength={512}
                        className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        rows={3}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Precedence<span className="text-red-500">*</span></label>
                      <input
                        value={createBodyForm.body_precedence}
                        onChange={(e) => setCreateBodyForm({ ...createBodyForm, body_precedence: e.target.value })}
                        inputMode="decimal"
                        className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="e.g., 1 or 1.5"
                      />
                    </div>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={createBody}
                      disabled={createBodySaving}
                      className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium px-3 py-1.5 rounded-md"
                    >
                      {createBodySaving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                      Save
                    </button>
                    <button
                      onClick={() => { setShowCreateBody(false); setCreateBodyForm(toEditableBody()); }}
                      className="inline-flex items-center gap-2 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium px-3 py-1.5 rounded-md"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Bodies list */}
              {loading ? (
                <div className="flex items-center justify-center py-8 text-gray-500"><Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading…</div>
              ) : filteredBodies.length === 0 ? (
                <div className="text-gray-600 py-6 text-center">No bodies found</div>
              ) : (
                <ul className="divide-y divide-gray-200" role="list">
                  {filteredBodies.map((b) => (
                    <li key={b.body_id} className={`py-3 ${selectedBodyId === b.body_id ? "bg-blue-50" : ""}`}>
                      {editingBodyId === b.body_id ? (
                        <div className="space-y-2">
                          <input
                            aria-label="Body name"
                            value={editBodyForm.name}
                            onChange={(e) => setEditBodyForm({ ...editBodyForm, name: e.target.value })}
                            maxLength={45}
                            className="w-full rounded-md border border-gray-300 px-2 py-1"
                          />
                          <textarea
                            aria-label="Body mission"
                            value={editBodyForm.mission}
                            onChange={(e) => setEditBodyForm({ ...editBodyForm, mission: e.target.value })}
                            maxLength={512}
                            rows={2}
                            className="w-full rounded-md border border-gray-300 px-2 py-1"
                          />
                          <input
                            aria-label="Body precedence"
                            value={editBodyForm.body_precedence}
                            onChange={(e) => setEditBodyForm({ ...editBodyForm, body_precedence: e.target.value })}
                            inputMode="decimal"
                            className="w-full rounded-md border border-gray-300 px-2 py-1"
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => saveEditBody(b.body_id)}
                              disabled={editBodySavingId === b.body_id}
                              className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded disabled:opacity-60"
                            >
                              {editBodySavingId === b.body_id ? <Loader2 className="h-4 w-4 animate-spin inline" /> : null} Save
                            </button>
                            <button className="bg-gray-200 hover:bg-gray-300 text-gray-800 px-3 py-1.5 rounded" onClick={cancelEditBody}>Cancel</button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-start justify-between gap-3">
                          <button
                            onClick={() => setSelectedBodyId(b.body_id)}
                            className="text-left flex-1"
                            aria-label={`Select body ${b.name}`}
                          >
                            <div className="font-medium text-gray-900">{b.name}</div>
                            {b.mission ? (
                              <div className="text-sm text-gray-600 line-clamp-2">{b.mission}</div>
                            ) : null}
                            <div className="text-xs text-gray-500 mt-0.5">Precedence: {b.body_precedence}</div>
                          </button>
                          <div className="shrink-0 inline-flex items-center gap-2">
                            <button
                              onClick={(e) => { e.stopPropagation(); setConfirmDeleteBodyId(null); beginEditBody(b); }}
                              className="bg-blue-50 hover:bg-blue-100 text-blue-700 px-3 py-1.5 rounded-md border border-blue-200"
                            >
                              Edit
                            </button>
                            {confirmDeleteBodyId === b.body_id ? (
                              <button
                                onClick={(e) => { e.stopPropagation(); deleteBody(b.body_id); }}
                                disabled={deletingBodyId === b.body_id}
                                className="bg-red-600 hover:bg-red-700 text-white px-3 py-1.5 rounded-md disabled:opacity-60"
                              >
                                {deletingBodyId === b.body_id ? <Loader2 className="h-4 w-4 animate-spin inline" /> : null} Confirm
                              </button>
                            ) : (
                              <button
                                onClick={(e) => { e.stopPropagation(); setConfirmDeleteBodyId(b.body_id); }}
                                className="bg-red-50 hover:bg-red-100 text-red-700 px-3 py-1.5 rounded-md border border-red-200"
                              >
                                Delete
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Right: Offices (approx 65%) */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-900">Offices</h2>
                <button
                  type="button"
                  disabled={selectedBodyId == null}
                  onClick={(e) => { e.stopPropagation(); setShowCreateOffice((s) => !s); }}
                  className={`inline-flex items-center gap-2 ${selectedBodyId == null ? "opacity-60 cursor-not-allowed" : "bg-green-600 hover:bg-green-700"} text-white font-medium px-3 py-1.5 rounded-md`}
                  aria-disabled={selectedBodyId == null}
                >
                  Add Office
                </button>
              </div>

              {selectedBodyId == null ? (
                <div className="text-gray-600 py-12 text-center">
                  Select a body on the left to manage its offices, or create a new body.
                </div>
              ) : (
                <>
                  {/* Create office form */}
                  {showCreateOffice && (
                    <div className="mb-6 border border-gray-200 rounded-md p-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Title<span className="text-red-500">*</span></label>
                          <input
                            value={createOfficeForm.title}
                            onChange={(e) => setCreateOfficeForm({ ...createOfficeForm, title: e.target.value })}
                            maxLength={45}
                            className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Precedence<span className="text-red-500">*</span></label>
                          <input
                            value={createOfficeForm.office_precedence}
                            onChange={(e) => setCreateOfficeForm({ ...createOfficeForm, office_precedence: e.target.value })}
                            inputMode="decimal"
                            className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="e.g., 1 or 1.5"
                          />
                        </div>
                      </div>
                      <div className="mt-3 flex gap-2">
                        <button
                          onClick={createOffice}
                          disabled={createOfficeSaving}
                          className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium px-3 py-1.5 rounded-md"
                        >
                          {createOfficeSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                          Save
                        </button>
                        <button
                          onClick={() => { setShowCreateOffice(false); setCreateOfficeForm(toEditableOffice()); }}
                          className="inline-flex items-center gap-2 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium px-3 py-1.5 rounded-md"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Offices table */}
                  {loading ? (
                    <div className="flex items-center justify-center py-8 text-gray-500"><Loader2 className="h-5 w-5 animate-spin mr-2" /> Loading…</div>
                  ) : officesForSelected.length === 0 ? (
                    <div className="text-gray-600 py-6 text-center">No offices for this body</div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Title</th>
                            <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Precedence</th>
                            <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 bg-white">
                          {officesForSelected.map((o) => (
                            <tr key={o.office_id} className="hover:bg-gray-50">
                              {/* Title */}
                              <td className="px-4 py-3 align-top">
                                {editingOfficeId === o.office_id ? (
                                  <input
                                    aria-label="Office title"
                                    value={editOfficeForm.title}
                                    onChange={(e) => setEditOfficeForm({ ...editOfficeForm, title: e.target.value })}
                                    maxLength={45}
                                    className="w-full rounded-md border border-gray-300 px-2 py-1"
                                  />
                                ) : (
                                  <span className="text-gray-900">{o.title}</span>
                                )}
                              </td>
                              {/* Precedence */}
                              <td className="px-4 py-3 align-top">
                                {editingOfficeId === o.office_id ? (
                                  <input
                                    aria-label="Office precedence"
                                    value={editOfficeForm.office_precedence}
                                    onChange={(e) => setEditOfficeForm({ ...editOfficeForm, office_precedence: e.target.value })}
                                    inputMode="decimal"
                                    className="w-32 rounded-md border border-gray-300 px-2 py-1"
                                  />
                                ) : (
                                  <span className="text-gray-900">{o.office_precedence}</span>
                                )}
                              </td>
                              {/* Actions */}
                              <td className="px-4 py-3 align-top text-right whitespace-nowrap">
                                {editingOfficeId === o.office_id ? (
                                  <div className="inline-flex items-center gap-2">
                                    <button
                                      onClick={() => saveEditOffice(o.office_id)}
                                      disabled={editOfficeSavingId === o.office_id}
                                      className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white px-3 py-1.5 rounded-md"
                                    >
                                      {editOfficeSavingId === o.office_id ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                                      Save
                                    </button>
                                    <button
                                      onClick={cancelEditOffice}
                                      className="inline-flex items-center gap-2 bg-gray-200 hover:bg-gray-300 text-gray-800 px-3 py-1.5 rounded-md"
                                    >
                                      Cancel
                                    </button>
                                  </div>
                                ) : (
                                  <div className="inline-flex items-center gap-2">
                                    <button
                                      onClick={(e) => { e.stopPropagation(); setConfirmDeleteOfficeId(null); beginEditOffice(o); }}
                                      className="inline-flex items-center gap-2 bg-blue-50 hover:bg-blue-100 text-blue-700 px-3 py-1.5 rounded-md border border-blue-200"
                                    >
                                      Edit
                                    </button>
                                    {/* Reorder */}
                                    <div className="inline-flex items-center gap-1">
                                      <button
                                        aria-label="Move up"
                                        title="Move up"
                                        onClick={(e) => { e.stopPropagation(); nudgeOffice(o.office_id, -0.5); }}
                                        className="px-2 py-1 rounded-md border border-gray-200 hover:bg-gray-100"
                                      >
                                        ↑
                                      </button>
                                      <button
                                        aria-label="Move down"
                                        title="Move down"
                                        onClick={(e) => { e.stopPropagation(); nudgeOffice(o.office_id, +0.5); }}
                                        className="px-2 py-1 rounded-md border border-gray-200 hover:bg-gray-100"
                                      >
                                        ↓
                                      </button>
                                    </div>
                                    {confirmDeleteOfficeId === o.office_id ? (
                                      <button
                                        onClick={(e) => { e.stopPropagation(); deleteOffice(o.office_id); }}
                                        disabled={deletingOfficeId === o.office_id}
                                        className="inline-flex items-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white px-3 py-1.5 rounded-md"
                                      >
                                        {deletingOfficeId === o.office_id ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                                        Confirm
                                      </button>
                                    ) : (
                                      <button
                                        onClick={(e) => { e.stopPropagation(); setConfirmDeleteOfficeId(o.office_id); }}
                                        className="inline-flex items-center gap-2 bg-red-50 hover:bg-red-100 text-red-700 px-3 py-1.5 rounded-md border border-red-200"
                                      >
                                        Delete
                                      </button>
                                    )}
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
      </main>
    </div>
  );
}
