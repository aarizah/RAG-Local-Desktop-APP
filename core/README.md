# Core Service

Servicio FastAPI para Local RAG con arquitectura por puertos/adaptadores.

## Ingesta de PDFs (nuevo flujo)

- Endpoint: `POST /v1/ingest`
- La ingesta SOLO toma archivos PDF ubicados dentro de `core/s3` (por defecto; configurable con `S3_DIR`).
- `source_path` y `source_paths` deben ser rutas **relativas** a esa carpeta `s3`.
- No se admite `content` inline en la request.

### Ejemplo (1 PDF)

```json
{
  "document_id": "manual-laboral",
  "source_path": "manual-laboral.pdf"
}
```

### Ejemplo (batch)

```json
{
  "document_id": "normativa-2026",
  "source_paths": ["ley-1.pdf", "ley-2.pdf"]
}
```

### Seguridad básica

- Se rechazan rutas absolutas.
- Se rechaza path traversal (`../`).
- Se rechazan archivos fuera de la carpeta `s3`.
- Se rechazan extensiones distintas de `.pdf`.

### Chunking PDF

La ingesta parsea cada PDF con Docling (`DocumentConverter`) y chunking híbrido (`HybridChunker` + `AutoTokenizer`).
Cada chunk conserva metadatos útiles: `source_file`, `pages`, `first_page`, `headings` (si Docling los provee).
