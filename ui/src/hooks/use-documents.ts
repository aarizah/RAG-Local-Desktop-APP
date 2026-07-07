import { useQuery } from "@tanstack/react-query"
import { listDocuments } from "@/api/client"

export const DOCUMENTS_QUERY_KEY = ["documents"] as const

export function useDocuments() {
  return useQuery({
    queryKey: DOCUMENTS_QUERY_KEY,
    queryFn: listDocuments,
    staleTime: 30_000,
    retry: false,
  })
}
