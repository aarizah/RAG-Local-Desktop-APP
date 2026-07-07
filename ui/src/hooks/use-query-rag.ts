import { useMutation } from "@tanstack/react-query"
import { queryRag } from "@/api/client"

export function useQueryRag() {
  return useMutation({
    mutationFn: queryRag,
  })
}
