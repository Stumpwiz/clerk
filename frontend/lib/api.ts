// lib/api.ts - API client for communicating with FastAPI backend

import type {Body, Office, Person, Term, LetterTemplate, ApiError} from './types';

const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL ?? "";

class ApiClient {
    private baseUrl: string;

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
    }

    // Ensure we always send a valid JSON body object and coerce empty strings to null
    private toJsonBody(input: Record<string, unknown> | undefined | null): string {
        const obj = (input && typeof input === 'object') ? input : {};
        const normalized: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(obj)) {
            if (typeof v === 'string') {
                // Convert empty strings to null to satisfy backend optional fields
                normalized[k] = v.trim() === '' ? null : v;
            } else {
                normalized[k] = v as unknown;
            }
        }
        return JSON.stringify(normalized);
    }

    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<T> {
        const url = `${this.baseUrl}${endpoint}`;
        const method = (options.method || "GET").toUpperCase();
        const hasBody = options.body !== undefined && options.body !== null;
        const headers = new Headers(options.headers || {});

        // Match browser-simple request behavior when possible.
        // Only send JSON content type when actually submitting a body.
        if (hasBody && method !== "GET" && method !== "HEAD" && !headers.has("Content-Type")) {
            headers.set("Content-Type", "application/json");
        }

        const config: RequestInit = {
            ...options,
            headers,
            credentials: "include",
        };

        const response = await fetch(url, config);

        if (!response.ok) {
            const error = await response.json().catch(() => ({detail: 'Unknown error'})) as ApiError;
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        // Handle 204 No Content
        if (response.status === 204) {
            return {} as T;
        }

        return response.json() as Promise<T>;
    }

    // Bodies
    async getBodies(): Promise<Body[]> {
        return this.request<Body[]>('/api/bodies');
    }

    async getBody(id: number): Promise<Body> {
        return this.request<Body>(`/api/bodies/${id}`);
    }

    async createBody(data: Omit<Body, 'body_id'>): Promise<Body> {
        return this.request<Body>('/api/bodies', {
            method: 'POST',
            body: this.toJsonBody(data as unknown as Record<string, unknown>),
        });
    }

    async updateBody(id: number, data: Partial<Omit<Body, 'body_id'>>): Promise<Body> {
        return this.request<Body>(`/api/bodies/${id}`, {
            method: 'PUT',
            body: this.toJsonBody(data as unknown as Record<string, unknown>),
        });
    }

    async deleteBody(id: number): Promise<void> {
        return this.request<void>(`/api/bodies/${id}`, {
            method: 'DELETE',
        });
    }

    // Offices
    async getOffices(): Promise<Office[]> {
        return this.request<Office[]>('/api/offices');
    }

    async getOffice(id: number): Promise<Office> {
        return this.request<Office>(`/api/offices/${id}`);
    }

    async createOffice(data: Omit<Office, 'office_id'>): Promise<Office> {
        return this.request<Office>('/api/offices', {
            method: 'POST',
            body: this.toJsonBody(data as unknown as Record<string, unknown>),
        });
    }

    async updateOffice(id: number, data: Partial<Omit<Office, 'office_id'>>): Promise<Office> {
        return this.request<Office>(`/api/offices/${id}`, {
            method: 'PUT',
            body: this.toJsonBody(data as unknown as Record<string, unknown>),
        });
    }

    async deleteOffice(id: number): Promise<void> {
        return this.request<void>(`/api/offices/${id}`, {
            method: 'DELETE',
        });
    }

    // Persons
    async getPersons(): Promise<Person[]> {
        return this.request<Person[]>('/api/persons');
    }

    async getPerson(id: number): Promise<Person> {
        return this.request<Person>(`/api/persons/${id}`);
    }

    async createPerson(data: Omit<Person, 'person_id'>): Promise<Person> {
        return this.request<Person>('/api/persons', {
            method: 'POST',
            body: this.toJsonBody(data as unknown as Record<string, unknown>),
        });
    }

    async updatePerson(id: number, data: Partial<Omit<Person, 'person_id'>>): Promise<Person> {
        return this.request<Person>(`/api/persons/${id}`, {
            method: 'PUT',
            body: this.toJsonBody(data as unknown as Record<string, unknown>),
        });
    }

    async deletePerson(id: number): Promise<void> {
        return this.request<void>(`/api/persons/${id}`, {
            method: 'DELETE',
        });
    }

    // Terms
    async getTerms(): Promise<Term[]> {
        return this.request<Term[]>('/api/terms');
    }

    async getTerm(personId: number, officeId: number): Promise<Term> {
        return this.request<Term>(`/api/terms/${personId}/${officeId}`);
    }

    async createTerm(data: Term): Promise<Term> {
        return this.request<Term>('/api/terms', {
            method: 'POST',
            body: this.toJsonBody(data as unknown as Record<string, unknown>),
        });
    }

    async updateTerm(personId: number, officeId: number, data: Partial<Omit<Term, 'term_person_id' | 'term_office_id'>>): Promise<Term> {
        return this.request<Term>(`/api/terms/${personId}/${officeId}`, {
            method: 'PUT',
            body: this.toJsonBody(data as unknown as Record<string, unknown>),
        });
    }

    async deleteTerm(personId: number, officeId: number): Promise<void> {
        return this.request<void>(`/api/terms/${personId}/${officeId}`, {
            method: 'DELETE',
        });
    }

    // Letter Template
    async getLetterTemplate(): Promise<LetterTemplate> {
        return this.request<LetterTemplate>('/api/letter-template');
    }

    async updateLetterTemplate(data: Omit<LetterTemplate, 'id'>): Promise<LetterTemplate> {
        return this.request<LetterTemplate>('/api/letter-template', {
            method: 'PUT',
            body: this.toJsonBody(data as unknown as Record<string, unknown>),
        });
    }
}

export const api = new ApiClient(API_BASE_URL);
