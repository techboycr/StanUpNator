"""
rag_engine.py — El Estilo
Motor RAG basado en FAISS + Gemini Embeddings para recuperar estructuras
de chistes de stand-up relevantes al perfil del usuario.
"""
import os
import logging
import tempfile
from typing import List, Optional

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_community.embeddings import FakeEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from gemini_model_selector import select_embedding_model

logger = logging.getLogger(__name__)

# Material base con estructuras de Set-up → Punchline de distintos estilos
_BASE_SAMPLES = [
    """ESTILO: Observacional cotidiano
Set-up: "¿Han notado que cuando alguien dice 'con todo respeto'..."
Punchline: "...lo que viene después no tiene NADA de respeto?"
[Pausa breve] [Risas] [Gesto de incredulidad]

Set-up: "Las instrucciones del shampoo dicen: aplique, enjuague, repita..."
Punchline: "...¿repita? ¿Cuántas veces? ¿Hasta que se acabe el shampoo? ¿Hasta la muerte?"
[Pausa] [Risas]""",

    """ESTILO: Auto-deprecativo
Set-up: "Fui al gimnasio por primera vez en tres años..."
Punchline: "...me cobró la membresía de los tres años que no fui. 'Técnicamente seguías siendo miembro.'"
[Pausa] [Risas] [Gesto de resignación]

Set-up: "Mis amigos dicen que debería salir más..."
Punchline: "...y yo abro una segunda ventana en el navegador. Ya salí."
[Pausa larga] [Risas]""",

    """ESTILO: Absurdo
Set-up: "Leí que los pulpos tienen tres corazones..."
Punchline: "...y los tres les rompen al mismo tiempo cuando alguien les dice 'hablemos'."
[Pausa] [Risas]

Set-up: "La gente dice que el tiempo lo cura todo..."
Punchline: "...esa gente claramente nunca esperó en urgencias un domingo."
[Pausa] [Risas] [Caminar]""",

    """ESTILO: Laboral / Trabajo
Set-up: "Mi jefe me dijo que tenía 'gran potencial'..."
Punchline: "...ocho años después entendí que 'potencial' significa que todavía no te van a pagar más."
[Pausa] [Risas]

Set-up: "En la reunión dijeron que necesitábamos más 'sinergia'..."
Punchline: "...nadie sabe qué significa eso, pero todos asintieron muy seguros."
[Pausa breve] [Risas] [Gesto de asentir exageradamente]""",

    """ESTILO: Familiar / Relaciones
Set-up: "Mi familia me llama solo cuando necesita ayuda con la tecnología..."
Punchline: "...soy básicamente el soporte técnico no remunerado de toda la genealogía."
[Pausa] [Risas]

Set-up: "Mis padres dicen que cuando ellos eran jóvenes todo era mejor..."
Punchline: "...sí, incluyendo su capacidad para idealizar el pasado."
[Pausa] [Risas] [Caminar]""",
]

_vectorstore: Optional[FAISS] = None
_using_fake_embeddings: bool = False


def _get_embeddings(api_key: str) -> GoogleGenerativeAIEmbeddings:
    # Some API keys/projects do not expose embed models in v1beta.
    # Fallback keeps the app functional without breaking the flow.
    try:
        embedding_model = select_embedding_model(api_key)
        return GoogleGenerativeAIEmbeddings(
            model=embedding_model,
            google_api_key=api_key,
        )
    except Exception as exc:
        logger.warning(f"Embeddings Gemini no disponibles, usando fallback local: {exc}")
        return FakeEmbeddings(size=768)


def initialize_vectorstore(api_key: str) -> FAISS:
    """Crea el vectorstore FAISS con el material base."""
    global _vectorstore, _using_fake_embeddings
    embeddings = _get_embeddings(api_key)
    docs = [
        Document(page_content=sample, metadata={"source": f"base_sample_{i}", "style": "base"})
        for i, sample in enumerate(_BASE_SAMPLES)
    ]
    try:
        _vectorstore = FAISS.from_documents(docs, embeddings)
        _using_fake_embeddings = isinstance(embeddings, FakeEmbeddings)
    except Exception as exc:
        logger.warning(f"Fallo embeddings remotos, activando fallback local: {exc}")
        embeddings = FakeEmbeddings(size=768)
        _vectorstore = FAISS.from_documents(docs, embeddings)
        _using_fake_embeddings = True
    logger.info(f"Vectorstore inicializado con {len(docs)} muestras base.")
    return _vectorstore


def add_comedian_material(file_path: str, api_key: str) -> int:
    """
    Procesa un archivo .txt o .pdf y lo agrega al vectorstore.
    Devuelve el número de fragmentos indexados.
    """
    global _vectorstore, _using_fake_embeddings
    if _vectorstore is None:
        initialize_vectorstore(api_key)

    if file_path.lower().endswith(".pdf"):
        loader = PyPDFLoader(file_path)
    else:
        loader = TextLoader(file_path, encoding="utf-8")

    raw_docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(raw_docs)

    embeddings = FakeEmbeddings(size=768) if _using_fake_embeddings else _get_embeddings(api_key)
    try:
        new_store = FAISS.from_documents(chunks, embeddings)
    except Exception as exc:
        logger.warning(f"Fallo indexado con embeddings remotos, usando fallback local: {exc}")
        embeddings = FakeEmbeddings(size=768)
        new_store = FAISS.from_documents(chunks, embeddings)
        _using_fake_embeddings = True
    _vectorstore.merge_from(new_store)

    logger.info(f"Material '{file_path}' agregado: {len(chunks)} fragmentos indexados.")
    return len(chunks)


def add_transcript_records(records: List[dict], api_key: str) -> int:
    """
    Agrega transcripciones (provenientes de links de video) al vectorstore.
    Cada registro debe incluir: title, url, transcript.
    Devuelve el número de chunks indexados.
    """
    global _vectorstore, _using_fake_embeddings

    if _vectorstore is None:
        initialize_vectorstore(api_key)

    docs = [
        Document(
            page_content=record.get("transcript", ""),
            metadata={
                "source": record.get("url", "video_url"),
                "title": record.get("title", "video"),
                "style": "transcript",
            },
        )
        for record in records
        if record.get("transcript", "").strip()
    ]

    splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=80)
    chunks = splitter.split_documents(docs)

    embeddings = FakeEmbeddings(size=768) if _using_fake_embeddings else _get_embeddings(api_key)
    try:
        new_store = FAISS.from_documents(chunks, embeddings)
    except Exception as exc:
        logger.warning(f"Fallo indexado de transcripciones con embeddings remotos, usando fallback local: {exc}")
        embeddings = FakeEmbeddings(size=768)
        new_store = FAISS.from_documents(chunks, embeddings)
        _using_fake_embeddings = True

    _vectorstore.merge_from(new_store)
    logger.info(f"Transcripciones agregadas: {len(chunks)} chunks indexados.")
    return len(chunks)


def retrieve_comedy_structures(topics: List[str], api_key: str, k: int = 3) -> str:
    """
    Recupera semánticamente estructuras de chistes relacionadas con los temas del usuario.
    """
    global _vectorstore, _using_fake_embeddings
    if _vectorstore is None:
        initialize_vectorstore(api_key)

    query = f"chiste set-up punchline sobre: {', '.join(topics)}"
    try:
        docs = _vectorstore.similarity_search(query, k=k)
    except Exception as exc:
        logger.warning(f"Fallo en búsqueda semántica remota, reintentando con fallback local: {exc}")
        # Rebuild with local embeddings to keep the app usable.
        _using_fake_embeddings = True
        initialize_vectorstore(api_key)
        docs = _vectorstore.similarity_search(query, k=k)
    return "\n\n---\n\n".join(d.page_content for d in docs)


def get_vectorstore() -> Optional[FAISS]:
    return _vectorstore
