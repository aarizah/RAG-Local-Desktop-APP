import { useState } from "react"
import { Send } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useQueryRag } from "@/hooks/use-query-rag"
import type { QueryResponseV1 } from "@/types/api"
import { AnswerDisplay } from "./answer-display"

export function QueryPanel() {
  const [query, setQuery] = useState("")

  const { mutate, isPending, data, error, reset } = useQueryRag()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || isPending) return
    reset()
    mutate({ query: query.trim() })
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div className="flex gap-2">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                handleSubmit(e as unknown as React.FormEvent)
              }
            }}
            placeholder="Escribe tu pregunta… (Enter para enviar, Shift+Enter para nueva línea)"
            rows={3}
            className="flex-1 resize-none rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm text-[var(--color-foreground)] placeholder:text-[var(--color-muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--color-ring)] transition-colors"
          />
          <Button
            type="submit"
            size="icon"
            className="self-end h-10 w-10 shrink-0"
            disabled={!query.trim() || isPending}
            aria-label="Enviar pregunta"
          >
            {isPending ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>

      </form>

      {/* Answer area */}
      {isPending && (
        <div className="space-y-3 rounded-xl border border-[var(--color-border)] p-5">
          <div className="h-4 w-3/4 animate-pulse rounded bg-[var(--color-muted)]" />
          <div className="h-4 w-full animate-pulse rounded bg-[var(--color-muted)]" />
          <div className="h-4 w-5/6 animate-pulse rounded bg-[var(--color-muted)]" />
        </div>
      )}

      {!isPending && data && (
        <AnswerDisplay response={data as QueryResponseV1} />
      )}

      {!isPending && error && (
        <div className="rounded-xl border border-[var(--color-destructive)]/30 bg-red-50 dark:bg-red-950/20 p-4 text-sm text-red-700 dark:text-red-400">
          {(error as { status?: number }).status === 500
            ? "El modelo LLM no está disponible. Verifica que LLAMACPP_MODEL_PATH esté configurado y el servidor esté activo."
            : "Error al procesar la consulta. Intenta nuevamente."}
        </div>
      )}

      {!isPending && !data && !error && (
        <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--color-border)] py-16 text-[var(--color-muted-foreground)]">
          <Send className="h-8 w-8 opacity-30" />
          <p className="text-sm">Escribe una pregunta para comenzar</p>
        </div>
      )}
    </div>
  )
}
