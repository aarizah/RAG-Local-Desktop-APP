// TypeScript types mirroring core/src/contracts.py

export type ErrorCode =
  | "INVALID_REQUEST"
  | "GENERATION_FAILED"
  | "INGESTION_FAILED"
  | "DUPLICATE_DOCUMENT"

export interface ApiErrorV1 {
  code: ErrorCode
  message: string
  correlation_id?: string
}

export interface ChunkRefV1 {
  document_id: string
  version: number
  chunk_id: string
  source_path: string
  source_file?: string
  pages?: number[]
  first_page?: number
  headings?: string[]
}

export interface RetrievedChunkV1 {
  ref: ChunkRefV1
  text: string
  score: number
}

export interface QueryRequestV1 {
  query: string
}

export interface QueryResponseV1 {
  answer: string
  citations: string[]
  /** Fragmentos con texto (API actual). */
  retrieved_chunks?: RetrievedChunkV1[]
  /** Refs por fragmento (API actual también lo envía por compatibilidad). */
  chunks?: ChunkRefV1[]
  correlation_id: string
  total_ms: number
}

export interface IngestResponseV1 {
  document_id: string
  version: number
  status: string
  content_hash: string
  created_at: string
  chunks_indexed: number
}

export interface DocumentItemV1 {
  document_id: string
  version: number
  source_file: string
  content_hash: string
  status: string
  created_at: string
}

export interface DocumentListResponseV1 {
  documents: DocumentItemV1[]
  total: number
}

/** Structured error returned by the API on 4xx/5xx */
export interface ApiHttpError {
  status: number
  detail: ApiErrorV1 | string
}
