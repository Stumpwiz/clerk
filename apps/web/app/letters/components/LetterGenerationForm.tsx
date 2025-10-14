"use client";

import { useState } from "react";
import { letterApi } from "@/lib/client-api";

interface Props {
  onGenerate: () => Promise<void>;
}

export default function LetterGenerationForm({ onGenerate }: Props) {
  const [addressee, setAddressee] = useState("");
  const [salutation, setSalutation] = useState("");
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
  const [apartment, setApartment] = useState("");
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Validate apartment regex
  const apartmentValid = /^[KLS][1-7](0[1-9]|[1-3][0-9]|4[0-4])$/.test(apartment);
  const canSubmit = addressee && salutation && date && apartmentValid && !generating;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!canSubmit) return;

    try {
      setGenerating(true);
      setMessage(null);

      const result = await letterApi.generate({
        addressee,
        salutation,
        date,
        apartment,
      });

      if (result.success) {
        setMessage({
          type: "success",
          text: `✅ Generated: ${result.filename}`,
        });
        
        // Clear form
        setAddressee("");
        setSalutation("");
        setDate(new Date().toISOString().split("T")[0]);
        setApartment("");
        
        // Refresh PDF list
        await onGenerate();
        
        setTimeout(() => setMessage(null), 5000);
      } else {
        setMessage({
          type: "error",
          text: result.error || "Generation failed",
        });
      }
    } catch (err: any) {
      let errorText = "Unexpected error";
      
      if (typeof err === 'string') {
        errorText = err;
      } else if (err.message) {
        errorText = err.message;
      } else if (err.detail) {
        errorText = err.detail;
      } else {
        try {
          errorText = JSON.stringify(err);
        } catch {
          errorText = "Unexpected error";
        }
      }
      
      setMessage({
        type: "error",
        text: errorText,
      });
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="rounded-lg bg-white shadow p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">
        ✉️ Generate Welcome Letter
      </h2>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Addressee
          </label>
          <input
            type="text"
            value={addressee}
            onChange={(e) => setAddressee(e.target.value)}
            placeholder="John and Mary Smith"
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-700 placeholder-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Salutation
          </label>
          <input
            type="text"
            value={salutation}
            onChange={(e) => setSalutation(e.target.value)}
            placeholder="John and Mary"
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-700 placeholder-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
            required
          />
          <p className="mt-1 text-xs text-gray-500">
            Without "Dear" - e.g., "John and Mary"
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Date
          </label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-700 focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Apartment
          </label>
          <input
            type="text"
            value={apartment}
            onChange={(e) => setApartment(e.target.value.toUpperCase())}
            placeholder="K742"
            pattern="^[KLS][1-7](0[1-9]|[1-3][0-9]|4[0-4])$"
            className={`w-full rounded-lg border px-4 py-2 text-gray-700 placeholder-gray-400 focus:ring-2 ${
              apartment && !apartmentValid
                ? "border-red-300 focus:border-red-500 focus:ring-red-200"
                : "border-gray-300 focus:border-blue-500 focus:ring-blue-200"
            }`}
            required
          />
          <p className="mt-1 text-xs text-gray-500">
            Format: Building (K/L/S) + Floor (1-7) + Apartment (01-44). Examples: K522, L342, S714
          </p>
          {apartment && !apartmentValid && (
            <p className="mt-1 text-xs text-red-600">
              ❌ Invalid format. Example: K742
            </p>
          )}
        </div>

        {message && (
          <div
            className={`rounded-lg p-3 ${
              message.type === "success"
                ? "bg-green-50 text-green-800"
                : "bg-red-50 text-red-800"
            }`}
          >
            {message.text}
          </div>
        )}

        <button
          type="submit"
          disabled={!canSubmit}
          className="w-full rounded-lg bg-emerald-600 px-6 py-3 text-white font-semibold hover:bg-emerald-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {generating ? "Generating PDF..." : "Generate PDF"}
        </button>
      </form>
    </div>
  );
}
