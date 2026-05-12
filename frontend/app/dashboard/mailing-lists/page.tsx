'use client';

import {useCallback, useEffect, useState} from 'react';
import {AlertCircle, Clock, FileText, Loader2} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface MailingListButton {
    id: string;
    label: string;
    endpoint: string;
    filename: string;
    description: string;
}

interface MailingListMetadata {
    id: string;
    label: string;
    description: string;
    filename: string;
    renderer_type: string;
}

export default function MailingListsPage() {
    const [listsRegistry, setListsRegistry] = useState<MailingListButton[]>([]);
    const [selectedList, setSelectedList] = useState<string | null>(null);
    const [loadingRegistry, setLoadingRegistry] = useState(true);
    const [generatingLists, setGeneratingLists] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);

    const loadListsRegistry = useCallback(async () => {
        try {
            setLoadingRegistry(true);
            const response = await fetch(`${API_BASE_URL}/api/mailing-lists`);

            if (!response.ok) {
                throw new Error('Failed to fetch mailing lists registry');
            }

            const data: MailingListMetadata[] = await response.json();
            const mappedLists: MailingListButton[] = data.map((item) => ({
                id: item.id,
                label: item.label,
                endpoint: `/api/mailing-lists/${item.id}`,
                filename: item.filename,
                description: item.description,
            }));

            mappedLists.sort((a, b) => a.label.localeCompare(b.label));
            setListsRegistry(mappedLists);
            setSelectedList((current) => current ?? mappedLists[0]?.id ?? null);
        } catch (err) {
            console.error('Error loading mailing lists registry:', err);
            setError('Failed to load mailing lists registry from backend');
        } finally {
            setLoadingRegistry(false);
        }
    }, []);

    useEffect(() => {
        loadListsRegistry();
    }, [loadListsRegistry]);

    const handleGenerateList = async (list: MailingListButton) => {
        setGeneratingLists((prev) => new Set(prev).add(list.id));
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}${list.endpoint}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            setSelectedList(list.id);
        } catch (err) {
            console.error(`Error refreshing ${list.label}:`, err);
            setError(`Failed to refresh ${list.label}: ${err}`);
        } finally {
            setGeneratingLists((prev) => {
                const next = new Set(prev);
                next.delete(list.id);
                return next;
            });
        }
    };

    const handleViewList = async () => {
        if (!selectedList) {
            alert('Please select a mailing list to view.');
            return;
        }

        const selected = listsRegistry.find((list) => list.id === selectedList);
        if (!selected) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}${selected.endpoint}?_=${Date.now()}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const content = await response.text();
            const blob = new Blob([content], {type: 'text/plain;charset=utf-8'});
            const url = URL.createObjectURL(blob);
            window.open(url, '_blank', 'noopener,noreferrer');
            setTimeout(() => URL.revokeObjectURL(url), 60_000);
        } catch (err) {
            console.error(`Error viewing ${selected.label}:`, err);
            setError(`Failed to view ${selected.label}: ${err}`);
        }
    };

    if (loadingRegistry) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600"/>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold text-gray-900">Mailing Lists</h1>
                <p className="mt-2 text-sm text-gray-600">
                    Refresh and view mailing lists generated from the current database
                </p>
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4 flex items-start">
                    <AlertCircle className="h-5 w-5 text-red-600 mr-3 mt-0.5"/>
                    <div className="flex-1">
                        <h3 className="text-sm font-medium text-red-800">Error</h3>
                        <p className="mt-1 text-sm text-red-700">{error}</p>
                    </div>
                    <button
                        type="button"
                        onClick={() => setError(null)}
                        className="text-red-600 hover:text-red-800"
                    >
                        ×
                    </button>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white shadow rounded-lg">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <h2 className="text-xl font-semibold text-gray-900">Refresh Mailing Lists</h2>
                        <p className="mt-1 text-sm text-gray-600">
                            Click to refresh a mailing list with the latest data
                        </p>
                    </div>
                    <div className="p-6">
                        <div className="space-y-4">
                            {listsRegistry.map((list) => {
                                const isGenerating = generatingLists.has(list.id);
                                return (
                                    <div
                                        key={list.id}
                                        className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <h3 className="text-sm font-medium text-gray-900">
                                                    {list.label}
                                                </h3>
                                                <p className="mt-1 text-xs text-gray-500">
                                                    {list.description}
                                                </p>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => handleGenerateList(list)}
                                                disabled={isGenerating}
                                                className="ml-4 inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                {isGenerating ? (
                                                    <>
                                                        <Loader2 className="animate-spin h-4 w-4 mr-1"/>
                                                        Refreshing...
                                                    </>
                                                ) : (
                                                    <>
                                                        <FileText className="h-4 w-4 mr-1"/>
                                                        Refresh
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-md p-4">
                            <div className="flex">
                                <Clock className="h-5 w-5 text-blue-600 mr-3 flex-shrink-0"/>
                                <div>
                                    <h4 className="text-sm font-medium text-blue-900">About Mailing Lists</h4>
                                    <p className="mt-1 text-sm text-blue-700">
                                        Mailing lists are generated as Outlook-ready plain text with one email per line.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="bg-white shadow rounded-lg">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <h2 className="text-xl font-semibold text-gray-900">Available Mailing Lists</h2>
                        <p className="mt-1 text-sm text-gray-600">
                            Select a mailing list and open it as plain text
                        </p>
                    </div>
                    <div className="p-6">
                        {listsRegistry.length > 0 ? (
                            <>
                                <div className="mb-4">
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Select a mailing list:
                                    </label>
                                    <div className="border border-gray-300 rounded-md overflow-y-auto"
                                         style={{maxHeight: '300px'}}>
                                        <div className="divide-y divide-gray-200">
                                            {listsRegistry.map((list) => (
                                                <button
                                                    key={list.id}
                                                    type="button"
                                                    onClick={() => setSelectedList(list.id)}
                                                    className={`w-full text-left px-4 py-3 text-sm hover:bg-gray-50 transition-colors ${
                                                        selectedList === list.id
                                                            ? 'bg-blue-50 text-blue-700 font-medium'
                                                            : 'text-gray-900'
                                                    }`}
                                                >
                                                    <div className="flex items-center">
                                                        <FileText className="h-4 w-4 mr-2 flex-shrink-0"/>
                                                        <span className="truncate">{list.label}</span>
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                <div className="flex justify-center gap-4 mt-4 pt-4 border-t border-gray-200">
                                    <button
                                        type="button"
                                        onClick={handleViewList}
                                        disabled={!selectedList}
                                        className="px-6 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        View
                                    </button>
                                </div>
                            </>
                        ) : (
                            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
                                <div className="flex">
                                    <AlertCircle className="h-5 w-5 text-yellow-600 mr-3 flex-shrink-0"/>
                                    <div>
                                        <h4 className="text-sm font-medium text-yellow-900">No Mailing Lists Available</h4>
                                        <p className="mt-1 text-sm text-yellow-700">
                                            No mailing-list metadata was returned by the backend.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
