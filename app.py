"""
app.py - Wizard de Generative StandUp AI
Flujo:
  Paso 1: Links de videos + transcripciones + embeddings
  Paso 2: Entrevista guiada estilo chat
  Paso 3: Revision de perfil en chat + generacion final
"""
import json
import logging
import os
import re
from typing import List, Tuple

import streamlit as st
from dotenv import load_dotenv
from fpdf import FPDF
from langchain_google_genai import ChatGoogleGenerativeAI

from agent_logic import (
    INTERVIEW_QUESTIONS,
    build_user_profile,
    create_interview_agent,
    process_user_response,
)
from gemini_model_selector import select_chat_model
from generator import run_pipeline
from rag_engine import add_transcript_records, initialize_vectorstore, retrieve_comedy_structures
from video_ingestion import (
    MAX_ALLOWED_MINUTES,
    MAX_IDEAL_MINUTES,
    extract_semantic_signals,
    validate_and_collect_videos,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Generative StandUp AI",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _get_api_key() -> str:
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        st.error("Ingresa tu Google API Key en la barra lateral para continuar.")
        st.stop()
    return key


def _render_sidebar() -> None:
    with st.sidebar:
        st.title("🎤 StandUp AI")
        st.caption("Wizard guiado para crear tu rutina de stand-up")
        st.divider()

        key_input = st.text_input(
            "Google Gemini API Key",
            value=os.getenv("GOOGLE_API_KEY", ""),
            type="password",
            help="Tu key de Google AI Studio",
        )
        if key_input and key_input.strip():
            os.environ["GOOGLE_API_KEY"] = key_input.strip()
            st.success("API Key configurada")
        else:
            st.warning("Falta API Key")

        st.divider()
        st.markdown("**Modelos prioritarios**")
        st.markdown("- Chat: `gemini-2.5-flash`")
        st.markdown("- Embeddings: `gemini-embedding-001`")
        st.caption("Si fallan, se activa fallback local automaticamente.")


def _init_state() -> None:
    defaults = {
        "wizard_step": 1,
        "links_input": "",
        "videos_ready": False,
        "video_records": [],
        "semantic_signals": [],
        "agent_ready": False,
        "answered_count": 0,
        "profile_data": [],
        "interview_done": False,
        "interview_messages": [],
        "last_asked_index": -1,
        "profile_report": "",
        "profile_review_messages": [],
        "profile_approved": False,
        "generate_now": False,
        "reset_confirm": False,
        "reset_counter": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if _show_test_controls() and not st.session_state.links_input:
        st.session_state.links_input = _read_test_links()


def _show_test_controls() -> bool:
    return os.getenv("STANDUP_SHOW_TEST_LINKS", "false").strip().lower() in {"1", "true", "yes", "on"}


def _reset_from_step_2() -> None:
    keys = [
        "agent_ready",
        "answered_count",
        "profile_data",
        "interview_done",
        "interview_messages",
        "last_asked_index",
        "profile_report",
        "profile_review_messages",
        "profile_approved",
        "last_result",
        "generate_now",
        "llm",
        "memory",
        "tools",
    ]
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]
    _init_state()


def _reset_wizard_process() -> None:
    next_counter = st.session_state.get("reset_counter", 0) + 1
    keys = [
        "wizard_step",
        "links_input",
        "videos_ready",
        "video_records",
        "semantic_signals",
        "agent_ready",
        "answered_count",
        "profile_data",
        "interview_done",
        "interview_messages",
        "last_asked_index",
        "profile_report",
        "profile_review_messages",
        "profile_approved",
        "generate_now",
        "reset_confirm",
        "last_result",
        "llm",
        "memory",
        "tools",
        "interview_chat_input",
        "profile_review_input",
    ]
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.reset_counter = next_counter
    _init_state()


def _step_badge(step: int, title: str) -> str:
    current = st.session_state.wizard_step
    marker = "✅" if current > step else ("🟢" if current == step else "⚪")
    return f"{marker} Paso {step}: {title}"


def _render_wizard_motion() -> None:
    current = st.session_state.wizard_step
    st.progress(current / 3, text=f"Wizard {current}/3")
    labels = [
        "1) Videos",
        "2) Entrevista",
        "3) Perfil y Generacion",
    ]
    cols = st.columns(3)
    for idx, label in enumerate(labels, start=1):
        if idx < current:
            cols[idx - 1].success(label)
        elif idx == current:
            cols[idx - 1].info(label)
        else:
            cols[idx - 1].caption(label)

    with cols[2]:
        if not st.session_state.reset_confirm:
            if st.button("Reiniciar proceso", use_container_width=True, key="reset_open_btn"):
                st.session_state.reset_confirm = True
                st.rerun()
        else:
            st.warning("Esto borrara el progreso actual. Confirmas reiniciar?")
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                if st.button("Si, reiniciar", use_container_width=True, key="reset_confirm_btn"):
                    _reset_wizard_process()
                    st.rerun()
            with cancel_col:
                if st.button("Cancelar", use_container_width=True, key="reset_cancel_btn"):
                    st.session_state.reset_confirm = False
                    st.rerun()


def _build_pdf_bytes(title: str, body: str) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, title)
    pdf.ln(2)
    pdf.set_font("Helvetica", size=11)

    safe_body = (
        body.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u2013", "-")
        .replace("\u2026", "...")
        .replace("\u2014", "--")
        .replace("\u00ab", '"')
        .replace("\u00bb", '"')
        .replace("\u00b4", "'")
        .replace("`", "'")
        .encode("latin-1", errors="ignore")
        .decode("latin-1")
    )
    pdf.multi_cell(0, 6, safe_body)

    raw_pdf = pdf.output(dest="S")
    if isinstance(raw_pdf, (bytes, bytearray)):
        return bytes(raw_pdf)
    return str(raw_pdf).encode("latin-1", errors="ignore")


def _read_test_links() -> str:
    test_file = "test_links.txt"
    if os.path.exists(test_file):
        with open(test_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def _create_chat_llm(api_key: str, temperature: float = 0.2) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=select_chat_model(api_key),
        google_api_key=api_key,
        temperature=temperature,
    )


def _build_profile_report(api_key: str, profile_text: str, topics: List[str]) -> str:
    topics_line = ", ".join(topics) if topics else "vida cotidiana"
    prompt = f"""Eres un editor de perfiles para comedia stand-up.

Con base en esta entrevista, crea un reporte en espanol claro y accionable.

TRANSCRIPCION DE ENTREVISTA:
{profile_text}

TEMAS DETECTADOS:
{topics_line}

Devuelve un reporte markdown con estas secciones exactas:
1) Resumen personal
2) Temas fuertes para comedia
3) Estilo y tono recomendado
4) Limites y temas a evitar
5) Remate potencial de cierre

Reglas:
- Maximo 180 palabras
- No inventes datos sensibles
- Mantener tono profesional y util para guion
"""
    try:
        llm = _create_chat_llm(api_key, temperature=0.3)
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as exc:
        logger.warning(f"No se pudo construir reporte con LLM, usando fallback: {exc}")
        return (
            "### 1) Resumen personal\n"
            f"Perfil base detectado de entrevista.\n\n"
            "### 2) Temas fuertes para comedia\n"
            f"- {topics_line}\n\n"
            "### 3) Estilo y tono recomendado\n"
            "- Observacional, cercano y con energia.\n\n"
            "### 4) Limites y temas a evitar\n"
            "- Evitar temas sensibles declarados por el usuario.\n\n"
            "### 5) Remate potencial de cierre\n"
            "- Cerrar con callback de su anecdota final."
        )


def _apply_profile_change(api_key: str, current_report: str, user_message: str) -> Tuple[str, str]:
    prompt = f"""Eres un editor conversacional de perfiles de comedia.

REPORTE ACTUAL:
{current_report}

MENSAJE DEL USUARIO:
{user_message}

Tarea:
- Si el usuario pide cambios, aplica los cambios al reporte.
- Si el mensaje es solo una duda, responde brevemente y manten el reporte.

Devuelve SOLO JSON valido con esta estructura exacta:
{{
  "updated_report": "...",
  "assistant_reply": "..."
}}

assistant_reply debe cerrar con: "Estas de acuerdo con los cambios?"
"""
    try:
        llm = _create_chat_llm(api_key, temperature=0.2)
        response = llm.invoke(prompt)
        raw = response.content.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            updated = parsed.get("updated_report", "").strip() or current_report
            reply = parsed.get("assistant_reply", "").strip() or "Actualice el perfil. Estas de acuerdo con los cambios?"
            return updated, reply
    except Exception as exc:
        logger.warning(f"Fallo aplicando cambios de perfil con LLM: {exc}")

    fallback_report = f"{current_report}\n\nNota del usuario: {user_message}" if user_message else current_report
    fallback_reply = "He aplicado tu comentario al reporte. Estas de acuerdo con los cambios?"
    return fallback_report, fallback_reply


def _is_affirmative(text: str) -> bool:
    normalized = text.strip().lower()
    yes_tokens = {
        "si",
        "sí",
        "ok",
        "dale",
        "de acuerdo",
        "me parece",
        "correcto",
        "listo",
        "adelante",
        "genera",
        "generar",
    }
    return any(token in normalized for token in yes_tokens)


def _collect_topics() -> List[str]:
    topics: List[str] = []
    for item in st.session_state.profile_data:
        topics.extend(item.get("temas", []))
    return list(dict.fromkeys(topics)) or ["vida cotidiana"]


def _execute_generation(api_key: str) -> None:
    all_topics = _collect_topics()
    user_profile_text = st.session_state.profile_report or build_user_profile(st.session_state.memory)
    semantic_topics = st.session_state.semantic_signals[:8]
    retrieval_topics = list(dict.fromkeys(all_topics + semantic_topics))

    progress = st.progress(0, text="Iniciando generacion...")
    status = st.empty()

    status.info("1) Recuperando estilo de referencias (RAG)")
    progress.progress(20, text="Recuperando contexto RAG...")
    rag_context = retrieve_comedy_structures(retrieval_topics, api_key, k=5)

    status.info("2) Ejecutando pipeline de analisis y escritura")
    progress.progress(55, text="Analizando perfil y escribiendo rutina...")
    result = run_pipeline(
        api_key=api_key,
        user_profile=user_profile_text,
        rag_context=rag_context,
        topics=retrieval_topics,
        language="Español",
    )

    status.info("3) Agente verificador de comedia (QA)")
    progress.progress(85, text="Corriendo verificador de comedia...")

    st.session_state.last_result = result
    st.session_state.generate_now = False
    progress.progress(100, text="Material listo")
    status.success("Proceso completado.")


def _render_step_1(api_key: str) -> None:
    st.subheader(_step_badge(1, "Referencias de Comedia (Videos)"))
    st.caption(
        f"Carga links de videos de hasta {MAX_IDEAL_MINUTES} min idealmente "
        f"(tolerancia hasta {MAX_ALLOWED_MINUTES} min)."
    )

    links_widget_key = f"links_textarea_{st.session_state.reset_counter}"
    col_a, col_b = st.columns([3, 1])
    with col_a:
        links_text = st.text_area(
            "Pega aqui tus links (uno por linea)",
            value=st.session_state.links_input,
            height=180,
            key=links_widget_key,
        )
    with col_b:
        if _show_test_controls():
            if st.button("Usar test_links.txt", use_container_width=True):
                st.session_state.links_input = _read_test_links()
                st.rerun()

    st.session_state.links_input = links_text

    if st.button("Next: procesar videos", type="primary", use_container_width=True):
        urls = [line.strip() for line in links_text.splitlines() if line.strip()]
        if not urls:
            st.error("No hay links para procesar.")
            return

        with st.spinner("Validando duracion y descargando transcripciones..."):
            accepted, rejected, warnings = validate_and_collect_videos(urls)

        if warnings:
            for item in warnings:
                st.warning(item)

        if rejected:
            st.error("Se rechazaron algunos videos:")
            for item in rejected:
                st.markdown(f"- {item.url}: {item.reason}")

        if not accepted:
            st.error("❌ No se pudieron descargar automáticamente los transcripts.")
            
            with st.expander("📋 **Alternativa: Pegar transcripts manualmente**", expanded=True):
                st.info(
                    "Si YouTube está bloqueando desde este entorno, puedes pegar los transcripts "
                    "manualmente. Formato: `[VIDEO_ID o URL]\\n[TRANSCRIPT]\\n---\\n`"
                )
                
                manual_transcripts = st.text_area(
                    "Pega los transcripts (uno por sección separada por ---)",
                    height=300,
                    placeholder="Ejemplo:\n8pLi57wn0m0\nBuenas noches pues...\n---\n\n8AiulsAi_bM\nHoy les quiero contar...\n---",
                    key=f"manual_transcripts_{st.session_state.reset_counter}"
                )
                
                if st.button("Usar transcripts pegados manualmente", use_container_width=True):
                    if manual_transcripts.strip():
                        # Parsear transcripts manualmente
                        manual_accepted = []
                        sections = manual_transcripts.split("---")
                        
                        for section in sections:
                            lines = [l.strip() for l in section.strip().split("\n") if l.strip()]
                            if len(lines) < 2:
                                continue
                            
                            video_id_or_url = lines[0]
                            transcript_text = "\n".join(lines[1:])
                            
                            # Extraer video_id si es URL
                            from video_ingestion import extract_youtube_id
                            video_id = extract_youtube_id(video_id_or_url)
                            if not video_id:
                                video_id = video_id_or_url  # Asumir que es ID directo
                            
                            if transcript_text:
                                manual_accepted.append({
                                    "url": f"https://www.youtube.com/watch?v={video_id}",
                                    "title": f"Video {video_id}",
                                    "duration_seconds": -1,
                                    "transcript": transcript_text,
                                })
                        
                        if not manual_accepted:
                            st.error("No se encontraron transcripts válidos en el texto pegado.")
                            return
                        
                        # Indexar transcripts manualmente
                        with st.spinner("Indexando transcripciones manuales en RAG..."):
                            initialize_vectorstore(api_key)
                            chunks = add_transcript_records(manual_accepted, api_key)
                        
                        semantic_signals = extract_semantic_signals(
                            [r["transcript"] for r in manual_accepted], top_k=20
                        )
                        
                        st.session_state.videos_ready = True
                        st.session_state.video_records = manual_accepted
                        st.session_state.semantic_signals = semantic_signals
                        _reset_from_step_2()
                        
                        st.success(f"✅ Base lista (manual). Videos: {len(manual_accepted)} | Chunks: {chunks}")
                        st.session_state.wizard_step = 2
                        st.rerun()
                    else:
                        st.error("Por favor pega al menos un transcript.")
            
            return

        with st.spinner("Indexando transcripciones en RAG con embeddings..."):
            initialize_vectorstore(api_key)
            records = [
                {
                    "url": item.url,
                    "title": item.title,
                    "duration_seconds": item.duration_seconds,
                    "transcript": item.transcript,
                }
                for item in accepted
            ]
            chunks = add_transcript_records(records, api_key)

        semantic_signals = extract_semantic_signals([r["transcript"] for r in records], top_k=20)

        st.session_state.videos_ready = True
        st.session_state.video_records = records
        st.session_state.semantic_signals = semantic_signals
        _reset_from_step_2()

        st.success(f"Base lista. Videos aceptados: {len(records)} | Chunks indexados: {chunks}")
        st.session_state.wizard_step = 2
        st.rerun()


def _render_step_2(api_key: str) -> None:
    st.subheader(_step_badge(2, "Entrevista Guiada de Material"))
    st.info(
        "Esta entrevista sirve para capturar tu voz comica: temas, anecdotas, limites y tono. "
        "Con eso personalizamos la rutina final."
    )

    if not st.session_state.videos_ready:
        st.info("Completa primero el Paso 1 para continuar.")
        return

    if not st.session_state.agent_ready:
        llm, memory, tools = create_interview_agent(api_key)
        st.session_state.llm = llm
        st.session_state.memory = memory
        st.session_state.tools = tools
        st.session_state.agent_ready = True

    total_q = len(INTERVIEW_QUESTIONS)
    answered = st.session_state.answered_count
    st.progress(min(answered / total_q, 1.0), text=f"Progreso entrevista: {answered}/{total_q}")

    if not st.session_state.interview_messages:
        st.session_state.interview_messages.append(
            {
                "role": "assistant",
                "content": "Vamos a hacer una entrevista corta de 15 preguntas. Responde de forma natural y concreta.",
            }
        )

    if answered < total_q and st.session_state.last_asked_index != answered:
        question = INTERVIEW_QUESTIONS[answered]
        st.session_state.interview_messages.append({"role": "assistant", "content": question})
        st.session_state.last_asked_index = answered

    for msg in st.session_state.interview_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if answered < total_q:
        user_answer = st.chat_input("Tu respuesta...", key="interview_chat_input")
        if user_answer:
            question = INTERVIEW_QUESTIONS[answered]
            st.session_state.interview_messages.append({"role": "user", "content": user_answer})

            profile_info = process_user_response(
                st.session_state.llm,
                st.session_state.memory,
                user_answer,
                question,
            )
            st.session_state.profile_data.append(profile_info)
            st.session_state.answered_count += 1
            if st.session_state.answered_count >= total_q:
                st.session_state.interview_done = True
            st.rerun()

    if st.session_state.interview_done:
        st.success("Entrevista completa. Presiona Next para construir el reporte de perfil.")
        nav_col_1, nav_col_2 = st.columns([1, 1])
        with nav_col_1:
            if st.button("Volver al Paso 1", use_container_width=True):
                st.session_state.wizard_step = 1
                st.rerun()
        with nav_col_2:
            if st.button("Next: construir perfil", type="primary", use_container_width=True):
                profile_text = build_user_profile(st.session_state.memory)
                topics = _collect_topics()
                with st.spinner("Construyendo reporte de perfil..."):
                    st.session_state.profile_report = _build_profile_report(api_key, profile_text, topics)

                st.session_state.profile_review_messages = [
                    {
                        "role": "assistant",
                        "content": "Revise tu perfil inicial. Si quieres ajustes, pidemelos aqui. Si todo esta bien, responde: si.",
                    }
                ]
                st.session_state.profile_approved = False
                if "last_result" in st.session_state:
                    del st.session_state.last_result
                st.session_state.wizard_step = 3
                st.rerun()


def _render_step_3(api_key: str) -> None:
    st.subheader(_step_badge(3, "Perfil, Ajustes y Generacion"))

    if not st.session_state.videos_ready or not st.session_state.interview_done:
        st.info("Completa Paso 1 y Paso 2 para generar material.")
        return

    if not st.session_state.profile_report:
        profile_text = build_user_profile(st.session_state.memory)
        st.session_state.profile_report = _build_profile_report(api_key, profile_text, _collect_topics())

    left_col, right_col = st.columns([1.2, 1.0])

    with left_col:
        st.markdown("### Chat de revision del perfil")
        if not st.session_state.profile_review_messages:
            st.session_state.profile_review_messages = [
                {
                    "role": "assistant",
                    "content": "Te comparti un perfil inicial. Quieres ajustar algo antes de generar?",
                }
            ]

        for msg in st.session_state.profile_review_messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        review_input = st.chat_input(
            "Pide cambios o responde 'si' para generar material.",
            key="profile_review_input",
        )
        if review_input:
            st.session_state.profile_review_messages.append({"role": "user", "content": review_input})
            if _is_affirmative(review_input):
                st.session_state.profile_approved = True
                st.session_state.generate_now = True
                st.session_state.profile_review_messages.append(
                    {
                        "role": "assistant",
                        "content": "Perfecto. Aprobaste el perfil, voy a generar tu material ahora.",
                    }
                )
            else:
                with st.spinner("Analizando y aplicando cambios al perfil..."):
                    updated_report, reply = _apply_profile_change(
                        api_key,
                        st.session_state.profile_report,
                        review_input,
                    )
                st.session_state.profile_report = updated_report
                st.session_state.profile_approved = False
                st.session_state.profile_review_messages.append({"role": "assistant", "content": reply})
            st.rerun()

    with right_col:
        st.markdown("### Reporte del perfil")
        st.markdown(st.session_state.profile_report)

        st.divider()
        if st.session_state.profile_approved:
            st.success("Perfil aprobado. Puedes generar material.")
        else:
            st.warning("Aun falta confirmar el perfil en el chat.")

        if st.button("Generar material", type="primary", use_container_width=True):
            if not st.session_state.profile_approved:
                st.info("Primero confirma en el chat con un 'si' para aprobar el perfil.")
            else:
                st.session_state.generate_now = True
                st.rerun()

        if st.button("Volver al Paso 2", use_container_width=True):
            st.session_state.wizard_step = 2
            st.rerun()

    if st.session_state.generate_now:
        _execute_generation(api_key)

    if "last_result" in st.session_state:
        result = st.session_state.last_result
        st.success("Tu material esta listo.")

        qa = result.get("qa", {})
        st.subheader("Control de calidad (Agente Verificador)")
        cols = st.columns(5)
        cols[0].metric("Originalidad", f"{qa.get('originalidad', '-')}/10")
        cols[1].metric("Estructura", f"{qa.get('estructura', '-')}/10")
        cols[2].metric("Ritmo", f"{qa.get('ritmo', '-')}/10")
        cols[3].metric("Personalizacion", f"{qa.get('personalizacion', '-')}/10")
        cols[4].metric("Remate", f"{qa.get('remate', '-')}/10")

        if qa.get("sugerencias"):
            with st.expander("Sugerencias del verificador"):
                for suggestion in qa["sugerencias"]:
                    st.markdown(f"- {suggestion}")

        st.subheader("Rutina final (siempre en espanol)")
        st.markdown(result.get("routine", ""))

        txt_data = result.get("routine", "")
        pdf_data = None
        try:
            pdf_data = _build_pdf_bytes("Rutina StandUp AI", txt_data)
        except Exception as exc:
            st.error(f"Error generando PDF: {exc}")

        col_txt, col_pdf = st.columns(2)
        with col_txt:
            st.download_button(
                "Descargar TXT",
                data=txt_data,
                file_name="rutina_standup.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col_pdf:
            if pdf_data:
                st.download_button(
                    "Descargar PDF",
                    data=pdf_data,
                    file_name="rutina_standup.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.info("PDF no disponible en este momento")


def main() -> None:
    _render_sidebar()
    api_key = _get_api_key()
    _init_state()

    st.title("Generative StandUp AI - Wizard")
    st.caption("Flujo guiado: videos -> entrevista -> perfil validado en chat -> rutina final.")
    _render_wizard_motion()
    st.markdown("---")

    step = st.session_state.wizard_step
    if step == 1:
        _render_step_1(api_key)
    elif step == 2:
        _render_step_2(api_key)
    else:
        _render_step_3(api_key)


if __name__ == "__main__":
    main()
