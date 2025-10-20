"use client";

import React from "react";

interface FileActionsProps {
  viewHref: string;
  isConfirming: boolean;
  onRequestDelete: () => void;
  onConfirmDelete: () => void;
  onCancel?: () => void;
}

/**
 * Reusable View/Delete actions for file rows.
 * - View: anchor link (opens in new tab)
 * - Delete: button with two-step Delete → Confirm flow
 * Typography and colors match usage on Rosters/Reports pages.
 */
export default function FileActions(props: FileActionsProps) {
  const { viewHref, isConfirming, onRequestDelete, onConfirmDelete, onCancel } = props;

  return (
    <div className="inline-flex items-center gap-4" onClick={(e) => e.stopPropagation()}>
      <a
        href={viewHref}
        target="_blank"
        rel="noreferrer noopener"
        className="text-blue-600 hover:text-blue-900 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-sm"
      >
        View
      </a>
      <span aria-hidden="true" className="text-gray-300">·</span>
      {isConfirming ? (
        <>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onConfirmDelete();
            }}
            className="text-red-600 hover:text-red-900 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 rounded-sm"
          >
            Confirm
          </button>
          {onCancel && (
            <>
              <span aria-hidden="true" className="text-gray-300">·</span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onCancel();
                }}
                className="text-gray-600 hover:text-gray-900 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 rounded-sm"
              >
                Cancel
              </button>
            </>
          )}
        </>
      ) : (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRequestDelete();
          }}
          className="text-red-600 hover:text-red-900 font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 rounded-sm"
        >
          Delete
        </button>
      )}
    </div>
  );
}
