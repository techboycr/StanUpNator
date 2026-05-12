# Definición del contenido del archivo markdown
markdown_content = """# Especificaciones del Proyecto: Generative StandUp AI

Este documento sirve como guía de contexto para GitHub Copilot para la generación del código del Proyecto Final del Módulo de Python para IA.

## 1. Visión General
La aplicación es un "Generative StandUp" que crea rutinas de comedia de 5 minutos personalizadas. Combina un Agente de entrevista, un sistema RAG para estilo de comedia y un flujo Multi-IA para la generación final.

## 2. Arquitectura del Sistema (Integración Ejercicio 4)
Para cumplir con el assignment, el sistema integra:
- **Agente (Opción C):** Un `InterviewAgent` con `ConversationBufferMemory` y herramientas de `DuckDuckGoSearch` para perfilar al usuario.
- **RAG (Opción B):** Uso de `ChromaDB` o `FAISS` para indexar transcripciones de comediantes favoritos y asegurar que el output siga una estructura de stand-up real (Set-up -> Punchline).
- **Multi-IA (Opción A):** Un pipeline que: (1) Analiza el perfil del usuario, (2) Genera la rutina, (3) Realiza un control de calidad del humor y (4) Traduce el resultado si es necesario.

## 3. Requerimientos Técnicos
- **Interfaz:** Streamlit (preferido por flexibilidad en dashboards).
- **Modelos:** Google Gemini API (`gemini-1.5-pro`) como motor principal.
- **Framework:** LangChain para la orquestación de agentes y RAG.
- **Deployment:** Preparado para HuggingFace Spaces (requiere `export` de variables de entorno).

## 4. Estructura de Archivos Modular
Instrucciones para generar los archivos:

### `app.py` (Entry Point)
- Layout con `st.sidebar` para configuración de API Keys.
- Tabs para: "Entrevista", "Base de Conocimiento", "Generación de Rutina".

### `agent_logic.py` (El Entrevistador)
- Implementar un Agente que use `LangChain`.
- Herramientas: Búsqueda web para analizar los links proporcionados por el usuario.
- Memoria: Guardar las preferencias de temas (política, fútbol, etc.).

### `rag_engine.py` (El Estilo)
- Función para procesar archivos `.txt` o `.pdf` con material de comediantes.
- Recuperación semántica de "estructuras de chistes" basadas en los temas elegidos por el usuario.

### `generator.py` (El Guionista)
- Prompt Engineering avanzado: "Actúa como un comediante profesional de stand-up...".
- Input: Contexto del agente + Documentos del RAG + Temas preferidos.
- Output: Guion de 5 minutos con anotaciones de [Pausa], [Risas], [Gesto].

## 5. Prompt de Generación Inicial para Copilot
"Genera una estructura base en Python usando Streamlit para una app llamada Generative StandUp. Necesito que el código sea modular. Crea primero el archivo `app.py` que importe funciones de `agent_logic.py` y `generator.py`. Asegúrate de incluir manejo de errores para la API Key de Gemini y un sistema de logs básico."

## 6. Variables de Entorno
- `GOOGLE_API_KEY`: Para acceso a Gemini.
- `USER_ROLE`: Technical Marketing Manager / Estudiante de IA (para contexto de prompts internos).

## 7. Criterios de Evaluación a cumplir
- **Funcionalidad:** El flujo debe ir de Entrevista -> Procesamiento -> Rutina.
- **UI/UX:** Usar `st.chat_message` para la parte de la entrevista.
- **Deployment:** Crear `requirements.txt` con `langchain`, `google-generativeai`, `streamlit`, `duckduckgo-search`.
"""

# Ejecutar la creación del archivo
with open('copilot-instructions-standup-ai.md', 'w', encoding='utf-8') as f:
    f.write(markdown_content)