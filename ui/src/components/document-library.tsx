import { RefreshCw, FileText, Inbox } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useDocuments } from "@/hooks/use-documents"

export function DocumentLibrary() {
  const { data, isLoading, isError, refetch, isFetching } = useDocuments()

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-[var(--color-muted-foreground)] uppercase tracking-wide">
          Documentos indexados
        </h2>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => refetch()}
          disabled={isFetching}
          className="h-7 w-7"
          aria-label="Refrescar lista"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-12 animate-pulse rounded-md bg-[var(--color-muted)]"
            />
          ))}
        </div>
      )}

      {isError && (
        <p className="text-xs text-[var(--color-destructive)]">
          No se pudo cargar la lista
        </p>
      )}

      {!isLoading && !isError && data?.documents.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-6 text-[var(--color-muted-foreground)]">
          <Inbox className="h-8 w-8" />
          <p className="text-sm">Ningún documento indexado todavía</p>
        </div>
      )}

      {!isLoading && !isError && (data?.documents.length ?? 0) > 0 && (
        <ul className="flex flex-col gap-1.5">
          {data!.documents.map((doc) => (
            <li
              key={`${doc.document_id}-${doc.version}`}
              className="flex items-center gap-2.5 rounded-md px-3 py-2 hover:bg-[var(--color-accent)] transition-colors"
            >
              <FileText className="h-4 w-4 shrink-0 text-[var(--color-muted-foreground)]" />
              <div className="min-w-0 flex-1">
                <p
                  className="truncate text-sm font-medium text-[var(--color-foreground)]"
                  title={doc.source_file}
                >
                  {doc.source_file}
                </p>
                <p className="text-xs text-[var(--color-muted-foreground)]">
                  ID {doc.document_id.slice(0, 8)}… · {doc.status}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
