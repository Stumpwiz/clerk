"use client";

import { useEffect, useMemo, useState } from "react";
import { clientApiCall } from "@/lib/client-api";
import { Calendar, Loader2 } from "lucide-react";

// API models
interface Person {
  personid: number;
  first?: string | null;
  last?: string | null;
}

interface Body {
  body_id: number;
  name: string;
  body_precedence: number;
}

interface Office {
  office_id: number;
  title?: string | null;
  office_body_id: number;
  max_incumbents?: number | null;
}

interface Term {
  termpersonid: number;
  termofficeid: number;
  start: string | null; // YYYY-MM-DD
  end: string | null; // YYYY-MM-DD
  ordinal?: string | null; // up to 7
}

// Enriched row for display
interface TermRow extends Term {
  personFirstLast: string;
  personSortable: string;
  bodyName: string;
  officeTitle: string;
}

// Helpers
const fullNameFirstLast = (p?: Person) => {
  const first = (p?.first ?? "").trim();
  const last = (p?.last ?? "").trim();
  if (!first && !last) return "(Vacant)";
  if (!first) return last;
  if (!last) return first;
  return `${first} ${last}`.trim();
};

const toISO = (d: string | null | undefined) => (d ? d : null);

const isDateOnOrAfter = (a: string | null, b: string | null) => {
  if (!a || !b) return false;
  // Compare as YYYY-MM-DD strings
  return a >= b;
};

export default function TermsPage() {
  // Data
  const [people, setPeople] = useState<Person[]>([]);
  const [bodies, setBodies] = useState<Body[]>([]);
  const [offices, setOffices] = useState<Office[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);

  // Status
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Create form visibility/state
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  // Create form fields
  const [createSelectedBodyId, setCreateSelectedBodyId] = useState<number | "">("");
  const [createSelectedOfficeId, setCreateSelectedOfficeId] = useState<number | "">("");
  const [createSelectedPersonId, setCreateSelectedPersonId] = useState<number | "">("");
  const [createStart, setCreateStart] = useState<string>("");
  const [createEnd, setCreateEnd] = useState<string>("");
  const [createOrdinal, setCreateOrdinal] = useState<string>("");
  const [vacancyToggle, setVacancyToggle] = useState<boolean>(false);

  // Row edit/delete state
  const [editingKey, setEditingKey] = useState<string | null>(null); // `${personid}-${officeid}`
  const [editStart, setEditStart] = useState<string>("");
  const [editEnd, setEditEnd] = useState<string>("");
  const [editOrdinal, setEditOrdinal] = useState<string>("");
  const [savingKey, setSavingKey] = useState<string | null>(null);

  const [confirmDeleteKey, setConfirmDeleteKey] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);

  // Derived maps
  const peopleById = useMemo(() => {
    const m = new Map<number, Person>();
    for (const p of people) m.set(p.personid, p);
    return m;
  }, [people]);

  const bodiesById = useMemo(() => {
    const m = new Map<number, Body>();
    for (const b of bodies) m.set(b.body_id, b);
    return m;
  }, [bodies]);

  const officesById = useMemo(() => {
    const m = new Map<number, Office>();
    for (const o of offices) m.set(o.office_id, o);
    return m;
  }, [offices]);

  // Identify vacancy person
  const vacancyPerson = useMemo(() => {
    return people.find((p) => !((p.first ?? "").trim()) && !((p.last ?? "").trim()));
  }, [people]);

  // Offices grouped by body for select
  const officesByBody = useMemo(() => {
    const m = new Map<number, Office[]>();
    for (const o of offices) {
      const arr = m.get(o.office_body_id) ?? [];
      arr.push(o);
      m.set(o.office_body_id, arr);
    }
    // sort each group by title
    for (const arr of m.values()) arr.sort((a, b) => (a.title ?? "").localeCompare(b.title ?? ""));
    return m;
  }, [offices]);

  // Enriched and sorted term rows
  const rows: TermRow[] = useMemo(() => {
    const out: TermRow[] = [];
    for (const t of terms) {
      const person = peopleById.get(t.termpersonid);
      const office = officesById.get(t.termofficeid);
      const body = office ? bodiesById.get(office.office_body_id) : undefined;
      const personFL = fullNameFirstLast(person);
      out.push({
        ...t,
        personFirstLast: personFL,
        personSortable: (person?.first ?? "") + "," + (person?.last ?? ""),
        officeTitle: (office?.title ?? "").trim(),
        bodyName: (body?.name ?? "").trim(),
      });
    }
    out.sort((a, b) =>
      a.bodyName.localeCompare(b.bodyName) ||
      a.officeTitle.localeCompare(b.officeTitle) ||
      a.personSortable.localeCompare(b.personSortable)
    );
    return out;
  }, [terms, peopleById, officesById, bodiesById]);

  // Filters
  const [filterPersonId, setFilterPersonId] = useState<number | "">("");
  const [filterBodyId, setFilterBodyId] = useState<number | "">("");
  const [filterOfficeId, setFilterOfficeId] = useState<number | "">("");

  const filteredRows = useMemo(() => {
    const filtered = rows.filter((r) => {
      // Person filter by exact personid
      if (filterPersonId !== "" && r.termpersonid !== filterPersonId) return false;
      // Body filter via office.office_body_id
      if (filterBodyId !== "") {
        const office = officesById.get(r.termofficeid);
        if (!office || office.office_body_id !== filterBodyId) return false;
      }
      // Office filter by termofficeid
      if (filterOfficeId !== "" && r.termofficeid !== filterOfficeId) return false;
      return true;
    });

    // Canonical sort: Person First (asc, case-insensitive), then Last
    const norm = (s?: string | null) => (s ?? "").trim().toLowerCase();
    return filtered.sort((a, b) => {
      const pa = peopleById.get(a.termpersonid);
      const pb = peopleById.get(b.termpersonid);
      const firstCmp = norm(pa?.first).localeCompare(norm(pb?.first));
      if (firstCmp !== 0) return firstCmp;
      const lastCmp = norm(pa?.last).localeCompare(norm(pb?.last));
      if (lastCmp !== 0) return lastCmp;
      const bodyCmp = norm(a.bodyName).localeCompare(norm(b.bodyName));
      if (bodyCmp !== 0) return bodyCmp;
      const officeCmp = norm(a.officeTitle).localeCompare(norm(b.officeTitle));
      if (officeCmp !== 0) return officeCmp;
      return (a.start ?? "").localeCompare(b.start ?? "");
    });
  }, [rows, filterPersonId, filterBodyId, filterOfficeId, officesById, peopleById]);

  // Alerts auto-dismiss
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

  // Click-away to cancel delete confirm
  useEffect(() => {
    if (!confirmDeleteKey) return;
    const handler = () => setConfirmDeleteKey(null);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [confirmDeleteKey]);

  // Initial load
  useEffect(() => {
    fetchAll();
  }, []);

  async function fetchAll() {
    try {
      setLoading(true);
      setError(null);
      const [t, p, b, o] = await Promise.all([
        clientApiCall<Term[]>("/api/v1/terms"),
        clientApiCall<Person[]>("/api/v1/persons"),
        clientApiCall<Body[]>("/api/v1/bodies"),
        clientApiCall<Office[]>("/api/v1/offices"),
      ]);
      setTerms(Array.isArray(t) ? t : []);
      setPeople(Array.isArray(p) ? p : []);
      setBodies(Array.isArray(b) ? b : []);
      setOffices(Array.isArray(o) ? o : []);
    } catch (e: any) {
      setError(e?.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  }

  // Keep person selection consistent with vacancy toggle
  useEffect(() => {
    if (!createSelectedOfficeId) {
      setVacancyToggle(false);
      return;
    }
    const office = officesById.get(createSelectedOfficeId as number);
    const allowed = (office?.max_incumbents === 1);
    if (!allowed) {
      setVacancyToggle(false);
      if (createSelectedPersonId && vacancyPerson && createSelectedPersonId === vacancyPerson.personid) {
        setCreateSelectedPersonId("");
      }
    }
  }, [createSelectedOfficeId, officesById, vacancyPerson]);

  // If vacancy toggle enabled, force person to vacancy
  useEffect(() => {
    if (vacancyToggle) {
      if (vacancyPerson) setCreateSelectedPersonId(vacancyPerson.personid);
    } else {
      if (vacancyPerson && createSelectedPersonId === vacancyPerson.personid) {
        setCreateSelectedPersonId("");
      }
    }
  }, [vacancyToggle, vacancyPerson]);

  // Create form validation
  function validateCreate(): { ok: boolean; message?: string } {
    const personid = createSelectedPersonId;
    const bodyid = createSelectedBodyId;
    const officeid = createSelectedOfficeId;
    const start = createStart.trim();
    const end = createEnd.trim();
    const ordinal = createOrdinal.trim();

    // Required
    if (!officeid) return { ok: false, message: "Office is required" };
    if (!bodyid) return { ok: false, message: "Body is required" };

    // Person: required unless vacancy toggle enabled (then vacancy must exist)
    if (!vacancyToggle) {
      if (!personid) return { ok: false, message: "Person is required" };
      if (vacancyPerson && personid === vacancyPerson.personid) {
        return { ok: false, message: "Vacancy placeholder requires the toggle" };
      }
    } else {
      if (!vacancyPerson) return { ok: false, message: "Vacancy placeholder person not found" };
      if (personid !== vacancyPerson.personid) {
        return { ok: false, message: "Enable vacancy will assign the vacancy placeholder" };
      }
    }

    if (!start) return { ok: false, message: "Start date is required" };
    if (end && end < start) return { ok: false, message: "End date must be on or after start date" };
    if (ordinal.length > 7) return { ok: false, message: "Ordinal must be at most 7 characters" };

    return { ok: true };
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const v = validateCreate();
    if (!v.ok) {
      setError(v.message || "Invalid form");
      return;
    }

    try {
      setCreating(true);
      setError(null);
      setSuccess(null);

      const payload = {
        termpersonid: createSelectedPersonId as number,
        termofficeid: createSelectedOfficeId as number,
        start: toISO(createStart),
        end: createEnd ? toISO(createEnd) : null,
        ordinal: createOrdinal.trim() || null,
      };

      const resp = await clientApiCall<Term>("/api/v1/terms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      // If API returns conflict-like error elsewhere, clientApiCall may throw.
      setSuccess("Term assigned successfully");
      setShowCreate(false);
      // reset form
      setCreateSelectedBodyId("");
      setCreateSelectedOfficeId("");
      setCreateSelectedPersonId("");
      setCreateStart("");
      setCreateEnd("");
      setCreateOrdinal("");
      setVacancyToggle(false);
      await fetchAll();
    } catch (e: any) {
      const msg = e?.message || "Failed to create term";
      // Friendly duplicate composite key message hint
      const friendly = /unique|already exists|duplicate|conflict/i.test(msg)
        ? "A term for the selected person and office already exists"
        : msg;
      setError(friendly);
    } finally {
      setCreating(false);
    }
  }

  function startEdit(row: TermRow) {
    const key = `${row.termpersonid}-${row.termofficeid}`;
    setEditingKey(key);
    setEditStart(row.start ?? "");
    setEditEnd(row.end ?? "");
    setEditOrdinal(row.ordinal ?? "");
  }
  function cancelEdit() {
    setEditingKey(null);
    setEditStart("");
    setEditEnd("");
    setEditOrdinal("");
  }
  async function saveEdit(row: TermRow) {
    const s = editStart.trim();
    const e = editEnd.trim();
    const o = editOrdinal.trim();
    if (!s) {
      setError("Start date is required");
      return;
    }
    if (e && e < s) {
      setError("End date must be on or after start date");
      return;
    }
    const key = `${row.termpersonid}-${row.termofficeid}`;
    try {
      setSavingKey(key);
      setError(null);
      setSuccess(null);
      await clientApiCall<Term>(`/api/v1/terms/${row.termpersonid}/${row.termofficeid}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start: toISO(s), end: e ? toISO(e) : null, ordinal: o || null }),
      });
      setSuccess("Term updated");
      setEditingKey(null);
      await fetchAll();
    } catch (e: any) {
      setError(e?.message || "Failed to update term");
    } finally {
      setSavingKey(null);
    }
  }

  async function deleteRow(row: TermRow) {
    const key = `${row.termpersonid}-${row.termofficeid}`;
    try {
      setDeletingKey(key);
      setError(null);
      setSuccess(null);
      await clientApiCall(`/api/v1/terms/${row.termpersonid}/${row.termofficeid}`, { method: "DELETE" });
      setSuccess("Term deleted");
      setConfirmDeleteKey(null);
      await fetchAll();
    } catch (e: any) {
      setError(e?.message || "Failed to delete term");
    } finally {
      setDeletingKey(null);
    }
  }

  // Create form office allowlist logic
  const selectedOffice = useMemo(() => {
    if (!createSelectedOfficeId) return undefined;
    return officesById.get(createSelectedOfficeId as number);
  }, [createSelectedOfficeId, officesById]);
  const vacancyAllowed = useMemo(() => selectedOffice?.max_incumbents === 1, [selectedOffice]);

  // Options excluding vacancy by default
  const personOptions = useMemo(() => {
    const list = people
      .filter((p) => {
        const isVacant = !((p.first ?? "").trim()) && !((p.last ?? "").trim());
        if (vacancyToggle) return isVacant; // only vacancy when toggled on
        return !isVacant; // exclude vacancy by default
      })
      .map((p) => ({ id: p.personid, label: fullNameFirstLast(p) }));
    // Sort by first, then last (case-insensitive) based on the "First Last" label
    return list.sort((a, b) => a.label.toLowerCase().localeCompare(b.label.toLowerCase()));
  }, [people, vacancyToggle]);

  const personFilterOptions = useMemo(() => {
    const list = people.map((p) => {
      const first = (p.first ?? "").trim();
      const last = (p.last ?? "").trim();
      const label = (!first && !last) ? "(Vacant)" : `${first} ${last}`.trim() || first || last;
      return { id: p.personid, first, last, label };
    });
    list.sort((a, b) => {
      const firstCmp = (a.first || "").toLowerCase().localeCompare((b.first || "").toLowerCase());
      if (firstCmp !== 0) return firstCmp;
      return (a.last || "").toLowerCase().localeCompare((b.last || "").toLowerCase());
    });
    return list.map(({ id, label }) => ({ id, label }));
  }, [people]);

  const bodyOptions = useMemo(() => {
    const sortedBodies = bodies.slice().sort((a, b) => {
      const prec = (a.body_precedence ?? 0) - (b.body_precedence ?? 0);
      if (prec !== 0) return prec;
      return (a.name || "").toLowerCase().localeCompare((b.name || "").toLowerCase());
    });
    return sortedBodies.map((b) => ({ id: b.body_id, label: b.name }));
  }, [bodies]);

  // Offices grouped by body optgroups
  const officeGroups = useMemo(() => {
    return bodies
      .map((b) => ({
        body: b,
        offices: (officesByBody.get(b.body_id) ?? []).slice(),
      }))
      .filter((g) => g.offices.length > 0);
  }, [bodies, officesByBody]);

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Terms Management</h1>
          <p className="text-gray-600">Assign people to offices and manage term dates</p>
        </div>

        {/* Alerts */}
        {success && (
          <div className="mb-4 rounded-md bg-green-50 p-4 text-green-800 border border-green-200">{success}</div>
        )}
        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-4 text-red-800 border border-red-200">{error}</div>
        )}

        {/* Create button */}
        <div className="mb-6 flex items-center justify-between">
          <button
            onClick={() => setShowCreate((v) => !v)}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md transition"
          >
            <Calendar size={18} />
            Assign Person to Office
          </button>
        </div>

        {/* Create form */}
        {showCreate && (
          <div className="mb-8 bg-white rounded-lg shadow p-6">
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Body */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Body</label>
                  <select
                    className="w-full bg-white border border-gray-300 text-gray-900 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    value={createSelectedBodyId}
                    onChange={(e) => {
                      const v = e.target.value ? Number(e.target.value) : "";
                      setCreateSelectedBodyId(v);
                      // Reset office if it doesn't belong to body
                      if (v === "" || (createSelectedOfficeId && officesById.get(createSelectedOfficeId as number)?.office_body_id !== v)) {
                        setCreateSelectedOfficeId("");
                      }
                    }}
                    required
                  >
                    <option value="">Select body</option>
                    {bodyOptions.map((b) => (
                      <option key={b.id} value={b.id}>{b.label}</option>
                    ))}
                  </select>
                </div>

                {/* Office */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Office</label>
                  <select
                    className="w-full bg-white border border-gray-300 text-gray-900 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    value={createSelectedOfficeId}
                    onChange={(e) => setCreateSelectedOfficeId(e.target.value ? Number(e.target.value) : "")}
                    required
                  >
                    <option value="">Select office</option>
                    {officeGroups.map((g) => (
                      <optgroup key={g.body.body_id} label={g.body.name}>
                        {g.offices
                          .filter((o) => (createSelectedBodyId === "" ? true : o.office_body_id === createSelectedBodyId))
                          .map((o) => (
                            <option key={o.office_id} value={o.office_id}>{o.title}</option>
                          ))}
                      </optgroup>
                    ))}
                  </select>
                </div>

                {/* Vacancy toggle and Person */}
                <div>
                  <div className="flex items-center justify-between">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Person (First Last)</label>
                    <div className={`flex items-center gap-2 ${vacancyAllowed ? "" : "opacity-50"}`}>
                      <span className="text-xs text-gray-500">Use vacancy placeholder</span>
                      <label className="inline-flex cursor-pointer items-center">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-gray-300"
                          disabled={!vacancyAllowed}
                          checked={vacancyToggle}
                          onChange={(e) => setVacancyToggle(e.target.checked)}
                        />
                      </label>
                    </div>
                  </div>
                  <select
                    className="w-full bg-white border border-gray-300 text-gray-900 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    value={createSelectedPersonId}
                    onChange={(e) => setCreateSelectedPersonId(e.target.value ? Number(e.target.value) : "")}
                    required={!vacancyToggle}
                    disabled={vacancyToggle}
                  >
                    <option value="">Select person</option>
                    {personOptions.map((p) => (
                      <option key={p.id} value={p.id}>{p.label}</option>
                    ))}
                  </select>
                </div>

                {/* Start */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Start date</label>
                  <input
                    type="date"
                    className="w-full border rounded-md px-3 py-2"
                    value={createStart}
                    onChange={(e) => setCreateStart(e.target.value)}
                    required
                  />
                </div>

                {/* End */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">End date</label>
                  <input
                    type="date"
                    className="w-full border rounded-md px-3 py-2"
                    value={createEnd}
                    onChange={(e) => setCreateEnd(e.target.value)}
                  />
                </div>

                {/* Ordinal */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Ordinal</label>
                  <input
                    type="text"
                    className="w-full border rounded-md px-3 py-2"
                    value={createOrdinal}
                    onChange={(e) => setCreateOrdinal(e.target.value)}
                    maxLength={7}
                    placeholder="e.g., 1st, 2024-25"
                  />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md disabled:opacity-50"
                  disabled={creating}
                >
                  {creating ? <Loader2 className="animate-spin" size={18} /> : null}
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreate(false);
                    setVacancyToggle(false);
                  }}
                  className="bg-gray-100 hover:bg-gray-200 text-gray-800 px-4 py-2 rounded-md"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* List card */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="mb-4 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
            {/* Filters */}
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Person</label>
                <select
                  className="bg-white border border-gray-300 text-gray-900 rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  value={filterPersonId}
                  onChange={(e) => setFilterPersonId(e.target.value ? Number(e.target.value) : "")}
                >
                  <option value="">All Persons</option>
                  {personFilterOptions.map((p) => (
                    <option key={p.id} value={p.id}>{p.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Body</label>
                <select
                  className="bg-white border border-gray-300 text-gray-900 rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  value={filterBodyId}
                  onChange={(e) => {
                    const v = e.target.value ? Number(e.target.value) : "";
                    setFilterBodyId(v);
                    setFilterOfficeId("");
                  }}
                >
                  <option value="">All Bodies</option>
                  {bodyOptions.map((b) => (
                    <option key={b.id} value={b.id}>{b.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Office</label>
                <select
                  className="bg-white border border-gray-300 text-gray-900 rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  value={filterOfficeId}
                  onChange={(e) => setFilterOfficeId(e.target.value ? Number(e.target.value) : "")}
                >
                  <option value="">All Offices</option>
                  {officeGroups.map((g) => (
                    <optgroup key={g.body.body_id} label={g.body.name}>
                      {g.offices
                        .filter((o) => (filterBodyId === "" ? true : o.office_body_id === filterBodyId))
                        .map((o) => (
                          <option key={o.office_id} value={o.office_id}>{o.title}</option>
                        ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Person</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Body</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Office</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Start</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">End</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ordinal</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                      <span className="inline-flex items-center gap-2"><Loader2 className="animate-spin" size={18}/> Loading…</span>
                    </td>
                  </tr>
                ) : filteredRows.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-gray-500">No terms found</td>
                  </tr>
                ) : (
                  filteredRows.map((r) => {
                    const key = `${r.termpersonid}-${r.termofficeid}`;
                    const isEditing = editingKey === key;
                    const isSaving = savingKey === key;
                    const isDeleting = deletingKey === key;
                    return (
                      <tr key={key} className="hover:bg-gray-50">
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">{r.personFirstLast}</td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">{r.bodyName}</td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">{r.officeTitle}</td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                          {isEditing ? (
                            <input type="date" className="border rounded px-2 py-1" value={editStart} onChange={(e) => setEditStart(e.target.value)} />
                          ) : (
                            r.start || "—"
                          )}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                          {isEditing ? (
                            <input type="date" className="border rounded px-2 py-1" value={editEnd} onChange={(e) => setEditEnd(e.target.value)} />
                          ) : (
                            r.end || "—"
                          )}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-900">
                          {isEditing ? (
                            <input type="text" className="border rounded px-2 py-1 w-28" maxLength={7} value={editOrdinal} onChange={(e) => setEditOrdinal(e.target.value)} />
                          ) : (
                            r.ordinal || "—"
                          )}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap text-right text-sm">
                          {isEditing ? (
                            <div className="inline-flex gap-2">
                              <button
                                className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded disabled:opacity-50"
                                disabled={isSaving}
                                onClick={() => saveEdit(r)}
                              >
                                {isSaving ? <Loader2 className="animate-spin inline" size={14}/> : null} Save
                              </button>
                              <button className="bg-gray-100 hover:bg-gray-200 text-gray-800 px-3 py-1 rounded" onClick={cancelEdit}>Cancel</button>
                            </div>
                          ) : (
                            <div className="inline-flex gap-2">
                              <button className="bg-blue-50 hover:bg-blue-100 text-blue-700 px-3 py-1 rounded" onClick={() => startEdit(r)}>Edit</button>
                              {confirmDeleteKey === key ? (
                                <button
                                  className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded disabled:opacity-50"
                                  disabled={isDeleting}
                                  onClick={() => deleteRow(r)}
                                >
                                  {isDeleting ? <Loader2 className="animate-spin inline" size={14}/> : null} Confirm
                                </button>
                              ) : (
                                <button className="bg-red-50 hover:bg-red-100 text-red-700 px-3 py-1 rounded" onClick={(e) => { e.stopPropagation(); setConfirmDeleteKey(key); }}>Delete</button>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
