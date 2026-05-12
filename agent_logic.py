"""
agent_logic.py — El Entrevistador
Agente LangChain que conduce la entrevista, extrae preferencias del usuario
y construye su perfil para el generador de rutinas.
"""
import json
import re
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools import DuckDuckGoSearchRun
from gemini_model_selector import select_chat_model

logger = logging.getLogger(__name__)


# ── Memoria simple (no requiere LangChain memory) ────────────────────────────

class _Message:
    """Mensaje individual del historial de conversación."""
    __slots__ = ("type", "content")

    def __init__(self, type_: str, content: str) -> None:
        self.type = type_       # "human" | "ai"
        self.content = content


class _ChatHistory:
    """Historial de mensajes con API compatible con el resto del código."""

    def __init__(self) -> None:
        self.messages: list = []

    def add_user_message(self, text: str) -> None:
        self.messages.append(_Message("human", text))

    def add_ai_message(self, text: str) -> None:
        self.messages.append(_Message("ai", text))


class SimpleMemory:
    """Memoria de conversación ligera, sin dependencias externas."""

    def __init__(self) -> None:
        self.chat_memory = _ChatHistory()


INTERVIEW_QUESTIONS = [
    "1) Para arrancar: ¿cómo te llamas, de dónde eres y cómo te describirías en 3 palabras?",
    "2) ¿A qué te dedicas y qué parte de tu trabajo/estudio te parece más absurda?",
    "3) ¿Cuáles son tus temas favoritos para bromear? (familia, pareja, trabajo, viajes, tecnología, etc.)",
    "4) ¿Qué lugares frecuentas mucho (barrio, ciudad, transporte, oficina, universidad, gym, etc.) y qué cosas raras ves ahí?",
    "5) Cuéntame una anécdota divertida reciente que te haya pasado a ti.",
    "6) Cuéntame una anécdota vergonzosa tuya que hoy te dé risa.",
    "7) ¿Qué historias graciosas recuerdas de tus amigos? (sin datos sensibles)",
    "8) ¿Qué historias graciosas o raras recuerdas de tu familia?",
    "9) ¿Qué te da más rabia del día a día pero te parece cómico cuando lo cuentas?",
    "10) ¿Qué muletillas, expresiones o forma de hablar usas normalmente?",
    "11) ¿Qué comediantes te gustan y por qué?",
    "12) ¿Qué tipo de humor prefieres evitar (negro, político, religioso, etc.)?",
    "13) ¿Hay algún tema personal que NO quieres que aparezca en la rutina?",
    "14) ¿Cómo quieres sonar en el escenario? (irónico, tierno, sarcástico, energético...)",
    "15) Dame una última historia corta que quieras convertir en remate fuerte para el cierre.",
]


def create_interview_agent(api_key: str):
    """Inicializa el LLM, la memoria y las herramientas del agente."""
    chat_model = select_chat_model(api_key)
    llm = ChatGoogleGenerativeAI(
        model=chat_model,
        google_api_key=api_key,
        temperature=0.7,
    )
    memory = SimpleMemory()
    tools = [DuckDuckGoSearchRun()]
    logger.info("InterviewAgent inicializado correctamente.")
    return llm, memory, tools


def process_user_response(llm, memory, user_input: str, question: str) -> dict:
    """
    Guarda el intercambio en memoria y extrae datos del perfil del usuario
    en formato estructurado usando el LLM.
    """
    memory.chat_memory.add_user_message(user_input)

    extraction_prompt = f"""Analiza la siguiente respuesta de un usuario en una entrevista de comedia:

Pregunta: "{question}"
Respuesta: "{user_input}"

Extrae la información en JSON con exactamente estos campos:
- "temas": lista de strings con los temas de comedia detectados (máx 5)
- "info_personal": string con datos relevantes mencionados
- "estilo_humor": string con el estilo de humor inferido

Devuelve ÚNICAMENTE el JSON, sin texto adicional, sin bloques de código markdown."""

    try:
        response = llm.invoke(extraction_prompt)
        # Limpiar posibles bloques de código del LLM
        raw = response.content.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        logger.error(f"Error extrayendo perfil: {e}")

    return {"temas": [], "info_personal": user_input, "estilo_humor": "general"}


def build_user_profile(memory) -> str:
    """Construye un resumen textual del perfil a partir del historial de conversación."""
    messages = memory.chat_memory.messages
    if not messages:
        return "Sin información de perfil disponible."
    return "\n".join(
        f"{'Usuario' if m.type == 'human' else 'Sistema'}: {m.content}"
        for m in messages
    )
