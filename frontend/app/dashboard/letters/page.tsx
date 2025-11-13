'use client';

import {useState, useEffect} from 'react';
import {Loader2} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface LetterTemplate {
    id: number | null;
    header: string;
    body: string;
}

interface PDFFile {
    filename: string;
    date_prefix: string | null;
}

interface GenerateLetterRequest {
    recipient: string;
    salutation: string;
    apartment: string;
    letter_date: string;
}

export default function LettersPage() {
    const [template, setTemplate] = useState<LetterTemplate | null>(null);
    const [pdfFiles, setPdfFiles] = useState<PDFFile[]>([]);
    const [selectedPdf, setSelectedPdf] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [showEditModal, setShowEditModal] = useState(false);

    // Form states
    const [letterDate, setLetterDate] = useState('');
    const [recipient, setRecipient] = useState('');
    const [salutation, setSalutation] = useState('');
    const [apartment, setApartment] = useState('');
    const [dateError, setDateError] = useState('');

    // Edit modal states
    const [editHeader, setEditHeader] = useState('');
    const [editBody, setEditBody] = useState('');

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            setLoading(true);
            await Promise.all([loadTemplate(), loadPdfs()]);
        } catch (error) {
            console.error('Error loading data:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadTemplate = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/letters/template`);
            if (response.ok) {
                const data = await response.json();
                setTemplate(data);
                setEditHeader(data.header);
                setEditBody(data.body);
            }
        } catch (error) {
            console.error('Error loading template:', error);
        }
    };

    const loadPdfs = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/letters/pdfs`);
            if (response.ok) {
                const data = await response.json();
                setPdfFiles(data);
            }
        } catch (error) {
            console.error('Error loading PDFs:', error);
        }
    };

    const validateDate = (dateStr: string): boolean => {
        setDateError('');

        if (!dateStr) {
            setDateError('Letter Date is required.');
            return false;
        }

        const isoPattern = /^\d{4}-\d{2}-\d{2}$/;
        if (!isoPattern.test(dateStr)) {
            setDateError('Date must match YYYY-MM-DD.');
            return false;
        }

        const [y, m, d] = dateStr.split('-').map(Number);
        const dt = new Date(Date.UTC(y, m - 1, d));
        if (dt.getUTCFullYear() !== y || (dt.getUTCMonth() + 1) !== m || dt.getUTCDate() !== d) {
            setDateError('Please enter a valid calendar date.');
            return false;
        }

        return true;
    };

    const handleGenerateLetter = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!validateDate(letterDate)) {
            return;
        }

        if (!recipient || !salutation || !apartment) {
            alert('Please fill in all fields.');
            return;
        }

        setGenerating(true);

        try {
            const request: GenerateLetterRequest = {
                recipient,
                salutation,
                apartment,
                letter_date: letterDate,
            };

            const response = await fetch(`${API_BASE_URL}/api/letters/generate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(request),
            });

            const result = await response.json();

            if (result.success) {
                alert('Letter generated successfully! Use the buttons to view or delete the PDF.');
                await loadPdfs();
                setLetterDate('');
                setRecipient('');
                setSalutation('');
                setApartment('');
            } else {
                alert(`Failed to generate PDF: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            alert(`Failed to generate PDF: ${error}`);
        } finally {
            setGenerating(false);
        }
    };

    const handleUpdateTemplate = async (e: React.FormEvent) => {
        e.preventDefault();

        try {
            const response = await fetch(`${API_BASE_URL}/api/letters/template`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    header: editHeader,
                    body: editBody,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setTemplate(data);
                setShowEditModal(false);
                alert('Template updated successfully!');
            } else {
                alert('Failed to update template.');
            }
        } catch (error) {
            alert(`Error updating template: ${error}`);
        }
    };

    const handleViewPdf = () => {
        if (!selectedPdf) {
            alert('Please select a PDF file.');
            return;
        }
        window.open(`${API_BASE_URL}/api/letters/pdfs/${selectedPdf}`, '_blank');
    };

    const handleDeletePdf = async () => {
        if (!selectedPdf) {
            alert('Please select a PDF file.');
            return;
        }

        if (!confirm(`Are you sure you want to delete ${selectedPdf}?`)) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE_URL}/api/letters/pdfs/${selectedPdf}`, {
                method: 'DELETE',
            });

            if (response.ok) {
                alert('PDF deleted successfully!');
                setSelectedPdf(null);
                await loadPdfs();
            } else {
                alert('Failed to delete PDF.');
            }
        } catch (error) {
            alert(`Error deleting PDF: ${error}`);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600"/>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold text-gray-900">Letters and Template Management</h1>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white shadow rounded-lg">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <h2 className="text-xl font-semibold text-gray-900">Generate Letter</h2>
                    </div>
                    <div className="p-6">
                        <form onSubmit={handleGenerateLetter} className="space-y-4">
                            <div>
                                <label htmlFor="letter_date" className="block text-sm font-medium text-gray-700">
                                    Letter Date
                                </label>
                                <input
                                    type="text"
                                    id="letter_date"
                                    value={letterDate}
                                    onChange={(e) => setLetterDate(e.target.value)}
                                    onBlur={(e) => validateDate(e.target.value)}
                                    placeholder="Letter Date (e.g., 2025-09-15)"
                                    required
                                    className={`mt-1 block w-full rounded-md shadow-sm sm:text-sm text-gray-900 placeholder-gray-400 ${
                                        dateError
                                            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                                            : 'border-gray-300 focus:border-blue-500 focus:ring-blue-500'
                                    }`}
                                />
                                <p className="mt-1 text-xs text-gray-500">Format: YYYY-MM-DD</p>
                                {dateError && <p className="mt-1 text-sm text-red-600">{dateError}</p>}
                            </div>

                            <div>
                                <label htmlFor="recipient" className="block text-sm font-medium text-gray-700">
                                    Recipient(s)
                                </label>
                                <input
                                    type="text"
                                    id="recipient"
                                    value={recipient}
                                    onChange={(e) => setRecipient(e.target.value)}
                                    required
                                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm text-gray-900 placeholder-gray-400"
                                />
                                <p className="mt-1 text-xs text-gray-500">Format: &quot;John and Mary
                                    Smith&quot; or &quot;John Smith&quot;</p>
                            </div>

                            <div>
                                <label htmlFor="salutation" className="block text-sm font-medium text-gray-700">
                                    Salutation
                                </label>
                                <input
                                    type="text"
                                    id="salutation"
                                    value={salutation}
                                    onChange={(e) => setSalutation(e.target.value)}
                                    required
                                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm text-gray-900 placeholder-gray-400"
                                />
                                <p className="mt-1 text-xs text-gray-500">Format: No &quot;Dear&quot;; &quot;John and
                                    Mary&quot; or nickname</p>
                            </div>

                            <div>
                                <label htmlFor="apartment" className="block text-sm font-medium text-gray-700">
                                    Apartment
                                </label>
                                <input
                                    type="text"
                                    id="apartment"
                                    value={apartment}
                                    onChange={(e) => setApartment(e.target.value)}
                                    required
                                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm text-gray-900 placeholder-gray-400"
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={generating}
                                className="w-full flex justify-center items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50"
                            >
                                {generating ? (
                                    <>
                                        <Loader2 className="animate-spin -ml-1 mr-2 h-4 w-4"/>
                                        Generating...
                                    </>
                                ) : (
                                    'Generate Letter'
                                )}
                            </button>
                        </form>
                    </div>
                </div>

                <div className="bg-white shadow rounded-lg">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <h2 className="text-xl font-semibold text-gray-900">Available Letters</h2>
                    </div>
                    <div className="p-6 flex flex-col h-full">
                        {pdfFiles.length > 0 ? (
                            <>
                                <div className="mb-4">
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Select a PDF file:
                                    </label>
                                    <div className="border border-gray-300 rounded-md overflow-y-auto"
                                         style={{height: '200px'}}>
                                        <div className="divide-y divide-gray-200">
                                            {pdfFiles.map((pdf) => (
                                                <button
                                                    key={pdf.filename}
                                                    type="button"
                                                    onClick={() => setSelectedPdf(pdf.filename)}
                                                    className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-50 ${
                                                        selectedPdf === pdf.filename ? 'bg-blue-50 text-blue-700' : 'text-gray-900'
                                                    }`}
                                                >
                                                    {pdf.filename}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                                <div className="flex justify-around mt-auto">
                                    <button
                                        type="button"
                                        onClick={handleViewPdf}
                                        className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                                    >
                                        View
                                    </button>
                                    <button
                                        type="button"
                                        onClick={handleDeletePdf}
                                        className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                                    >
                                        Delete
                                    </button>
                                </div>
                            </>
                        ) : (
                            <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
                                <p className="text-sm text-blue-700">No PDF files found in the files_letters
                                    directory.</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="bg-white shadow rounded-lg">
                <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                    <h2 className="text-xl font-semibold text-gray-900">Current Template</h2>
                    <span className="text-sm text-gray-500"
                          title="Don't edit this LaTeX source code unless you know what you're doing">
                        ⓘ
                    </span>
                </div>
                <div className="p-6">
                    {template && template.id ? (
                        <>
                            <div className="mb-4">
                                <h3 className="text-lg font-medium text-gray-900 mb-2">Header</h3>
                                <pre
                                    className="bg-gray-100 border border-gray-400 rounded-md p-4 text-sm overflow-x-auto text-gray-900 font-mono">
                                    {template.header}
                                </pre>
                            </div>
                            <div className="mb-4">
                                <h3 className="text-lg font-medium text-gray-900 mb-2">Body</h3>
                                <pre
                                    className="bg-gray-100 border border-gray-400 rounded-md p-4 text-sm overflow-x-auto text-gray-900 font-mono">
                                    {template.body}
                                </pre>
                            </div>
                            <button
                                type="button"
                                onClick={() => setShowEditModal(true)}
                                className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                            >
                                Edit Template
                            </button>
                        </>
                    ) : (
                        <>
                            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4 mb-4">
                                <p className="text-sm text-yellow-700">No letter template found. Please initialize a
                                    template.</p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setShowEditModal(true)}
                                className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                            >
                                Create Template
                            </button>
                        </>
                    )}
                </div>
            </div>

            {showEditModal && (
                <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <h3 className="text-lg font-medium text-gray-900">
                                {template && template.id ? 'Edit Letter Template' : 'Create Letter Template'}
                            </h3>
                        </div>
                        <form onSubmit={handleUpdateTemplate}>
                            <div className="p-6 space-y-4">
                                <div>
                                    <label htmlFor="edit_header" className="block text-sm font-medium text-gray-700">
                                        Header
                                    </label>
                                    <textarea
                                        id="edit_header"
                                        value={editHeader}
                                        onChange={(e) => setEditHeader(e.target.value)}
                                        rows={5}
                                        required
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono text-gray-900"
                                    />
                                    <p className="mt-1 text-xs text-gray-500">Use \\ for LaTeX commands</p>
                                </div>
                                <div>
                                    <label htmlFor="edit_body" className="block text-sm font-medium text-gray-700">
                                        Body
                                    </label>
                                    <textarea
                                        id="edit_body"
                                        value={editBody}
                                        onChange={(e) => setEditBody(e.target.value)}
                                        rows={10}
                                        required
                                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm font-mono text-gray-900"
                                    />
                                    <p className="mt-1 text-xs text-gray-500">Use \\ for LaTeX commands</p>
                                </div>
                            </div>
                            <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowEditModal(false);
                                        setEditHeader(template?.header || '');
                                        setEditBody(template?.body || '');
                                    }}
                                    className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                                >
                                    {template && template.id ? 'Save Changes' : 'Create Template'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}