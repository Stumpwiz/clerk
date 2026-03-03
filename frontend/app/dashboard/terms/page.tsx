"use client";

import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import type { Term, Person, Office, Body } from "@/lib/types";
import { Plus, Edit2, Trash2 } from "lucide-react";
import { Modal } from "@/components/modal";
import { Toast } from "@/components/toast";

interface TermFormData {
  term_person_id: number;
  term_office_id: number;
  start: string;
  end: string;
  ordinal: string;
}

export default function TermsPage() {
  const [terms, setTerms] = useState<Term[]>([]);
  const [persons, setPersons] = useState<Person[]>([]);
  const [offices, setOffices] = useState<Office[]>([]);
  const [bodies, setBodies] = useState<Body[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTerm, setEditingTerm] = useState<Term | null>(null);
  const [formData, setFormData] = useState<TermFormData>({
    term_person_id: 0,
    term_office_id: 0,
    start: "",
    end: "",
    ordinal: "",
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [isOngoing, setIsOngoing] = useState(false);

  // Toast state
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  // Filter state
  const [filterPersonId, setFilterPersonId] = useState<number>(0); // 0 = All
  const [filterBodyId, setFilterBodyId] = useState<number>(0); // 0 = All
  const [filterOfficeId, setFilterOfficeId] = useState<number>(0); // 0 = All

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [termsData, personsData, officesData, bodiesData] = await Promise.all([
        api.getTerms(),
        api.getPersons(),
        api.getOffices(),
        api.getBodies(),
      ]);

      // Sort terms by person's first name, then last name
      const sortedTerms = termsData.sort((a, b) => {
        const personA = personsData.find((p) => p.person_id === a.term_person_id);
        const personB = personsData.find((p) => p.person_id === b.term_person_id);

        const firstA = (personA?.first || "").toLowerCase();
        const firstB = (personB?.first || "").toLowerCase();
        const lastA = (personA?.last || "").toLowerCase();
        const lastB = (personB?.last || "").toLowerCase();

        if (firstA !== firstB) {
          return firstA.localeCompare(firstB);
        }
        return lastA.localeCompare(lastB);
      });

      setTerms(sortedTerms);
      setPersons(personsData);
      setOffices(officesData);
      setBodies(bodiesData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const formatPersonName = (person: Person): string => {
    const first = person.first || "";
    const last = person.last || "";

    if (first && last) {
      return `${first} ${last}`;
    } else if (first) {
      return first;
    } else if (last) {
      return last;
    }
    return "—";
  };

  const getPersonName = (personId: number): string => {
    const person = persons.find((p) => p.person_id === personId);
    if (!person) return "Unknown";
    return formatPersonName(person);
  };

  const getOfficeTitle = (officeId: number): string => {
    const office = offices.find((o) => o.office_id === officeId);
    return office?.title || "Unknown";
  };

  const getBodyName = (officeId: number): string => {
    const office = offices.find((o) => o.office_id === officeId);
    if (!office) return "Unknown";
    const body = bodies.find((b) => b.body_id === office.office_body_id);
    return body?.name || "Unknown";
  };

  const formatOfficeWithBody = (office: Office): string => {
    const body = bodies.find((b) => b.body_id === office.office_body_id);
    return `${office.title || "Unknown"} (${body?.name || "Unknown"})`;
  };

  // Sorted lists for dropdowns
  const sortedPersons = useMemo(() => {
    return [...persons].sort((a, b) => {
      const firstA = (a.first || "").toLowerCase();
      const firstB = (b.first || "").toLowerCase();
      const lastA = (a.last || "").toLowerCase();
      const lastB = (b.last || "").toLowerCase();

      if (firstA !== firstB) {
        return firstA.localeCompare(firstB);
      }
      return lastA.localeCompare(lastB);
    });
  }, [persons]);

  const sortedBodies = useMemo(() => {
    return [...bodies].sort((a, b) => a.name.localeCompare(b.name));
  }, [bodies]);

  const sortedOffices = useMemo(() => {
    return [...offices].sort((a, b) => {
      const titleA = (a.title || "").toLowerCase();
      const titleB = (b.title || "").toLowerCase();

      if (titleA !== titleB) {
        return titleA.localeCompare(titleB);
      }

      const bodyA = bodies.find((body) => body.body_id === a.office_body_id);
      const bodyB = bodies.find((body) => body.body_id === b.office_body_id);
      return (bodyA?.name || "").localeCompare(bodyB?.name || "");
    });
  }, [offices, bodies]);

  // Filtered terms based on selected filters
  const filteredTerms = useMemo(() => {
    return terms.filter((term) => {
      // Filter by person
      if (filterPersonId !== 0 && term.term_person_id !== filterPersonId) {
        return false;
      }

      // Filter by office
      if (filterOfficeId !== 0 && term.term_office_id !== filterOfficeId) {
        return false;
      }

      // Filter by body
      if (filterBodyId !== 0) {
        const office = offices.find((o) => o.office_id === term.term_office_id);
        if (!office || office.office_body_id !== filterBodyId) {
          return false;
        }
      }

      return true;
    });
  }, [terms, filterPersonId, filterOfficeId, filterBodyId, offices]);

  const openCreateModal = () => {
    setEditingTerm(null);
    setFormData({
      term_person_id: persons[0]?.person_id || 0,
      term_office_id: offices[0]?.office_id || 0,
      start: "",
      end: "",
      ordinal: "none",
    });
    setIsOngoing(false);
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (term: Term) => {
    setEditingTerm(term);
    // Handle legacy data: if ordinal is empty or not one of the valid values, default to "none"
    const validOrdinals = ["none", "first", "second"];
    const ordinalValue = term.ordinal && validOrdinals.includes(term.ordinal.toLowerCase()) 
      ? term.ordinal.toLowerCase() 
      : "none";
    const ongoing = term.end === "9999-12-31";

    setFormData({
      term_person_id: term.term_person_id,
      term_office_id: term.term_office_id,
      start: term.start || "",
      end: ongoing ? "9999-12-31" : term.end || "",
      ordinal: ordinalValue,
    });
    setIsOngoing(ongoing);
    setFormError(null);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingTerm(null);
    setFormError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    // Validation
    if (!formData.term_person_id || formData.term_person_id === 0) {
      setFormError("Please select a person");
      return;
    }

    if (!formData.term_office_id || formData.term_office_id === 0) {
      setFormError("Please select an office");
      return;
    }

    try {
      setSubmitting(true);

      if (editingTerm) {
        // Update existing term (only non-key fields)
        await api.updateTerm(
          editingTerm.term_person_id,
          editingTerm.term_office_id,
          {
            start: formData.start || null,
            end: isOngoing ? "9999-12-31" : formData.end || null,
            ordinal: formData.ordinal || null,
          }
        );
        setToast({ message: "Term updated successfully!", type: "success" });
      } else {
        // Create new term
        await api.createTerm({
          term_person_id: formData.term_person_id,
          term_office_id: formData.term_office_id,
          start: formData.start || null,
          end: isOngoing ? "9999-12-31" : formData.end || null,
          ordinal: formData.ordinal || null,
        });
        setToast({ message: "Term created successfully!", type: "success" });
      }

      closeModal();
      await loadData();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to save term");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (personId: number, officeId: number) => {
    if (!confirm("Are you sure you want to delete this term?")) return;

    try {
      await api.deleteTerm(personId, officeId);
      setToast({ message: "Term deleted successfully!", type: "success" });
      await loadData();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to delete term",
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

  const canCreateTerm = persons.length > 0 && offices.length > 0;

  return (
    <div className="px-4 sm:px-0">
      <div className="sm:flex sm:items-center sm:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Terms</h1>
          <p className="mt-2 text-sm text-gray-700">
            Assign persons to office positions with term dates
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <button
            onClick={openCreateModal}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            disabled={!canCreateTerm}
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Term
          </button>
        </div>
      </div>

      {!canCreateTerm && (
        <div className="mb-4 bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-3 rounded">
          Please create at least one Person and one Office before adding Terms.
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 bg-white shadow rounded-lg p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Filter by Person */}
          <div>
            <label htmlFor="filterPerson" className="block text-sm font-medium text-gray-700 mb-1">
              Filter by Person
            </label>
            <select
              id="filterPerson"
              value={filterPersonId}
              onChange={(e) => setFilterPersonId(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
            >
              <option value={0}>All Persons</option>
              {sortedPersons.map((person) => (
                <option key={person.person_id} value={person.person_id}>
                  {formatPersonName(person)}
                </option>
              ))}
            </select>
          </div>

          {/* Filter by Body */}
          <div>
            <label htmlFor="filterBody" className="block text-sm font-medium text-gray-700 mb-1">
              Filter by Body
            </label>
            <select
              id="filterBody"
              value={filterBodyId}
              onChange={(e) => setFilterBodyId(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
            >
              <option value={0}>All Bodies</option>
              {sortedBodies.map((body) => (
                <option key={body.body_id} value={body.body_id}>
                  {body.name}
                </option>
              ))}
            </select>
          </div>

          {/* Filter by Office */}
          <div>
            <label htmlFor="filterOffice" className="block text-sm font-medium text-gray-700 mb-1">
              Filter by Office
            </label>
            <select
              id="filterOffice"
              value={filterOfficeId}
              onChange={(e) => setFilterOfficeId(parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
            >
              <option value={0}>All Offices</option>
              {sortedOffices.map((office) => (
                <option key={office.office_id} value={office.office_id}>
                  {formatOfficeWithBody(office)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Person
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Office
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Body
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Start
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                End
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Ordinal
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredTerms.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-4 text-center text-gray-500">
                  {terms.length === 0 ? "No terms found" : "No terms match the selected filters"}
                </td>
              </tr>
            ) : (
              filteredTerms.map((term) => (
                <tr
                  key={`${term.term_person_id}-${term.term_office_id}`}
                  className="hover:bg-gray-50"
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {getPersonName(term.term_person_id)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {getOfficeTitle(term.term_office_id)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {getBodyName(term.term_office_id)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {term.start || "—"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {term.end === "9999-12-31" ? "Ongoing" : term.end || "—"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {term.ordinal || "—"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => openEditModal(term)}
                      className="text-blue-600 hover:text-blue-900 mr-4"
                      title="Edit"
                    >
                      <Edit2 className="w-4 h-4 inline" />
                    </button>
                    <button
                      onClick={() =>
                        handleDelete(term.term_person_id, term.term_office_id)
                      }
                      className="text-red-600 hover:text-red-900"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4 inline" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create/Edit Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={closeModal}
        title={editingTerm ? "Edit Term" : "Create New Term"}
      >
        <form onSubmit={handleSubmit}>
          {formError && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
              {formError}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="person" className="block text-sm font-medium text-gray-700 mb-1">
                Person *
              </label>
              <select
                id="person"
                value={formData.term_person_id}
                onChange={(e) =>
                  setFormData({ ...formData, term_person_id: parseInt(e.target.value) })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                required
                disabled={!!editingTerm}
              >
                <option value={0}>Select a person...</option>
                {persons.map((person) => (
                  <option key={person.person_id} value={person.person_id}>
                    {formatPersonName(person)}
                  </option>
                ))}
              </select>
              {editingTerm && (
                <p className="mt-1 text-xs text-gray-500">
                  This value cannot be edited from here. To change it, delete this term and create a new one with the correct person.
                </p>
              )}
            </div>

            <div>
              <label htmlFor="office" className="block text-sm font-medium text-gray-700 mb-1">
                Office *
              </label>
              <select
                id="office"
                value={formData.term_office_id}
                onChange={(e) =>
                  setFormData({ ...formData, term_office_id: parseInt(e.target.value) })
                }
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                required
                disabled={!!editingTerm}
              >
                <option value={0}>Select an office...</option>
                {sortedOffices.map((office) => (
                  <option key={office.office_id} value={office.office_id}>
                    {office.title} ({getBodyName(office.office_id)})
                  </option>
                ))}
              </select>
              {editingTerm && (
                <p className="mt-1 text-xs text-gray-500">
                  This value cannot be edited from here. To change it, delete this term and create a new one with the correct office.
                </p>
              )}
            </div>

            <div>
              <label htmlFor="start" className="block text-sm font-medium text-gray-700 mb-1">
                Start Date
              </label>
              <input
                type="date"
                id="start"
                value={formData.start}
                onChange={(e) => setFormData({ ...formData, start: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label htmlFor="end" className="block text-sm font-medium text-gray-700 mb-1">
                End Date
              </label>
              <input
                type="date"
                id="end"
                value={isOngoing ? "" : formData.end}
                onChange={(e) => setFormData({ ...formData, end: e.target.value })}
                disabled={isOngoing}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
              <div className="mt-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  id="ongoing"
                  checked={isOngoing}
                  onChange={(e) => {
                    const next = e.target.checked;
                    setIsOngoing(next);
                    setFormData({ ...formData, end: next ? "9999-12-31" : "" });
                  }}
                  className="h-4 w-4 border-gray-300 rounded text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="ongoing" className="text-sm text-gray-700">
                  Ongoing (no end date)
                </label>
              </div>
              {isOngoing && (
                <p className="mt-1 text-xs text-gray-500">No end date</p>
              )}
            </div>

            <div>
              <label htmlFor="ordinal" className="block text-sm font-medium text-gray-700 mb-1">
                Term Limit Status *
              </label>
              <select
                id="ordinal"
                value={formData.ordinal}
                onChange={(e) => setFormData({ ...formData, ordinal: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                required
              >
                <option value="none">None (not term-limited)</option>
                <option value="first">First (term-limited)</option>
                <option value="second">Second (term-limited)</option>
              </select>
              <p className="mt-1 text-xs text-gray-500">
                Council officers and department chairs are term-limited to two consecutive terms. Select &quot;first&quot; or &quot;second&quot; for term-limited positions, or &quot;none&quot; for other positions.
              </p>
            </div>
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <button
              type="button"
              onClick={closeModal}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50"
              disabled={submitting}
            >
              {submitting ? "Saving..." : editingTerm ? "Update" : "Create"}
            </button>
          </div>
        </form>
      </Modal>

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
