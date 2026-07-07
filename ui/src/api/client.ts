import type {
  ApiHttpError,
  DocumentListResponseV1,
  IngestResponseV1,
  QueryRequestV1,
  QueryResponseV1,
} from "@/types/api"

const BASE = "/v1"

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) return res.json() as Promise<T>

  let detail: unknown
  try {
    detail = await res.json()
  } catch {
    detail = await res.text()
  }

  const err: ApiHttpError = { status: res.status, detail: detail as ApiHttpError["detail"] }
  throw err
}

export async function uploadDocument(file: File): Promise<IngestResponseV1> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch(`${BASE}/upload`, { method: "POST", body: form })
  return handleResponse<IngestResponseV1>(res)
}

export async function queryRag(req: QueryRequestV1): Promise<QueryResponseV1> {
  const res = await fetch(`${BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  return handleResponse<QueryResponseV1>(res)
}

export async function listDocuments(): Promise<DocumentListResponseV1> {
  const res = await fetch(`${BASE}/documents`)
  return handleResponse<DocumentListResponseV1>(res)
}
