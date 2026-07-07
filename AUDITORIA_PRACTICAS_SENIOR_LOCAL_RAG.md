# Auditoría de prácticas “senior” en Local RAG (guía de estudio)

Este documento toma **tu código actual** del backend (`core/`) y lo usa como material para contrastar hábitos típicos de desarrolladores junior con patrones que suelen buscar seniors: **arquitectura hexagonal (puertos/adaptadores)**, **idempotencia y deduplicación**, **contratos de API**, **observabilidad**, **seguridad básica**, **inyección de dependencias** y **tests con dobles**.

Rutas de referencia: `core/src/`, `core/main.py`, `core/tests/`.

---

## 1. Arquitectura hexagonal (puertos y adaptadores)

### Qué es (resumido)

- **Núcleo / dominio**: reglas de negocio y orquestación (p. ej. ingestión, recuperación) que **no** deberían depender de FastAPI, Chroma ni de archivos concretos de librerías.
- **Puerto**: interfaz que el núcleo necesita (`Protocol` en Python: “necesito algo que embeda textos” o “algo que persista vectores”).
- **Adaptador**: implementación concreta (SentenceTransformers, Chroma, Docling).

### Ejemplos concretos en tu repo

**Puerto de chunking** — el servicio de ingestión depende de la abstracción, no de Docling:

```23:25:core/src/chunking.py
class ChunkingPort(Protocol):
    def chunk(self, *, document_id: str, version: int, source_path: str) -> list[Chunk]: ...
```

**Puerto del vector store**:

```22:25:core/src/vector_store.py
class VectorStorePort(Protocol):
    def upsert(self, records: list[VectorRecord]) -> None: ...

    def search(self, query_embedding: list[float], limit: int) -> list[RetrievedChunkV1]: ...
```

**Adaptador Chroma** implementa ese contrato sin que `IngestionService` importe detalles de Chroma en cada línea (solo recibe `VectorStorePort`).

**Composición en el borde** (`main.py`): un solo lugar arma adaptadores reales y los inyecta. La API recibe servicios ya construidos:

```40:48:core/src/api.py
def create_app(
    *,
    ingestion_service: IngestionService,
    retrieval_service: RetrievalService,
    reranker: Reranker,
    generation_service: object,
) -> FastAPI:
```

### Qué suele hacer un junior

- Importar `chromadb`, `llama_cpp` o `DocumentConverter` **dentro** de los handlers de FastAPI o de funciones “de negocio”.
- Mezclar lectura de `request`, SQL y llamadas al modelo en un mismo bloque de 200 líneas.
- Imposibilitar tests rápidos porque “siempre hace falta” GPU, disco o red.

### Qué ganas con el enfoque del repo

- Puedes sustituir Chroma por otro store o el chunker por un fake **sin reescribir** `IngestionService` (solo cambias el cableado en `build_app` o en tests).

---

## 2. Idempotencia, deduplicación y “reintentos seguros”

### Aclaración importante

**Idempotencia** significa: “la misma operación aplicada dos veces deja el sistema en el mismo estado que una vez” (a veces con la misma respuesta).

En ingestión de documentos, un patrón habitual es:

- **Clave natural del contenido**: hash del archivo (aquí SHA-256).
- **Rechazo explícito de duplicados** antes de escribir en vector DB + SQLite → evita duplicar índice y filas.

### Ejemplo concreto en tu repo

1. Calculás el hash del archivo y consultás si ya existe en `documents`.
2. Si existe → `DuplicateDocumentError` (no re-indexás).

```159:168:core/src/ingestion.py
        content_hashes = [content_hash for _, _, content_hash in resolved_files]
        placeholders = ", ".join("?" for _ in content_hashes)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT content_hash FROM documents WHERE content_hash IN ({placeholders})",
                tuple(content_hashes),
            ).fetchall()
        duplicated_in_db = [str(row["content_hash"]) for row in rows]
        if duplicated_in_db:
            raise DuplicateDocumentError(duplicate_hashes=duplicated_in_db)
```

3. La API traduce eso a **HTTP 409 Conflict** con un **código de error estable** para el cliente:

```67:69:core/src/api.py
        except DuplicateDocumentError as exc:
            error = ApiErrorV1(code=ErrorCode.DUPLICATE_DOCUMENT, message=str(exc))
            raise HTTPException(status_code=409, detail=error.model_dump()) from exc
```

4. Los tests documentan comportamiento “tipo transacción lógica” en batch: si el lote incluye un duplicado, **no** debería dejar el documento nuevo a medias; el test verifica que después podés ingestar el archivo nuevo solo:

```171:187:core/tests/test_integration_ingestion.py
def test_ingest_batch_with_new_and_duplicate_is_atomic_and_returns_409(tmp_path: Path) -> None:
    ...
    batch_resp = client.post(
        "/v1/ingest",
        json={"source_paths": ["new.pdf", "existing.pdf"]},
    )
    assert batch_resp.status_code == 409

    retry_new = client.post("/v1/ingest", json={"source_path": "new.pdf"})
    assert retry_new.status_code == 200
```

### Qué suele hacer un junior

- Re-indexar siempre y acumular chunks duplicados en el vector store.
- Devolver 500 genérico para “ya existía”.
- No distinguir **mismo contenido, distinto nombre de archivo** vs **mismo archivo subido dos veces**.

### Límite honesto (tema senior)

- **Idempotencia fuerte end-to-end** suele requerir transacciones distribuidas o compensación: acá escribís lexical + vector + SQLite en pasos separados; un fallo a mitad de `_ingest_one` puede dejar estado parcial. Un senior lo tiene en el radar y, según criticidad, introduce patrones como saga, cola con reintentos, o “transactional outbox”.

---

## 3. Contratos de API versionados y validación en el borde

### Ejemplo concreto

- Rutas bajo `/v1/...`.
- Modelos Pydantic compartidos (`contracts.py`) = **contrato** estable entre backend y UI.
- Validaciones declarativas (p. ej. cadena de `candidate_k` → `rerank_k` → `final_k`):

```53:59:core/src/contracts.py
    @model_validator(mode="after")
    def validate_k_chain(self) -> "QueryRequestV1":
        if self.final_k > self.rerank_k:
            raise ValueError("final_k must be <= rerank_k")
        if self.rerank_k > self.candidate_k:
            raise ValueError("rerank_k must be <= candidate_k")
        return self
```

- `IngestRequestV1` con `extra="forbid"` evita que el cliente mande campos basura sin que falle explícitamente (422).

### Qué suele hacer un junior

- Validar con `if` sueltos en el handler, duplicando reglas.
- Aceptar JSON arbitrario y depurar errores opacos.
- Cambiar respuestas sin versión (`/query`) y romper el frontend en silencio.

---

## 4. Inyección de dependencias y composición raíz

### Ejemplo concreto

`build_app()` en `main.py` lee configuración, construye adaptadores y pasa instancias a `create_app`. Los servicios reciben dependencias por constructor (`IngestionService`, `RetrievalService`).

### Qué suele hacer un junior

- Singletons globales (`get_db()` que lee env en cada llamada).
- Instanciar el modelo LLM dentro del endpoint la primera vez que alguien pega.

### Beneficio

- Testabilidad y claridad de **ciclo de vida** (¿cuándo se carga el modelo? una vez al arranque).

---

## 5. Observabilidad: trazas, métricas y privacidad en logs

### Ejemplo concreto

- **Correlation ID** por query para enlazar logs y errores:

```114:115:core/src/api.py
        correlation_id = str(uuid.uuid4())
        with timed_stage(TOTAL_MS) as total:
```

- **Histogramas Prometheus** por etapa (retrieval, rerank, generation, total).
- **Context manager** `timed_stage` que mide y observa en `finally` (siempre registra, incluso si hay excepción en el bloque):

```43:51:core/src/observability.py
@contextmanager
def timed_stage(histogram: Histogram) -> Iterator[dict[str, float]]:
    start = time.perf_counter()
    payload = {"ms": 0.0}
    try:
        yield payload
    finally:
        payload["ms"] = (time.perf_counter() - start) * 1000
        histogram.observe(payload["ms"])
```

- **Redacción ligera de PII** en logs de la query (`redact_pii`).

### Qué suele hacer un junior

- `print()` o logs sin estructura.
- Sin ID de correlación: imposible seguir una request en producción.
- Loguear datos sensibles completos.

---

## 6. Seguridad básica: path traversal y superficie de entrada

### Ejemplo concreto

`_resolve_source_path` exige rutas relativas al bucket `s3`, resuelve con `Path.resolve()` y comprueba que el archivo quede **bajo** el directorio permitido:

```85:96:core/src/ingestion.py
    def _resolve_source_path(self, source_path: str) -> Path:
        candidate = Path(source_path)
        if candidate.is_absolute():
            raise ValueError("source_path must be relative to s3")

        full_path = (self.s3_dir / candidate).resolve()
        if full_path != self.s3_dir and self.s3_dir not in full_path.parents:
            raise ValueError("source_path points outside s3")
```

Test explícito: `../evil.pdf` → error / 400 según capa.

### Qué suele hacer un junior

- `open(base_dir + user_input)` sin normalizar.
- Confiar en el nombre de archivo del upload sin sanitizar.

### Nota sobre `/v1/upload`

El handler escribe el archivo a disco y luego llama a `ingest`. Si `ingest` falla después del `write_bytes`, puede quedar un archivo huérfano en `s3_dir`. Un senior plantea: limpieza, transacción, o ingest idempotente con job asíncrono.

---

## 7. Errores de dominio vs errores HTTP

### Ejemplo concreto

- `DuplicateDocumentError` lleva metadata (`duplicate_hashes`).
- `GenerationError` (adaptador de generación) asocia `ErrorCode` y `correlation_id` para mapear a respuesta API.

Patrón: **excepción de dominio/adaptador** → **traducción en la capa HTTP** a status y cuerpo estable.

### Qué suele hacer un junior

- Capturar `Exception` y devolver 500 con `"Error"`.
- Perder el `from exc` en `raise`, ocultando la causa raíz en logs y depuración.

Tu código usa `from exc` al levantar `HTTPException`, lo cual preserva cadena de excepciones.

---

## 8. Testing: dobles, fakes y contratos

### Ejemplo concreto

En `test_integration_ingestion.py`:

- `FakeEmbedding`, `FakePdfChunker`, `InMemoryVectorStore` cumplen los mismos métodos que los adaptadores reales (duck typing respecto a los `Protocol`).
- `create_app` se invoca con `DummyRetrieval`, `DummyReranker`, `DummyGeneration` para aislar ingestión.

Eso es **hexagonal en acción**: el test no necesita Docling ni Chroma para validar reglas de ingestión y HTTP.

### Qué suele hacer un junior

- Solo tests manuales o E2E frágiles que requieren modelos de 4 GB.
- Mockear librerías a bajo nivel con `patch` en cadena, difícil de mantener.

---

## 9. Configuración tipada y fail-fast

### Ejemplo concreto

`Settings` con `pydantic-settings`: variables de entorno con alias, validación de la cadena RAG k, detección opcional de modelo GGUF por defecto, `get_settings()` con `lru_cache` (una sola lectura “caliente”).

`build_app()` valida que exista un `.gguf` antes de exponer la app.

### Qué suele hacer un junior

- `os.getenv("PORT", 8000)` como string y fallos en runtime horas después.
- Sin validación cruzada entre parámetros relacionados.

---

## 10. Otros detalles “de madurez” que aparecen en el repo

| Tema | Dónde se nota |
|------|----------------|
| **Contrato de generación flexible** | `create_app` verifica `hasattr(generation_service, "generate")` para fallar temprano si cableás mal el adaptador. |
| **Enum de códigos de error** | `ErrorCode` en `contracts.py` para respuestas predecibles. |
| **Dataclasses con `slots`** | `VectorRecord` en `vector_store.py` — pequeña optimización y objetos más “cerrados”. |
| **Dependencias opcionales** | `try/import` de `chromadb` o docling con error claro si falta el paquete. |
| **UTC explícito en contratos** | `utc_now()` en `contracts.py` para timestamps coherentes. |

---

## 11. Tabla rápida Junior vs enfoque de este proyecto

| Tema | Típico junior | En tu código (referencia) |
|------|----------------|---------------------------|
| Capas | Todo en el handler FastAPI | Servicios + `create_app` delgado |
| Persistencia | Llamadas directas esparcidas | Puertos (`VectorStorePort`, `ChunkingPort`, etc.) |
| Duplicados | Reindexar o ignorar | Hash + `DuplicateDocumentError` + 409 |
| API | Respuestas ad hoc | `contracts.py` + `/v1` |
| Config | Env suelto | `Settings` + validadores |
| Logs | Prints | structlog + métricas + correlation id |
| Tests | Solo manual | Fakes + `TestClient` + escenarios de seguría/dedup |

---

## 12. Ideas de estudio (siguiente nivel)

1. **Transacciones y consistencia**: dibujar qué pasa si falla `vector_store.upsert` después de `lexical_store.upsert_chunk` en `_ingest_one`.
2. **Idempotency-Key HTTP**: comparar tu deduplicación por hash con el patrón de cabecera `Idempotency-Key` en APIs REST de pagos.
3. **Hexagonal estricto**: mover `SqliteFtsRepository` detrás de un `LexicalStorePort` si querés el mismo nivel de desacople que con vectores.
4. **SAGA / outbox**: leer un artículo corto sobre mensajería y consistencia eventual cuando hay varios stores.

---

*Documento generado como material de estudio a partir del estado del repositorio Local RAG. Actualizalo cuando cambies ingestión, contratos o la estrategia de deduplicación.*
