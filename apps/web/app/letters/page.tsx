import { Suspense } from "react";
import LetterManagement from "./components/LetterManagement";

export default function LettersPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">
            Letters & PDF Generation
          </h1>
          <p className="mt-2 text-gray-600">
            Manage LaTeX templates and generate welcome letters for new residents.
          </p>
        </div>
        
        <Suspense fallback={<div>Loading...</div>}>
          <LetterManagement />
        </Suspense>
      </div>
    </div>
  );
}
