// lib/api.ts - API client for communicating with FastAPI backend

import type { Body, Office, Person, Term, LetterTemplate, ApiError } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    const config: RequestInit = {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    };

    const response = await fetch(url, config);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' })) as ApiError;
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
      body: JSON.stringify(data),
    });
  }

  async updateBody(id: number, data: Partial<Omit<Body, 'body_id'>>): Promise<Body> {
    return this.request<Body>(`/api/bodies/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
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
      body: JSON.stringify(data),
    });
  }

  async updateOffice(id: number, data: Partial<Omit<Office, 'office_id'>>): Promise<Office> {
    return this.request<Office>(`/api/offices/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
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
      body: JSON.stringify(data),
    });
  }

  async updatePerson(id: number, data: Partial<Omit<Person, 'person_id'>>): Promise<Person> {
    return this.request<Person>(`/api/persons/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
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
      body: JSON.stringify(data),
    });
  }

  async updateTerm(personId: number, officeId: number, data: Partial<Omit<Term, 'term_person_id' | 'term_office_id'>>): Promise<Term> {
    return this.request<Term>(`/api/terms/${personId}/${officeId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
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
      body: JSON.stringify(data),
    });
  }
}

export const api = new ApiClient(API_BASE_URL);