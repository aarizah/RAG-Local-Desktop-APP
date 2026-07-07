import { useState, useEffect } from "react"
import { Moon, Sun, Database } from "lucide-react"
import { Button } from "@/components/ui/button"
import { UploadPanel } from "@/components/upload-panel"
import { DocumentLibrary } from "@/components/document-library"
import { QueryPanel } from "@/components/query-panel"
import { useDocuments } from "@/hooks/use-documents"

function useDarkMode() {
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem("theme")
    if (stored) return stored === "dark"
    return window.matchMedia("(prefers-color-scheme: dark)").matches
  })

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
    localStorage.setItem("theme", dark ? "dark" : "light")
  }, [dark])

  return [dark, setDark] as const
}

function BackendStatus() {
  const { isError, isSuccess } = useDocuments()
  const connected = isSuccess
  return (
    <div className="flex items-center gap-1.5 text-xs text-[var(--color-muted-foreground)]">
      <span
        className={`h-2 w-2 rounded-full ${connected ? "bg-green-500" : isError ? "bg-red-500" : "bg-yellow-400"}`}
        aria-label={connected ? "Backend conectado" : isError ? "Backend desconectado" : "Conectando…"}
      />
      <span>{connected ? "Backend" : isError ? "Sin backend" : "…"}</span>
    </div>
  )
}

export default function App() {
  const [dark, setDark] = useDarkMode()

  return (
    <div className="flex h-screen flex-col bg-[var(--color-background)]">
      {/* Header */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-[var(--color-border)] px-6">
        <div className="flex items-center gap-2.5">
          <Database className="h-5 w-5 text-[var(--color-primary)]" />
          <span className="font-semibold text-[var(--color-foreground)]">Local RAG</span>
        </div>
        <div className="flex items-center gap-3">
          <BackendStatus />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setDark((d) => !d)}
            aria-label={dark ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
          >
            {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </Button>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="flex w-80 shrink-0 flex-col gap-6 overflow-y-auto border-r border-[var(--color-border)] p-5">
          <UploadPanel />
          <div className="h-px bg-[var(--color-border)]" />
          <DocumentLibrary />
        </aside>

        {/* Main */}
        <main className="flex flex-1 flex-col overflow-y-auto p-6">
          <QueryPanel />
        </main>
      </div>
    </div>
  )
}
