'use client';

import {useState, useEffect} from 'react';
import {Loader2, FileText, Clock, AlertCircle} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface PDFFile {
    filename: string;
    url: string;
}

interface ReportButton {
    id: string;
    label: string;
    endpoint: string;
    filename: string;
    description: string;
}

const REPORTS: ReportButton[] = [
    {
        id: 'long-roster',
        label: 'Long Form Roster',
        endpoint: '/api/reports/long-roster',
        filename: 'long_form_roster.pdf',
        description: 'Complete roster with all details including contact information'
    },
    {
        id: 'short-roster',
        label: 'Short Form Roster',
        endpoint: '/api/reports/short-roster',
        filename: 'short_form_roster.pdf',
        description: 'Condensed roster showing names and offices only'
    },
    {
        id: 'vacancies',
        label: 'Vacancies Report',
        endpoint: '/api/reports/vacancies',
        filename: 'vacancies_report.pdf',
        description: 'List of all currently vacant positions'
    },
    {
        id: 'expirations',
        label: 'Expiring Terms',
        endpoint: '/api/reports/expirations',
        filename: 'expirations_report.pdf',
        description: 'Terms expiring this year'
    }
];

export default function ReportsPage() {
    const [pdfFiles, setPdfFiles] = useState<PDFFile[]>([]);
    const [selectedPdf, setSelectedPdf] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [generatingReports, setGeneratingReports] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadPdfFiles();
    }, []);

    const loadPdfFiles = async () => {
        try {
            setLoading(true);
            setError(null);

            // Fetch list of available PDFs from the backend
            const response = await fetch(`${API_BASE_URL}/api/reports/pdfs`);

            if (!response.ok) {
                throw new Error('Failed to fetch PDF list');
            }

            const data = await response.json();

            // Map to PDFFile format with proper URLs
            const files: PDFFile[] = data.map((file: {filename: string}) => ({
                filename: file.filename,
                url: `${API_BASE_URL}/api/reports/pdfs/${file.filename}`
            }));

            setPdfFiles(files);
        } catch (error) {
            console.error('Error loading PDF files:', error);
            setError('Failed to load available reports');
        } finally {
            setLoading(false);
        }
    };

    const handleGenerateReport = async (report: ReportButton) => {
        setGeneratingReports(prev => new Set(prev).add(report.id));
        setError(null);

        try {
            const response = await fetch(`${API_BASE_URL}${report.endpoint}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Report generated successfully
            await loadPdfFiles();

            // Auto-select the newly generated report
            setSelectedPdf(report.filename);

        } catch (error) {
            console.error(`Error generating ${report.label}:`, error);
            setError(`Failed to generate ${report.label}: ${error}`);
        } finally {
            setGeneratingReports(prev => {
                const newSet = new Set(prev);
                newSet.delete(report.id);
                return newSet;
            });
        }
    };

    const handleViewPdf = () => {
        if (!selectedPdf) {
            alert('Please select a report to view.');
            return;
        }

        const pdfFile = pdfFiles.find(f => f.filename === selectedPdf);
        if (pdfFile) {
            window.open(pdfFile.url, '_blank');
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
                <h1 className="text-3xl font-bold text-gray-900">Rosters & Reports</h1>
                <p className="mt-2 text-sm text-gray-600">
                    Generate and view rosters and reports from the database
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
                        onClick={() => setError(null)}
                        className="text-red-600 hover:text-red-800"
                    >
                        ×
                    </button>
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Left Column - Generate Reports */}
                <div className="bg-white shadow rounded-lg">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <h2 className="text-xl font-semibold text-gray-900">Generate Reports</h2>
                        <p className="mt-1 text-sm text-gray-600">
                            Click to generate or refresh reports
                        </p>
                    </div>
                    <div className="p-6">
                        <div className="space-y-4">
                            {REPORTS.map((report) => {
                                const isGenerating = generatingReports.has(report.id);

                                return (
                                    <div key={report.id}
                                         className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors">
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <h3 className="text-sm font-medium text-gray-900">
                                                    {report.label}
                                                </h3>
                                                <p className="mt-1 text-xs text-gray-500">
                                                    {report.description}
                                                </p>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => handleGenerateReport(report)}
                                                disabled={isGenerating}
                                                className="ml-4 inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                                            >
                                                {isGenerating ? (
                                                    <>
                                                        <Loader2 className="animate-spin h-4 w-4 mr-1"/>
                                                        Generating...
                                                    </>
                                                ) : (
                                                    <>
                                                        <FileText className="h-4 w-4 mr-1"/>
                                                        Generate
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
                                    <h4 className="text-sm font-medium text-blue-900">About Reports</h4>
                                    <p className="mt-1 text-sm text-blue-700">
                                        Reports are generated from the current database. Generating a report
                                        will overwrite any previous version with the latest data.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Column - Available Reports */}
                <div className="bg-white shadow rounded-lg">
                    <div className="px-6 py-4 border-b border-gray-200">
                        <h2 className="text-xl font-semibold text-gray-900">Available Reports</h2>
                        <p className="mt-1 text-sm text-gray-600">
                            Select a report to view or download
                        </p>
                    </div>
                                                <div className="p-6">
                        {pdfFiles.length > 0 ? (
                            <>
                                <div className="mb-4">
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Select a report:
                                    </label>
                                    <div className="border border-gray-300 rounded-md overflow-y-auto"
                                         style={{maxHeight: '300px'}}>
                                        <div className="divide-y divide-gray-200">
                                            {pdfFiles.map((pdf) => (
                                                <button
                                                    key={pdf.filename}
                                                    type="button"
                                                    onClick={() => setSelectedPdf(pdf.filename)}
                                                    className={`w-full text-left px-4 py-3 text-sm hover:bg-gray-50 transition-colors ${
                                                        selectedPdf === pdf.filename
                                                            ? 'bg-blue-50 text-blue-700 font-medium'
                                                            : 'text-gray-900'
                                                    }`}
                                                >
                                                    <div className="flex items-center">
                                                        <FileText className="h-4 w-4 mr-2 flex-shrink-0"/>
                                                        <span className="truncate">{pdf.filename}</span>
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                <div className="flex justify-center gap-4 mt-4 pt-4 border-t border-gray-200">
                                    <button
                                        type="button"
                                        onClick={handleViewPdf}
                                        disabled={!selectedPdf}
                                        className="px-6 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        View PDF
                                    </button>
                                </div>
                            </>
                        ) : (
                            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
                                <div className="flex">
                                    <AlertCircle className="h-5 w-5 text-yellow-600 mr-3 flex-shrink-0"/>
                                    <div>
                                        <h4 className="text-sm font-medium text-yellow-900">No Reports Generated</h4>
                                        <p className="mt-1 text-sm text-yellow-700">
                                            Click the Generate buttons to create reports from the current database.
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
