export type ChatResponseType =
  | "answer"
  | "clarify"
  | "unsupported"
  | "miss"
  | "refusal"
  | "performance_refusal"
  | "rate_limited";

export interface ChatApiResponse {
  type: ChatResponseType;
  text: string;
  citation_url?: string | null;
  last_updated_from_sources?: string | null;
  disclaimer: string;
  scheme_id?: string | null;
  facet?: string | null;
  refusal_kind?: string | null;
  retry_after_seconds?: number | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  responseType?: ChatResponseType;
  citationUrl?: string | null;
  lastUpdated?: string | null;
  isError?: boolean;
}

export const EXAMPLE_QUESTIONS = [
  "What is the expense ratio of Kotak Large Cap Fund – Direct Growth?",
  "What is the exit load for Kotak Flexicap Fund – Direct Growth?",
  "What is the minimum SIP amount for Kotak Liquid Fund?",
] as const;

export const CHIP_LABELS = [
  "Expense ratio — Kotak Large Cap Fund",
  "Exit load — Kotak Flexicap Fund",
  "Minimum SIP — Kotak Liquid Fund",
] as const;

export const SUPPORTED_SCHEMES = [
  "Kotak Large Cap Fund – Direct Growth",
  "Kotak Midcap Fund – Direct Growth",
  "Kotak Arbitrage Fund – Direct Growth",
  "Kotak Savings Fund – Direct Growth",
  "Kotak Gold Fund – Growth Direct",
  "Kotak Flexicap Fund – Direct Growth",
  "Kotak Liquid Fund – Growth Direct",
] as const;

export const DISCLAIMER = "Facts-only. No investment advice.";
