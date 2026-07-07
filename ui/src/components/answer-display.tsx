import { useState } from "react"
import { FileText, Clock, Hash, ChevronDown, ChevronUp } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import type { ChunkRefV1, QueryResponseV1, RetrievedChunkV1 } from "@/types/api"

/** Debe coincidir con el recorte en `core/src/rag/generation.py` (evidencia al LLM). */
const LLM_CONTEXT_CHAR_LIMIT = 400

function pickStr(o: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const k of keys) {
    const v = o[k]
    if (typeof v === "string" && v.length > 0) return v
  }
}

function pickNum(o: Record<string, unknown>, key: string, fallback: number): number {
  const v = o[key]
  if (typeof v === "number" && !Number.isNaN(v)) return v
  if (typeof v === "string") {
    const n = Number(v)
    if (!Number.isNaN(n)) return n
  }
  return fallback
}

function readNumList(o: Record<string, unknown>, ...keys: string[]): number[] | undefined {
  for (const k of keys) {
    const v = o[k]
    if (!Array.isArray(v)) continue
    const nums = v.filter((x): x is number => typeof x === "number")
    if (nums.length > 0) return nums
  }
  return undefined
}

function readStrList(o: Record<string, unknown>, ...keys: string[]): string[] | undefined {
  for (const k of keys) {
    const v = o[k]
    if (!Array.isArray(v)) continue
    const s = v.filter((x): x is string => typeof x === "string")
    if (s.length > 0) return s
  }
  return undefined
}

function readOptionalInt(o: Record<string, unknown>, snake: string, camel: string): number | undefined {
  const v = o[snake] ?? o[camel]
  if (typeof v === "number" && !Number.isNaN(v)) return v
  if (typeof v === "string") {
    const n = Number(v)
    if (!Number.isNaN(n)) return n
  }
  return undefined
}

function coerceChunkRef(src: Record<string, unknown>): ChunkRefV1 | null {
  const document_id = pickStr(src, "document_id", "documentId")
  const chunk_id = pickStr(src, "chunk_id", "chunkId")
  const source_path = pickStr(src, "source_path", "sourcePath") ?? ""
  if (!document_id || !chunk_id) return null
  let version = pickNum(src, "version", 1)
  if (version < 1) version = 1
  return {
    document_id,
    version,
    chunk_id,
    source_path,
    source_file: pickStr(src, "source_file", "sourceFile"),
    pages: readNumList(src, "pages"),
    first_page: readOptionalInt(src, "first_page", "firstPage"),
    headings: readStrList(src, "headings"),
  }
}

function coerceRetrievedChunkV1(row: unknown): RetrievedChunkV1 | null {
  if (typeof row !== "object" || row === null) return null
  const o = row as Record<string, unknown>
  if (typeof o.text !== "string") return null
  const score = typeof o.score === "number" && !Number.isNaN(o.score) ? o.score : 0

  const refRaw = o.ref
  if (typeof refRaw === "object" && refRaw !== null) {
    const ref = coerceChunkRef(refRaw as Record<string, unknown>)
    if (ref) return { ref, text: o.text, score }
  }
  const flatRef = coerceChunkRef(o)
  if (flatRef) return { ref: flatRef, text: o.text, score }
  return null
}

function isFlatChunkRef(row: unknown): row is ChunkRefV1 {
  if (typeof row !== "object" || row === null) return false
  const o = row as Record<string, unknown>
  return typeof o.chunk_id === "string" && typeof o.document_id === "string" && !("ref" in o)
}

function unparseableRetrievedChunks(count: number): RetrievedChunkV1[] {
  return [
    {
      ref: {
        document_id: "_",
        version: 1,
        chunk_id: "_",
        source_path: "",
      },
      text:
        `El servidor envió ${count} elemento(s) en «retrieved_chunks» en un formato que la UI no reconoce (revisá mayúsculas en claves o anidación de «ref»). Forzá recarga sin caché (Ctrl+F5) y comprobá en Red la respuesta JSON de /v1/query.`,
      score: 0,
    },
  ]
}

function legacyRefsWithoutText(refs: ChunkRefV1[]): RetrievedChunkV1[] {
  return refs.map((ref) => ({
    ref,
    text:
      "Este proceso de API no expone el texto del fragmento en JSON (solo referencias). Pará Uvicorn y volvé a levantarlo desde la carpeta «core» con el código actual: la respuesta debe incluir «retrieved_chunks» con «text» por ítem.",
    score: 0,
  }))
}

/**
 * Prioriza `retrieved_chunks`. Si viene no vacío pero no se puede parsear, no usa `chunks`
 * (evita mostrar el placeholder cuando el servidor nuevo manda ambos campos).
 */
function normalizeRetrievedChunks(response: QueryResponseV1): RetrievedChunkV1[] {
  const bag = response as unknown as Record<string, unknown>
  const modern = bag.retrieved_chunks ?? bag.retrievedChunks
  if (Array.isArray(modern) && modern.length > 0) {
    const mapped = modern.map(coerceRetrievedChunkV1).filter((x): x is RetrievedChunkV1 => x !== null)
    if (mapped.length > 0) return mapped
    return unparseableRetrievedChunks(modern.length)
  }

  const legacy = response.chunks
  if (!Array.isArray(legacy) || legacy.length === 0) return []

  const coerced = legacy.map(coerceRetrievedChunkV1).filter((x): x is RetrievedChunkV1 => x !== null)
  if (coerced.length > 0) return coerced
  if (isFlatChunkRef(legacy[0])) return legacyRefsWithoutText(legacy as ChunkRefV1[])
  return []
}

interface CitationChipProps {
  chunk: RetrievedChunkV1
  index: number
}

function CitationChip({ chunk, index }: CitationChipProps) {
  const [expanded, setExpanded] = useState(false)
  const ref = chunk.ref
  const label = ref.source_file ?? ref.source_path.split("/").pop() ?? "Fuente"
  const pages = ref.pages?.length
    ? ref.pages.length === 1
      ? `p. ${ref.pages[0]}`
      : `pp. ${ref.pages[0]}–${ref.pages[ref.pages.length - 1]}`
    : null
  const preview = chunk.text.slice(0, LLM_CONTEXT_CHAR_LIMIT)
  const truncatedForLlm = chunk.text.length > LLM_CONTEXT_CHAR_LIMIT

  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[var(--color-accent)] transition-colors"
      >
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-primary)] text-[var(--color-primary-foreground)] text-xs font-bold">
          {index + 1}
        </span>
        <FileText className="h-3.5 w-3.5 shrink-0 text-[var(--color-muted-foreground)]" />
        <span className="flex-1 truncate font-medium text-[var(--color-foreground)]" title={label}>
          {label}
        </span>
        {pages && (
          <Badge variant="secondary" className="shrink-0 text-xs">
            {pages}
          </Badge>
        )}
        <Badge variant="outline" className="hidden shrink-0 text-xs sm:inline-flex">
          score {chunk.score.toFixed(3)}
        </Badge>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 shrink-0 text-[var(--color-muted-foreground)]" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[var(--color-muted-foreground)]" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-[var(--color-border)] bg-[var(--color-muted)]/30 px-3 py-2 space-y-2">
          {ref.headings && ref.headings.length > 0 && (
            <p className="text-xs font-medium text-[var(--color-muted-foreground)]">
              {ref.headings.join(" › ")}
            </p>
          )}
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-muted-foreground)]">
              Texto recuperado (fragmento completo)
            </p>
            <div className="max-h-56 overflow-y-auto rounded border border-[var(--color-border)] bg-[var(--color-card)] px-2 py-1.5">
              <p className="text-xs text-[var(--color-foreground)] leading-relaxed whitespace-pre-wrap">
                {chunk.text}
              </p>
            </div>
          </div>
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-muted-foreground)]">
              Incluido en el prompt del modelo (primeros {LLM_CONTEXT_CHAR_LIMIT} caracteres)
            </p>
            <div className="max-h-40 overflow-y-auto rounded border border-dashed border-[var(--color-border)] bg-[var(--color-card)]/80 px-2 py-1.5">
              <p className="text-xs text-[var(--color-foreground)] leading-relaxed whitespace-pre-wrap">
                {preview}
                {truncatedForLlm ? "…" : ""}
              </p>
            </div>
            {truncatedForLlm && (
              <p className="mt-1 text-[10px] text-[var(--color-muted-foreground)]">
                El fragmento es más largo; el modelo solo ve el bloque anterior, no el texto completo.
              </p>
            )}
          </div>
          <p className="text-[10px] text-[var(--color-muted-foreground)]">
            ID: <span className="font-mono text-[var(--color-foreground)]">{ref.chunk_id}</span>
          </p>
        </div>
      )}
    </div>
  )
}

interface AnswerDisplayProps {
  response: QueryResponseV1
}

export function AnswerDisplay({ response }: AnswerDisplayProps) {
  const chunks = normalizeRetrievedChunks(response)

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5">
      {/* Answer text */}
      <p className="text-sm leading-relaxed whitespace-pre-wrap text-[var(--color-foreground)]">
        {response.answer}
      </p>

      {/* Citations + retrieved text (siempre visible: con datos o explicación) */}
      <div className="flex flex-col gap-2">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-muted-foreground)]">
            Fragmentos recuperados
          </h3>
          {chunks.length > 0 ? (
            <p className="mt-0.5 text-[11px] text-[var(--color-muted-foreground)] leading-snug">
              Orden final tras rerank; expandí cada uno para ver el texto íntegro y los primeros{" "}
              {LLM_CONTEXT_CHAR_LIMIT} caracteres que recibe el modelo.
            </p>
          ) : (
            <p className="mt-0.5 text-[11px] text-[var(--color-muted-foreground)] leading-snug">
              La consulta no devolvió fragmentos (lista vacía). El modelo respondió sin evidencia indexada o tu API no
              expone <span className="font-mono">retrieved_chunks</span>. Reiniciá el backend y comprobá indexación y
              umbrales de búsqueda.
            </p>
          )}
        </div>
        {chunks.length > 0 ? (
          <div className="flex flex-col gap-1.5">
            {chunks.map((chunk, i) => (
              <CitationChip
                key={`${chunk.ref.document_id}-${chunk.ref.chunk_id}-${i}`}
                chunk={chunk}
                index={i}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-md border border-dashed border-[var(--color-border)] bg-[var(--color-muted)]/20 px-3 py-2 text-xs text-[var(--color-muted-foreground)]">
            Sin chunks en la respuesta JSON. Si antes veías “Fuentes citadas” y ahora no, casi seguro el servidor sigue
            en una versión que solo manda <span className="font-mono">chunks</span> sin texto: actualizá y reiniciá el
            API, o recargá la UI tras el build.
          </div>
        )}
      </div>

      {/* Footer: timing + correlation id */}
      <div className="flex items-center gap-4 border-t border-[var(--color-border)] pt-3 text-xs text-[var(--color-muted-foreground)]">
        <span className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {response.total_ms.toFixed(0)} ms
        </span>
        <span className="flex items-center gap-1 truncate">
          <Hash className="h-3 w-3 shrink-0" />
          <span className="truncate">{response.correlation_id}</span>
        </span>
      </div>
    </div>
  )
}
