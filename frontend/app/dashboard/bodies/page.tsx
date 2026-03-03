"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Body } from "@/lib/types";
import { Plus, Edit2, Trash2 } from "lucide-react";
import { Modal } from "@/components/modal";
import { Toast } from "@/components/toast";

interface BodyFormData {
  name: string;
  mission: string;
  body_precedence: number;
}

export default function BodiesPage() {
  const [bodies, setBodies] = useState<Body[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const bodyRowRefs = useRef<Record<number, HTMLTableRowElement | null>>({});

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBody, setEditingBody] = useState<Body | null>(null);
  const [formData, setFormData] = useState<BodyFormData>({
    name: "",
    mission: "",
    body_precedence: 0,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Toast state
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  useEffect(() => {
    loadBodies();
  }, []);

  const loadBodies = async () => {
    try {
      setLoading(true);
      const data = await api.getBodies();
      setBodies(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bodies");
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingBody(null);
    setFormData({
      name: "",
      mission: "",
      body_precedence: 0,
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (body: Body) => {
    setEditingBody(body);
    setFormData({
      name: body.name,
      mission: body.mission || "",
      body_precedence: body.body_precedence,
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingBody(null);
    setFormError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    // Validation
    if (!formData.name.trim()) {
      setFormError("Name is required");
      return;
    }

    try {
      setSubmitting(true);

      if (editingBody) {
        // Update existing body
        await api.updateBody(editingBody.body_id, formData);
        setToast({ message: "Body updated successfully!", type: "success" });
      } else {
        // Create new body
        await api.createBody(formData);
        setToast({ message: "Body created successfully!", type: "success" });
      }

      closeModal();
      await loadBodies();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to save body");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm("Are you sure you want to delete this body?")) return;

    try {
      await api.deleteBody(id);
      setToast({ message: "Body deleted successfully!", type: "success" });
      await loadBodies();
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Failed to delete body",
        type: "error",
      });
    }
  };

  useEffect(() => {
    const query = searchTerm.trim().toLowerCase();
    if (!query) return;

    const matchesStartsWith = bodies.find((body) =>
      body.name.toLowerCase().startsWith(query)
    );

    const match =
      matchesStartsWith ||
      bodies.find((body) => body.name.toLowerCase().includes(query));

    if (!match) return;

    const element = bodyRowRefs.current[match.body_id];
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [searchTerm, bodies]);

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
      <div className="sm:flex sm:items-center sm:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bodies</h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage administrative bodies and committees
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <button
            onClick={openCreateModal}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Body
          </button>
        </div>
      </div>

      <div className="mb-4">
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Type a name to jump to..."
          aria-label="Search bodies"
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
        />
      </div>

      <div className="bg-white shadow overflow-hidden sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Mission
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Precedence
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {bodies.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-6 py-4 text-center text-gray-500">
                  No bodies found
                </td>
              </tr>
            ) : (
              bodies.map((body) => (
                <tr
                  key={body.body_id}
                  ref={(el) => {
                    bodyRowRefs.current[body.body_id] = el;
                  }}
                  className="hover:bg-gray-50"
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {body.name}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {body.mission || "—"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {body.body_precedence}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => openEditModal(body)}
                      className="text-blue-600 hover:text-blue-900 mr-4"
                      title="Edit"
                    >
                      <Edit2 className="w-4 h-4 inline" />
                    </button>
                    <button
                      onClick={() => handleDelete(body.body_id)}
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
        title={editingBody ? "Edit Body" : "Create New Body"}
      >
        <form onSubmit={handleSubmit}>
          {formError && (
            <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
              {formError}
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                Name *
              </label>
              <input
                type="text"
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                required
              />
            </div>

            <div>
              <label htmlFor="mission" className="block text-sm font-medium text-gray-700 mb-1">
                Mission
              </label>
              <textarea
                id="mission"
                value={formData.mission}
                onChange={(e) => setFormData({ ...formData, mission: e.target.value })}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
              />
            </div>

            <div>
              <label htmlFor="precedence" className="block text-sm font-medium text-gray-700 mb-1">
                Precedence *
              </label>
              <input
                type="number"
                id="precedence"
                value={formData.body_precedence}
                onChange={(e) =>
                  setFormData({ ...formData, body_precedence: parseFloat(e.target.value) })
                }
                step="0.1"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                required
              />
              <p className="mt-1 text-xs text-gray-500">Used for ordering in reports</p>
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
              {submitting ? "Saving..." : editingBody ? "Update" : "Create"}
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
