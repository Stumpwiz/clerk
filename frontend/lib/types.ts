// lib/types.ts - TypeScript types for API data

export interface Body {
  body_id: number;
  name: string;
  mission: string | null;
  body_precedence: number;
}

export interface Office {
  office_id: number;
  title: string | null;
  office_precedence: number | null;
  office_body_id: number;
}

export interface Person {
  person_id: number;
  first: string | null;
  last: string | null;
  email: string | null;
  phone: string | null;
  apt: string | null;
}

export interface Term {
  term_person_id: number;
  term_office_id: number;
  start: string | null;
  end: string | null;
  ordinal: string | null;
}

export interface LetterTemplate {
  id: number | null;
  body: string;
}

export interface ApiError {
  detail: string;
}
