import { useMutation, useQueryClient } from "@tanstack/react-query"
import { uploadDocument } from "@/api/client"
import { DOCUMENTS_QUERY_KEY } from "./use-documents"

export function useUpload() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: DOCUMENTS_QUERY_KEY })
    },
  })
}
