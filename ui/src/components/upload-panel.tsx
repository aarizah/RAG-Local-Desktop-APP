import { useCallback, useRef, useState } from "react"
import { Upload, FileText, CheckCircle2, AlertCircle, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useUpload } from "@/hooks/use-upload"
import type { ApiHttpError, IngestResponseV1, ApiErrorV1 } from "@/types/api"
import { cn } from "@/lib/utils"

function isDuplicateError(err: unknown): boolean {
  const e = err as ApiHttpError
  if (e?.status === 409) return true
  return false
}

function getErrorMessage(err: unknown): string {
  const e = err as ApiHttpError
  if (!e) return "Error desconocido"
  if (typeof e.detail === "string") return e.detail
  const detail = e.detail as ApiErrorV1
  if (detail?.message) return detail.message
  return `Error ${e.status}`
}

export function UploadPanel() {
  const [dragging, setDragging] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const { mutate, isPending, isSuccess, isError, error, data, reset } = useUpload()

  const handleFile = useCallback(
    (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        alert("Solo se aceptan archivos PDF")
        return
      }
      setSelectedFile(file)
      reset()
    },
    [reset]
  )

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragging(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile]
  )

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const handleUpload = () => {
    if (!selectedFile) return
    mutate(selectedFile)
  }

  const handleNewFile = () => {
    setSelectedFile(null)
    reset()
    if (inputRef.current) inputRef.current.value = ""
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-[var(--color-muted-foreground)] uppercase tracking-wide">
        Subir documento
      </h2>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !selectedFile && inputRef.current?.click()}
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-sm transition-colors",
          dragging
            ? "border-[var(--color-primary)] bg-[var(--color-accent)]"
            : "border-[var(--color-border)] hover:border-[var(--color-primary)] hover:bg-[var(--color-accent)]",
          !selectedFile && "cursor-pointer"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={onInputChange}
        />

        {selectedFile ? (
          <div className="flex flex-col items-center gap-1 text-center">
            <FileText className="h-8 w-8 text-[var(--color-muted-foreground)]" />
            <span className="font-medium text-[var(--color-foreground)] break-all">
              {selectedFile.name}
            </span>
            <span className="text-xs text-[var(--color-muted-foreground)]">
              {(selectedFile.size / 1024).toFixed(1)} KB
            </span>
          </div>
        ) : (
          <>
            <Upload className="h-8 w-8 text-[var(--color-muted-foreground)]" />
            <span className="text-[var(--color-muted-foreground)]">
              Arrastra un PDF aquí o haz click
            </span>
          </>
        )}
      </div>

      {/* Feedback */}
      {isSuccess && (data as IngestResponseV1) && (
        <div className="flex items-start gap-2 rounded-md bg-green-50 dark:bg-green-950/30 p-3 text-sm text-green-700 dark:text-green-400">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">{selectedFile?.name} indexado</p>
            <p className="text-xs opacity-80">
              {(data as IngestResponseV1).chunks_indexed} fragmentos · ID{" "}
              {(data as IngestResponseV1).document_id.slice(0, 8)}…
            </p>
          </div>
        </div>
      )}

      {isError && isDuplicateError(error) && (
        <div className="flex items-start gap-2 rounded-md bg-yellow-50 dark:bg-yellow-950/30 p-3 text-sm text-yellow-700 dark:text-yellow-400">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>Este documento ya estaba indexado</p>
        </div>
      )}

      {isError && !isDuplicateError(error) && (
        <div className="flex items-start gap-2 rounded-md bg-red-50 dark:bg-red-950/30 p-3 text-sm text-red-700 dark:text-red-400">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>{getErrorMessage(error)}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        {selectedFile && !isSuccess && (
          <Button
            className="flex-1"
            onClick={handleUpload}
            disabled={isPending}
          >
            {isPending ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Procesando…
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Indexar
              </>
            )}
          </Button>
        )}
        {(selectedFile || isSuccess || isError) && (
          <Button variant="outline" onClick={handleNewFile} className={isSuccess || isError ? "flex-1" : ""}>
            {isSuccess ? "Subir otro" : "Cancelar"}
          </Button>
        )}
      </div>
    </div>
  )
}
