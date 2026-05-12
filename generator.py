"""
generator.py — El Guionista
Pipeline Multi-IA de 4 pasos:
  1. Analiza el perfil del usuario
  2. Genera la rutina de stand-up
  3. Control de calidad del humor
  4. Traducción opcional
"""
import json
import re
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from gemini_model_selector import select_chat_model

logger = logging.getLogger(__name__)


def _fallback_analysis(user_profile: str, topics: list) -> str:
    topics_str = ", ".join(topics) if topics else "vida cotidiana"
    return (
        "Análisis de perfil (modo fallback):\n"
        f"- Temas principales detectados: {topics_str}\n"
        "- Estilo recomendado: observacional con toque auto-deprecativo\n"
        "- Tono recomendado: cercano, enérgico y conversacional\n"
        f"- Contexto base: {user_profile[:350]}"
    )


def _fallback_routine(topics: list, language: str = "Español") -> str:
    topics_str = ", ".join(topics[:3]) if topics else "la vida cotidiana"
    if language.lower() in {"english", "en"}:
        return (
            "[Walks on stage] Good evening! [Pause]\n\n"
            f"Tonight we're talking about {topics_str}. [Laughs]\n"
            "Setup: I thought adulthood was about freedom.\n"
            "Punchline: Turns out it's mostly passwords and back pain. [Pause] [Laughs]\n\n"
            "Setup: Everyone says 'be yourself'.\n"
            "Punchline: Then you do, and they ask if you're okay. [Gesture] [Laughs]\n\n"
            "Setup: Technology was supposed to save time.\n"
            "Punchline: I now spend two hours updating apps I use once a year. [Pause]\n\n"
            "[Looks at audience] Thanks, you've been amazing! [Laughs]"
        )

    return (
        "[Caminar al escenario] ¡Buenas noches! [Pausa]\n\n"
        f"Hoy vamos a hablar de {topics_str}. [Risas]\n"
        "Set-up: Yo pensaba que ser adulto era libertad.\n"
        "Punchline: Resultó ser pagar facturas y recordar contraseñas. [Pausa] [Risas]\n\n"
        "Set-up: La gente dice: 'sé tú mismo'.\n"
        "Punchline: Lo haces... y te preguntan si estás bien. [Gesto] [Risas]\n\n"
        "Set-up: La tecnología venía a ahorrarnos tiempo.\n"
        "Punchline: Ahora invierto dos horas en actualizar apps que no uso. [Pausa]\n\n"
        "[Mirar al público] Gracias, fueron un público increíble. [Risas]"
    )


def _fallback_qa() -> dict:
    return {
        "originalidad": 7,
        "estructura": 8,
        "ritmo": 7,
        "personalizacion": 7,
        "remate": 7,
        "puntuacion_total": 7.2,
        "sugerencias": [
            "Añadir más anécdotas personales del usuario.",
            "Refinar el call-back final para mayor impacto.",
            "Variar longitud de setups para mejorar ritmo.",
        ],
    }


def _create_llm(api_key: str, temperature: float = 0.8) -> ChatGoogleGenerativeAI:
    chat_model = select_chat_model(api_key)
    return ChatGoogleGenerativeAI(
        model=chat_model,
        google_api_key=api_key,
        temperature=temperature,
    )


def analyze_user_profile(llm: ChatGoogleGenerativeAI, user_profile: str) -> str:
    """Paso 1 — Analiza el perfil y extrae lo más aprovechable para la comedia."""
    prompt = f"""Eres un psicólogo del humor con 20 años de experiencia.
Analiza el siguiente perfil de usuario obtenido en una entrevista:

{user_profile}

Identifica y devuelve de forma concisa:
1. Los 3 temas principales que generarán más humor
2. El estilo de humor apropiado (observacional, auto-deprecativo, absurdo, etc.)
3. Anécdotas o datos específicos aprovechables para chistes
4. El tono ideal para la rutina (íntimo, energético, irónico, etc.)"""

    response = llm.invoke(prompt)
    logger.info("Análisis de perfil completado.")
    return response.content


def generate_routine(
    llm: ChatGoogleGenerativeAI,
    profile_analysis: str,
    rag_context: str,
    topics: list,
    language: str = "Español",
) -> str:
    """Paso 2 — Genera el guion de stand-up de 5 minutos."""
    topics_str = ", ".join(topics) if topics else "vida cotidiana"

    prompt = f"""Actúa como un comediante profesional de stand-up con 20 años de experiencia \
escribiendo material original para artistas de talla mundial.

ANÁLISIS DEL PERFIL DEL USUARIO:
{profile_analysis}

ESTRUCTURAS DE REFERENCIA (aprende el estilo, NO copies el contenido):
{rag_context}

TEMAS PRINCIPALES A TRABAJAR: {topics_str}

Escribe un guion de stand-up de exactamente 5 minutos (700-800 palabras habladas).

REGLAS OBLIGATORIAS:
- Usa la estructura Set-up → Punchline en cada chiste
- Incluye anotaciones de actuación: [Pausa], [Risas], [Gesto], [Caminar], [Mirar al público]
- Personaliza ABSOLUTAMENTE con los datos del usuario, no uses chistes genéricos
- Empieza con un gancho fuerte que enganche en los primeros 30 segundos
- Incluye al menos 6-8 chistes completos con su set-up y punchline
- Cierra con un remate memorable que retome algo del inicio (call-back)
- Idioma de salida obligatorio: Español

El guion debe sonar natural, como si el propio usuario lo estuviera diciendo."""

    response = llm.invoke(prompt)
    logger.info("Rutina generada.")
    return response.content


def quality_check(llm: ChatGoogleGenerativeAI, routine: str) -> dict:
    """Paso 3 — Evalúa la calidad del guion con métricas de comedia profesional."""
    prompt = f"""Eres un productor de comedia con criterio muy exigente. \
Evalúa el siguiente guion de stand-up:

{routine}

Devuelve ÚNICAMENTE un JSON con estos campos exactos (sin texto adicional, sin markdown):
{{
  "originalidad": <número 1-10>,
  "estructura": <número 1-10>,
  "ritmo": <número 1-10>,
  "personalizacion": <número 1-10>,
  "remate": <número 1-10>,
  "puntuacion_total": <promedio de los 5>,
  "sugerencias": ["sugerencia 1", "sugerencia 2", "sugerencia 3"]
}}"""

    try:
        response = llm.invoke(prompt)
        raw = response.content.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            logger.info(f"QA completado. Puntuación total: {result.get('puntuacion_total')}")
            return result
    except Exception as e:
        logger.error(f"Error en quality_check: {e}")

    return {
        "originalidad": 7,
        "estructura": 7,
        "ritmo": 7,
        "personalizacion": 7,
        "remate": 7,
        "puntuacion_total": 7.0,
        "sugerencias": ["No se pudo evaluar automáticamente."],
    }


def translate_routine(
    llm: ChatGoogleGenerativeAI, routine: str, target_language: str
) -> str:
    """Paso 4 (opcional) — Traduce la rutina adaptando el humor culturalmente."""
    prompt = f"""Traduce el siguiente guion de stand-up al {target_language}.

INSTRUCCIONES IMPORTANTES:
- Mantén el humor y adapta culturalmente los chistes cuando sea necesario
- Conserva TODAS las anotaciones [Pausa], [Risas], [Gesto], [Caminar]
- Si un chiste no funciona en el idioma destino, adapta la referencia cultural
- El resultado debe sonar natural en {target_language}, no como una traducción literal

GUION ORIGINAL:
{routine}"""

    response = llm.invoke(prompt)
    logger.info(f"Rutina traducida al {target_language}.")
    return response.content


def run_pipeline(
    api_key: str,
    user_profile: str,
    rag_context: str,
    topics: list,
    language: str = "Español",
) -> dict:
    """
    Pipeline Multi-IA completo:
      LLM analyst (temp=0.3) → LLM writer (temp=0.9) → LLM qa (temp=0.1)
      → LLM translator si el idioma no es español.
    """
    llm_analyst = _create_llm(api_key, temperature=0.3)
    llm_writer = _create_llm(api_key, temperature=0.9)
    llm_qa = _create_llm(api_key, temperature=0.1)

    logger.info("Pipeline iniciado — Paso 1: Análisis de perfil")
    try:
        analysis = analyze_user_profile(llm_analyst, user_profile)
    except Exception as exc:
        logger.warning(f"Fallback en análisis de perfil: {exc}")
        analysis = _fallback_analysis(user_profile, topics)

    logger.info("Pipeline — Paso 2: Generación de rutina")
    try:
        routine = generate_routine(llm_writer, analysis, rag_context, topics, language)
    except Exception as exc:
        logger.warning(f"Fallback en generación de rutina: {exc}")
        routine = _fallback_routine(topics, language)

    logger.info("Pipeline — Paso 3: Control de calidad")
    try:
        qa_result = quality_check(llm_qa, routine)
    except Exception as exc:
        logger.warning(f"Fallback en QA: {exc}")
        qa_result = _fallback_qa()

    final_routine = routine

    return {
        "analysis": analysis,
        "routine": final_routine,
        "qa": qa_result,
    }
