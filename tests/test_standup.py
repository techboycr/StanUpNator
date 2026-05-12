"""
tests/test_standup.py
Tests unitarios para los módulos de Generative StandUp AI.
Usa mocks para evitar llamadas reales a la API de Gemini.
"""
import json
import sys
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# Asegurar que el directorio raíz esté en el path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de mock
# ─────────────────────────────────────────────────────────────────────────────
def _make_llm_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    return msg


# ─────────────────────────────────────────────────────────────────────────────
# agent_logic.py
# ─────────────────────────────────────────────────────────────────────────────
class TestAgentLogic:
    def test_interview_questions_not_empty(self):
        from agent_logic import INTERVIEW_QUESTIONS
        assert len(INTERVIEW_QUESTIONS) >= 5, "Debe haber al menos 5 preguntas"

    def test_interview_questions_are_strings(self):
        from agent_logic import INTERVIEW_QUESTIONS
        for q in INTERVIEW_QUESTIONS:
            assert isinstance(q, str) and len(q) > 0

    def test_process_user_response_valid_json(self):
        """Cuando el LLM devuelve JSON válido, la función lo parsea correctamente."""
        from agent_logic import process_user_response

        expected = {"temas": ["trabajo", "tecnología"], "info_personal": "dev", "estilo_humor": "sarcástico"}
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_llm_response(json.dumps(expected))

        mock_memory = MagicMock()
        mock_memory.chat_memory = MagicMock()
        mock_memory.chat_memory.add_user_message = MagicMock()

        result = process_user_response(mock_llm, mock_memory, "Soy dev", "¿A qué te dedicas?")
        assert result["temas"] == ["trabajo", "tecnología"]
        assert result["estilo_humor"] == "sarcástico"

    def test_process_user_response_fallback_on_bad_json(self):
        """Si el LLM devuelve texto no JSON, debe retornar estructura por defecto."""
        from agent_logic import process_user_response

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_llm_response("esto no es json")

        mock_memory = MagicMock()
        mock_memory.chat_memory = MagicMock()
        mock_memory.chat_memory.add_user_message = MagicMock()

        result = process_user_response(mock_llm, mock_memory, "respuesta cualquiera", "pregunta")
        assert "temas" in result
        assert "info_personal" in result
        assert "estilo_humor" in result

    def test_build_user_profile_empty_memory(self):
        """Con memoria vacía debe devolver el mensaje por defecto."""
        from agent_logic import build_user_profile

        mock_memory = MagicMock()
        mock_memory.chat_memory.messages = []
        result = build_user_profile(mock_memory)
        assert "Sin información" in result

    def test_build_user_profile_with_messages(self):
        """Con mensajes en memoria debe construir el perfil como string."""
        from agent_logic import build_user_profile

        msg1 = MagicMock()
        msg1.type = "human"
        msg1.content = "Me llamo Ana"
        msg2 = MagicMock()
        msg2.type = "ai"
        msg2.content = "Encantado, Ana"

        mock_memory = MagicMock()
        mock_memory.chat_memory.messages = [msg1, msg2]

        result = build_user_profile(mock_memory)
        assert "Ana" in result
        assert isinstance(result, str)


# ─────────────────────────────────────────────────────────────────────────────
# rag_engine.py
# ─────────────────────────────────────────────────────────────────────────────
class TestRagEngine:
    def test_base_samples_not_empty(self):
        """Las muestras base del RAG deben existir y tener contenido."""
        import rag_engine
        assert len(rag_engine._BASE_SAMPLES) >= 5

    def test_base_samples_contain_keywords(self):
        """Las muestras deben contener Set-up y Punchline."""
        import rag_engine
        combined = " ".join(rag_engine._BASE_SAMPLES).lower()
        assert "set-up" in combined
        assert "punchline" in combined

    @patch("rag_engine.FAISS")
    @patch("rag_engine.GoogleGenerativeAIEmbeddings")
    def test_initialize_vectorstore_returns_store(self, mock_embeddings, mock_faiss):
        """initialize_vectorstore debe crear y retornar un vectorstore."""
        import rag_engine
        rag_engine._vectorstore = None  # Reset global

        mock_store = MagicMock()
        mock_faiss.from_documents.return_value = mock_store

        result = rag_engine.initialize_vectorstore("fake-api-key")
        assert result is mock_store
        assert rag_engine._vectorstore is mock_store

    @patch("rag_engine.FAISS")
    @patch("rag_engine.GoogleGenerativeAIEmbeddings")
    def test_retrieve_comedy_structures_calls_similarity_search(self, mock_emb, mock_faiss):
        """retrieve_comedy_structures debe llamar a similarity_search."""
        import rag_engine
        rag_engine._vectorstore = None

        mock_doc = MagicMock()
        mock_doc.page_content = "Set-up: algo\nPunchline: algo"
        mock_store = MagicMock()
        mock_store.similarity_search.return_value = [mock_doc]
        mock_faiss.from_documents.return_value = mock_store

        result = rag_engine.retrieve_comedy_structures(["trabajo"], "fake-key", k=1)
        mock_store.similarity_search.assert_called_once()
        assert "Set-up" in result

    def test_get_vectorstore_returns_none_initially(self):
        """Antes de inicializar, get_vectorstore debe devolver None."""
        import rag_engine
        rag_engine._vectorstore = None
        assert rag_engine.get_vectorstore() is None


# ─────────────────────────────────────────────────────────────────────────────
# generator.py
# ─────────────────────────────────────────────────────────────────────────────
class TestGenerator:
    def test_analyze_user_profile_returns_string(self):
        from generator import analyze_user_profile

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_llm_response("Análisis: humor sarcástico, temas laborales")
        result = analyze_user_profile(mock_llm, "Me llamo Juan, trabajo en tech")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_routine_returns_string(self):
        from generator import generate_routine

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_llm_response(
            "Set-up: algo\nPunchline: algo\n[Pausa] [Risas]"
        )
        result = generate_routine(mock_llm, "perfil", "contexto rag", ["trabajo"])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_quality_check_valid_json(self):
        from generator import quality_check

        qa_data = {
            "originalidad": 8,
            "estructura": 9,
            "ritmo": 7,
            "personalizacion": 8,
            "remate": 9,
            "puntuacion_total": 8.2,
            "sugerencias": ["Mejorar el gancho inicial"],
        }
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_llm_response(json.dumps(qa_data))
        result = quality_check(mock_llm, "guion de prueba")
        assert result["originalidad"] == 8
        assert result["puntuacion_total"] == 8.2
        assert len(result["sugerencias"]) == 1

    def test_quality_check_fallback_on_bad_json(self):
        from generator import quality_check

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_llm_response("no es json")
        result = quality_check(mock_llm, "guion cualquiera")
        # Debe devolver estructura por defecto
        assert "puntuacion_total" in result
        assert "sugerencias" in result

    def test_translate_routine_invokes_llm(self):
        from generator import translate_routine

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = _make_llm_response("This is the translated routine.")
        result = translate_routine(mock_llm, "Guion en español", "English")
        mock_llm.invoke.assert_called_once()
        assert "translated" in result

    @patch("generator._create_llm")
    def test_run_pipeline_full_flow_español(self, mock_create):
        """El pipeline completo en español NO debe llamar a translate_routine."""
        from generator import run_pipeline

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            _make_llm_response("Análisis del perfil"),           # analyze
            _make_llm_response("Rutina generada [Pausa]"),       # generate
            _make_llm_response('{"originalidad":8,"estructura":8,"ritmo":8,"personalizacion":8,"remate":8,"puntuacion_total":8.0,"sugerencias":[]}'),  # qa
        ]
        mock_create.return_value = mock_llm

        result = run_pipeline("fake-key", "perfil test", "rag ctx", ["trabajo"], "Español")

        assert "analysis" in result
        assert "routine" in result
        assert "qa" in result
        assert result["routine"] == "Rutina generada [Pausa]"
        # En español no debe llamar translate (solo 3 invocaciones)
        assert mock_llm.invoke.call_count == 3

    @patch("generator._create_llm")
    def test_run_pipeline_keeps_spanish_output_even_if_language_differs(self, mock_create):
        """El pipeline actual siempre prioriza salida en español y no traduce."""
        from generator import run_pipeline

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            _make_llm_response("Profile analysis"),
            _make_llm_response("Generated routine"),
            _make_llm_response('{"originalidad":7,"estructura":7,"ritmo":7,"personalizacion":7,"remate":7,"puntuacion_total":7.0,"sugerencias":[]}'),
        ]
        mock_create.return_value = mock_llm

        result = run_pipeline("fake-key", "profile", "rag", ["work"], "English")
        assert result["routine"] == "Generated routine"
        assert mock_llm.invoke.call_count == 3
