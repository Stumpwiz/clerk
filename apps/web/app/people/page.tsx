"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { clientApiCall } from "@/lib/client-api";
import { Loader2, UserPlus } from "lucide-react";

interface Person {
  personid: number;
  first?: string | null;
  last?: string | null;
  email?: string | null;
  phone?: string | null;
  apt?: string | null;
}

interface EditablePerson {
  first: string;
  last: string;
  email: string;
  phone: string;
  apt: string;
}

function toEditable(p?: Partial<Person>): EditablePerson {
  return {
    first: (p?.first ?? "").toString(),
    last: (p?.last ?? "").toString(),
    email: (p?.email ?? "").toString(),
    phone: (p?.phone ?? "").toString(),
    apt: (p?.apt ?? "").toString(),
  };
}

function validatePerson(p: EditablePerson): { ok: boolean; message?: string } {
  const first = p.first.trim();
  const last = p.last.trim();
  const email = p.email.trim();
  const phone = p.phone.trim();
  const apt = p.apt.trim();

  if (!first) return { ok: false, message: "First name is required" };
  if (!last) return { ok: false, message: "Last name is required" };
  if (first.length > 15) return { ok: false, message: "First name must be at most 15 characters" };
  if (last.length > 30) return { ok: false, message: "Last name must be at most 30 characters" };
  if (email.length > 45) return { ok: false, message: "Email must be at most 45 characters" };
  if (phone.length > 19) return { ok: false, message: "Phone must be at most 19 characters" };
  if (apt.length > 4) return { ok: false, message: "Apartment must be at most 4 characters" };

  return { ok: true };
}

function trimmedPayload(p: EditablePerson) {
  return {
    first: p.first.trim() || null,
    last: p.last.trim() || null,
    email: p.email.trim() || null,
    phone: p.phone.trim() || null,
    apt: p.apt.trim() || null,
  };
}

export default function PeoplePage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState<EditablePerson>(toEditable());

  // Edit row states
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditablePerson>(toEditable());
  const [savingEditId, setSavingEditId] = useState<number | null>(null);

  // Delete confirm state
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // Vacancy placeholder warning modal state
  const [vacancyModal, setVacancyModal] = useState<{
    type: "edit" | "delete";
    person: Person;
  } | null>(null);

  // Click-away to cancel delete confirm
  useEffect(() => {
    if (confirmDeleteId == null) return;
    const handler = () => setConfirmDeleteId(null);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [confirmDeleteId]);

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
    fetchPeople();
  }, []);

  const fetchPeople = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await clientApiCall<Person[]>("/api/v1/persons");
      const list = Array.isArray(data) ? data : [];
      // Client-side sort: First (asc, case-insensitive) then Last; stable tie-breaker by personid
      const norm = (s?: string | null) => (s ?? "").trim().toLowerCase();
      list.sort((a, b) => {
        const firstCmp = norm(a.first).localeCompare(norm(b.first));
        if (firstCmp !== 0) return firstCmp;
        const lastCmp = norm(a.last).localeCompare(norm(b.last));
        if (lastCmp !== 0) return lastCmp;
        return (a.personid || 0) - (b.personid || 0);
      });
      setPeople(list);
    } catch (e: any) {
      setError(e?.message || "Failed to load persons");
    } finally {
      setLoading(false);
    }
  };

  const onCreate = async () => {
    const v = validatePerson(createForm);
    if (!v.ok) {
      setError(v.message || "Validation error");
      return;
    }
    try {
      setCreating(true);
      setError(null);
      await clientApiCall<Person>("/api/v1/persons", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(trimmedPayload(createForm)),
      });
      setCreateForm(toEditable());
      setShowCreate(false);
      setSuccess("Person created successfully");
      await fetchPeople();
    } catch (e: any) {
      setError(e?.message || "Failed to create person");
    } finally {
      setCreating(false);
    }
  };

  const beginEdit = (p: Person) => {
    setEditingId(p.personid);
    setEditForm(toEditable(p));
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm(toEditable());
  };

  const saveEdit = async (id: number) => {
    const v = validatePerson(editForm);
    if (!v.ok) {
      setError(v.message || "Validation error");
      return;
    }
    try {
      setSavingEditId(id);
      await clientApiCall<Person>(`/api/v1/persons/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(trimmedPayload(editForm)),
      });
      setSuccess("Person updated successfully");
      setEditingId(null);
      await fetchPeople();
    } catch (e: any) {
      setError(e?.message || "Failed to update person");
    } finally {
      setSavingEditId(null);
    }
  };

  const onDelete = async (id: number) => {
    try {
      setDeletingId(id);
      await clientApiCall<void>(`/api/v1/persons/${id}`, { method: "DELETE" });
      setSuccess("Person deleted successfully");
      await fetchPeople();
    } catch (e: any) {
      setError(e?.message || "Failed to delete person");
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  const isVacancyPlaceholder = (p: Person) => {
    const first = (p.first || "").trim().toLowerCase();
    return first === "(vacant)";
  };

  const nameOf = (p: Person) => {
    const first = (p.first || "").trim();
    const last = (p.last || "").trim();
    const name = `${first} ${last}`.trim();
    return name || "(Vacant)";
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {/* Alerts */}
        {success && (
          <div className="mb-4 rounded-md bg-green-50 border border-green-200 text-green-800 px-4 py-3">
            {success}
          </div>
        )}
        {error && (
          <div className="mb-4 rounded-md bg-red-50 border border-red-200 text-red-800 px-4 py-3">
            {error}
          </div>
        )}

        {/* Vacancy placeholder warning modal */}
        {vacancyModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div
              className="absolute inset-0 bg-black/40"
              onClick={(e) => {
                e.stopPropagation();
                setVacancyModal(null);
              }}
            />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Proceed with caution</h3>
              <p className="text-sm text-gray-700 mb-4">
                This is the special vacancy placeholder used for single-incumbent offices. Deleting or editing it may break vacancy assignments.
              </p>
              <div className="flex justify-end gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setVacancyModal(null);
                  }}
                  className="px-4 py-2 rounded-md bg-gray-200 hover:bg-gray-300 text-gray-800"
                >
                  Cancel
                </button>
                {vacancyModal && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (vacancyModal.type === "edit") {
                        beginEdit(vacancyModal.person);
                      } else {
                        setConfirmDeleteId(vacancyModal.person.personid);
                      }
                      setVacancyModal(null);
                    }}
                    className={`px-4 py-2 rounded-md ${vacancyModal.type === "delete" ? "bg-red-600 hover:bg-red-700 text-white" : "bg-blue-600 hover:bg-blue-700 text-white"}`}
                  >
                    {vacancyModal.type === "delete" ? "Proceed to Delete" : "Proceed to Edit"}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">People Management</h1>
            <p className="text-gray-600">Manage community members</p>
          </div>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setShowCreate((s) => !s);
            }}
            className="inline-flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white font-medium px-4 py-2 rounded-md transition"
          >
            <UserPlus className="h-5 w-5" />
            Create New Person
          </button>
        </div>

        {/* Create form */}
        {showCreate && (
          <div className="bg-white rounded-lg shadow p-6 mb-8">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">First<span className="text-red-500">*</span></label>
                <input
                  value={createForm.first}
                  onChange={(e) => setCreateForm({ ...createForm, first: e.target.value })}
                  maxLength={15}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Last<span className="text-red-500">*</span></label>
                <input
                  value={createForm.last}
                  onChange={(e) => setCreateForm({ ...createForm, last: e.target.value })}
                  maxLength={30}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  maxLength={45}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  value={createForm.phone}
                  onChange={(e) => setCreateForm({ ...createForm, phone: e.target.value })}
                  maxLength={19}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Apartment</label>
                <input
                  value={createForm.apt}
                  onChange={(e) => setCreateForm({ ...createForm, apt: e.target.value })}
                  maxLength={4}
                  className="w-full rounded-md border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="mt-4 flex gap-3">
              <button
                onClick={onCreate}
                disabled={creating}
                className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium px-4 py-2 rounded-md transition"
              >
                {creating ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
                Save
              </button>
              <button
                onClick={() => {
                  setShowCreate(false);
                  setCreateForm(toEditable());
                }}
                className="inline-flex items-center gap-2 bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium px-4 py-2 rounded-md transition"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Persons List */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Persons List</h2>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12 text-gray-500">
              <Loader2 className="h-6 w-6 animate-spin mr-2" /> Loading...
            </div>
          ) : people.length === 0 ? (
            <div className="text-gray-600 py-8 text-center">No persons found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Name</th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Email</th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Phone</th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Apartment</th>
                    <th className="px-4 py-3 text-right text-sm font-semibold text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {people.map((p) => (
                    <tr key={p.personid}>
                      {/* Name */}
                      <td className="px-4 py-3 align-top">
                        {editingId === p.personid ? (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            <input
                              value={editForm.first}
                              onChange={(e) => setEditForm({ ...editForm, first: e.target.value })}
                              maxLength={15}
                              className="w-full rounded-md border border-gray-300 px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
                              placeholder="First"
                            />
                            <input
                              value={editForm.last}
                              onChange={(e) => setEditForm({ ...editForm, last: e.target.value })}
                              maxLength={30}
                              className="w-full rounded-md border border-gray-300 px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
                              placeholder="Last"
                            />
                          </div>
                        ) : (
                          <span className="font-medium text-gray-900 inline-flex items-center gap-2">
                            {nameOf(p)}
                            {isVacancyPlaceholder(p) ? (
                              <span className="ml-2 inline-block text-xs px-2 py-0.5 rounded border border-amber-200 bg-amber-100 text-amber-800">Placeholder</span>
                            ) : null}
                          </span>
                        )}
                      </td>

                      {/* Email */}
                      <td className="px-4 py-3 align-top">
                        {editingId === p.personid ? (
                          <input
                            value={editForm.email}
                            onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                            maxLength={45}
                            className="w-full rounded-md border border-gray-300 px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        ) : (
                          <span className="text-gray-700">{(p.email || "").trim()}</span>
                        )}
                      </td>

                      {/* Phone */}
                      <td className="px-4 py-3 align-top">
                        {editingId === p.personid ? (
                          <input
                            value={editForm.phone}
                            onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                            maxLength={19}
                            className="w-full rounded-md border border-gray-300 px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        ) : (
                          <span className="text-gray-700">{(p.phone || "").trim()}</span>
                        )}
                      </td>

                      {/* Apt */}
                      <td className="px-4 py-3 align-top">
                        {editingId === p.personid ? (
                          <input
                            value={editForm.apt}
                            onChange={(e) => setEditForm({ ...editForm, apt: e.target.value })}
                            maxLength={4}
                            className="w-full rounded-md border border-gray-300 px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        ) : (
                          <span className="text-gray-700">{(p.apt || "").trim()}</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3 align-top text-right whitespace-nowrap">
                        {editingId === p.personid ? (
                          <div className="inline-flex items-center gap-2">
                            <button
                              onClick={() => saveEdit(p.personid)}
                              disabled={savingEditId === p.personid}
                              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white px-3 py-1.5 rounded-md"
                            >
                              {savingEditId === p.personid ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : null}
                              Save
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="inline-flex items-center gap-2 bg-gray-200 hover:bg-gray-300 text-gray-800 px-3 py-1.5 rounded-md"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <div className="inline-flex items-center justify-end gap-4" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setConfirmDeleteId(null);
                                if (isVacancyPlaceholder(p)) {
                                  setVacancyModal({ type: "edit", person: p });
                                } else {
                                  beginEdit(p);
                                }
                              }}
                              className="text-blue-600 hover:text-blue-900 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-sm"
                            >
                              Edit
                            </button>
                            <span aria-hidden="true" className="text-gray-300">·</span>
                            {confirmDeleteId === p.personid ? (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onDelete(p.personid);
                                }}
                                disabled={deletingId === p.personid}
                                className="text-red-600 hover:text-red-900 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 rounded-sm"
                              >
                                {deletingId === p.personid ? (
                                  <Loader2 className="h-4 w-4 animate-spin inline" />
                                ) : null}
                                Confirm
                              </button>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (isVacancyPlaceholder(p)) {
                                    setVacancyModal({ type: "delete", person: p });
                                  } else {
                                    setConfirmDeleteId(p.personid);
                                  }
                                }}
                                className="text-red-600 hover:text-red-900 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 rounded-sm"
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
        </div>
      </main>
    </div>
  );
}
