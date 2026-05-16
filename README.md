# 🎤 Generative StandUp AI

**Aplicación de IA para crear rutinas de stand-up personalizadas en español usando un flujo guiado (wizard), RAG con referencias de comedia y un pipeline multi-agente con Gemini.**

---

## 📱 Links Importantes (Para Blackboard)

- **🔗 Repositorio GitHub:** [https://github.com/techboycr/StanUpNator](https://github.com/techboycr/StanUpNator) *(público)*
- **🌐 App Desplegada:** [Streamlit Cloud - StandUp AI](https://standup-ai-demo.streamlit.app/) *(acceso público)*

---

## 🎯 ¿Qué hace el sistema? (capacidades reales)

- **Wizard de 3 pasos en Streamlit:**
  - **Paso 1:** Ingesta de links de YouTube, validación y construcción de base RAG.
  - **Paso 2:** Entrevista guiada de 15 preguntas en interfaz de chat.
  - **Paso 3:** Revisión de perfil en chat, ajustes del reporte y generación final.

- **Extracción de transcripciones** usando API local de cluster (`/api/transcriptions` en `127.0.0.1:3001`).
- **Fallback opcional** a `youtube-transcript-api` solo si se habilita por variable de entorno.

- **Validación de duración de videos:**
  - Ideal: ≤ 30 min
  - Tolerancia: ≤ 45 min

- **RAG con FAISS:**
  - Indexa transcripciones y ejemplos base de estructuras Set-up → Punchline.
  - Recupera contexto relevante según temas del usuario.

- **Pipeline de generación multi-etapa:**
  - Análisis de perfil (psicólogo IA)
  - Escritura de rutina (comediante IA)
  - Control de calidad con métricas (productor IA)

- **Revisión conversacional del perfil:**
  - El usuario pide cambios por chat.
  - El sistema aplica cambios al reporte en tiempo real.
  - Al confirmar con "sí", se dispara la generación automática.

- **Exportación del resultado:**
  - Descarga en TXT
  - Descarga en PDF (con sanitización de caracteres)

- **Fallbacks para resiliencia:**
  - Selección dinámica de modelo Gemini disponible
  - Fallback de embeddings locales cuando el remoto no está disponible

---

## 💻 Tecnologías Utilizadas

| Categoría | Tecnología |
|-----------|-----------|
| **Frontend** | Streamlit 1.35.0+ |
| **LLM & Embeddings** | Google Gemini 2.5 Flash, Gemini Embeddings |
| **Orquestación** | LangChain 0.3.0+ |
| **Vector Search** | FAISS + Gemini Embeddings |
| **Procesamiento** | API local de transcripciones (cluster), yt-dlp |
| **PDF Generation** | fpdf2 2.7.9 |
| **Testing** | pytest 8.0.0, Playwright |
| **Python** | 3.11+ |

---

## 📸 Capturas de Pantalla de la App

### Paso 1: Ingesta de Videos
![Wizard Step 1 - Video Input](docs/screenshots/wizard-step1.png)
*El usuario ingresa links de YouTube que serán validados y procesados.*

### Wizard - Encabezado con Progreso
![Wizard Header - Progress Bar](docs/screenshots/wizard-header.png)
*Barra de progreso mostrando los 3 pasos del wizard.*

---

## 🏗️ Arquitectura Funcional

1. `video_ingestion.py`
- Procesa URLs de YouTube
- Crea jobs en API local de transcripciones y hace polling hasta estado terminal
- Intenta leer metadata (titulo/duracion)
- Aplica reglas de duracion

2. `rag_engine.py`
- Inicializa vector store FAISS
- Indexa material base + transcripciones
- Recupera contexto semantico para la generacion

3. `agent_logic.py`
- Gestiona entrevista guiada
- Extrae estructura de perfil desde respuestas
- Mantiene memoria de conversacion simple

4. `generator.py`
- Ejecuta pipeline de analisis -> rutina -> QA
- Devuelve rutina y puntuaciones

5. `app.py`
- UI Streamlit (wizard, chat, validaciones, descargas)
- Orquesta el flujo completo end-to-end

## 📋 Requisitos

- **Python 3.11+** (recomendado: 3.14.4)
- **API key de Google Gemini** (gratis en [Google AI Studio](https://aistudio.google.com))
- **Sistema operativo:** Windows, Linux o macOS
- **Git** para clonar el repositorio

---

## 🚀 Instalación Local

1. Clonar repositorio:

```bash
git clone https://github.com/techboycr/StanUpNator.git
cd StandUp-AI
```

2. Crear y activar entorno virtual:

```bash
python -m venv .venv
```

Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno en `.env`, puedes usar el archivo '.env_example':

```env
GOOGLE_API_KEY=tu_api_key_aqui
TRANSCRIPTION_API_BASE_URL=http://127.0.0.1:3001
TRANSCRIPTION_API_ACCESS_TOKEN=test
TRANSCRIPTION_API_MODEL_PROFILE=balanced-es
```

Opcional para mostrar controles de testing en UI:

```env
STANDUP_SHOW_TEST_LINKS=true
```

> En produccion, mantener `STANDUP_SHOW_TEST_LINKS` en `false` o no definirla.

## Como correr la aplicacion

```bash
streamlit run app.py
```

Luego abrir en navegador:

- http://localhost:8501

## Como usar (flujo recomendado)

1. Paso 1 - Videos
- Pega 1 o varios links de YouTube (uno por linea).
- Presiona `Next: procesar videos`.
- El sistema valida, extrae transcript e indexa en RAG.

2. Paso 2 - Entrevista
- Responde las 15 preguntas del chat con ejemplos concretos.
- Presiona `Next: construir perfil` al finalizar.

3. Paso 3 - Perfil y Generacion
- Revisa el reporte de perfil.
- Si deseas cambios, pidelos en el chat.
- Cuando este correcto, responde `si` en el chat.
- Genera material y descarga en TXT/PDF.

## Variables de entorno

- `GOOGLE_API_KEY` (obligatoria): acceso a Gemini.
- `TRANSCRIPTION_API_BASE_URL` (recomendada): URL base del API local de transcripciones.
- `TRANSCRIPTION_API_ACCESS_TOKEN` (recomendada): cookie `access_token` para auth local.
- `TRANSCRIPTION_API_MODEL_PROFILE` (opcional): perfil a solicitar al cluster (ej. `balanced-es`).
- `TRANSCRIPTION_API_POLL_TIMEOUT_SECONDS` (opcional): timeout del polling por job.
- `TRANSCRIPTION_API_POLL_INTERVAL_SECONDS` (opcional): intervalo de polling.
- `STANDUP_ENABLE_YT_TRANSCRIPT_FALLBACK` (opcional): `true/false` para fallback legacy.
- `STANDUP_SHOW_TEST_LINKS` (opcional): muestra controles de testing (`true`/`false`).

## Validación local del handoff API

Para ejecutar el checklist técnico de conectividad del cluster en local:

```bash
python specs/run_transcription_api_handoff_local.py
```

Este runner valida auth, creación/polling de jobs, nodos/policy, cola, rebalance y pruebas de errores comunes.

## Testing

Ejecutar pruebas unitarias:

```bash
python -m pytest tests/test_standup.py
```

## Calidad de codigo (type hints y docstrings)

El proyecto incluye:

- Type hints en funciones clave para mejorar mantenibilidad.
- Docstrings en modulos y funciones principales para explicar responsabilidades.
- Separacion modular por dominio (ingesta, RAG, agente, generador, UI).

## ☁️ Despliegue en Streamlit Community Cloud

### Requisitos Previos
- Repositorio público en GitHub (ya configurado en [https://github.com/techboycr/StanUpNator](https://github.com/techboycr/StanUpNator))
- Cuenta en [Streamlit Community Cloud](https://streamlit.io/cloud)
- Google Gemini API key

### Pasos de Despliegue

#### 1. Preparar el Repositorio GitHub
```bash
# Verificar que todo está comprometido
git status

# Hacer push a main si hay cambios pendientes
git add .
git commit -m "docs: update README for Blackboard submission"
git push origin main
```

#### 2. Conectar a Streamlit Cloud
1. Ir a [https://share.streamlit.io/](https://share.streamlit.io/)
2. Clickear **"New app"**
3. Seleccionar:
   - **Repository:** `techboycr/StanUpNator`
   - **Branch:** `main`
   - **Main file path:** `app.py`

#### 3. Configurar Secrets
En Streamlit Cloud, ir a **Settings → Secrets** y agregar:

```toml
GOOGLE_API_KEY = "tu_api_key_aqui"
```

#### 4. Deploy
Clickear **Deploy** y esperar a que se complete (usualmente 2-5 minutos).

Una vez listo, recibirás un link público como:
```
https://standup-ai-demo.streamlit.app/
```

### Validación Post-Deploy
- ✅ Acceder a la URL pública desde navegador
- ✅ Probar Paso 1 (ingestar un video de YouTube)
- ✅ Probar Paso 2 (responder entrevista)
- ✅ Probar Paso 3 (generar rutina y descargar)

---

## ⚠️ Notas Importantes para Blackboard

| Elemento | Estado | URL |
|----------|--------|-----|
| **Repositorio GitHub** | ✅ Público | [https://github.com/techboycr/StanUpNator](https://github.com/techboycr/StanUpNator) |
| **App Desplegada** | ✅ Accesible | [https://standup-ai-demo.streamlit.app/](https://standup-ai-demo.streamlit.app/) |
| **Código en Repositorio** | ✅ Completo | `app.py`, `requirements.txt`, `README.md` + módulos |
| **Screenshots** | ✅ Incluidas | `docs/screenshots/` |
| **Documentación** | ✅ Completa | Este README |

---

## 🔍 Partes Relevantes del Código

### 1. Generación Multi-Etapa (generator.py)
```python
async def run_pipeline(
    user_profile: dict,
    rag_retriever,
    selected_chat_model,
    selected_embedding_model
) -> dict:
    """
    Ejecuta el pipeline completo de análisis → rutina → QA.
    
    Retorna:
    {
        'analysis': str,
        'routine': str,
        'qa': {
            'originalidad': (score, suggestions),
            'estructura': (score, suggestions),
            ...
        }
    }
    """
    # 1. Análisis de perfil (temp=0.3)
    analysis = await analyze_user_profile(...)
    
    # 2. Generación de rutina (temp=0.9)
    routine = await generate_routine(...)
    
    # 3. Control de calidad (temp=0.1)
    qa_result = await quality_check(...)
    
    return {
        'analysis': analysis,
        'routine': routine,
        'qa': qa_result
    }
```

### 2. Interfaz de Usuario - Paso 3 (app.py)
```python
def _render_step_3():
    """Revisión de perfil con chat + generación automática."""
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Chat para editar el perfil
        st.subheader("💬 Revisa tu perfil")
        user_message = st.chat_input("Pedir cambios o confirmar con 'sí'...")
        
    with col2:
        # Mostrar reporte actual
        st.subheader("📋 Tu Perfil")
        st.text_area("Reporte", value=profile_text, height=400)
        
    # Cuando usuario confirma "sí", generar automáticamente
    if user_says_yes:
        st.success("✅ Generando tu rutina...")
        result = asyncio.run(run_pipeline(...))
        
        # Mostrar rutina con métricas QA
        st.markdown("## 🎭 Tu Rutina Generada")
        st.write(result['routine'])
        
        # Descargas
        st.download_button("📥 Descargar TXT", result['routine'])
        st.download_button("📄 Descargar PDF", pdf_bytes)
```

### 3. Ingesta RAG con FAISS (rag_engine.py)
```python
def initialize_vectorstore(embedding_model):
    """Inicializa FAISS con ejemplos base + transcripciones."""
    
    base_samples = [
        "Set-up: Observo que la gente siempre mira el teléfono... Punchline: ¡Hasta en el cine, durante mi presentación!",
        # ... 4 ejemplos más
    ]
    
    # Indexar en FAISS con Gemini embeddings
    vectorstore = FAISS.from_texts(
        texts=base_samples,
        embedding=embedding_model
    )
    
    return vectorstore

def add_transcript_records(vectorstore, transcripts):
    """Agregar transcripciones indexadas."""
    for transcript in transcripts:
        # Split chunks (700 chars, 80 overlap)
        chunks = split_text(transcript, chunk_size=700, overlap=80)
        vectorstore.add_texts(chunks)
```

### 4. Extracción de Transcripciones (video_ingestion.py)
```python
def validate_and_collect_videos(video_urls: list) -> tuple:
    """
    Valida videos y extrae transcripciones.
    
    - Rechaza videos > 45 min
    - Solicita transcript al API local del cluster
    - Usa fallback legacy opcional si se habilita por env
    """
    
    valid_videos = []
    for url in video_urls:
        try:
            video_id = extract_youtube_id(url)
            
            # Leer metadata (duración/título)
            metadata = _get_video_metadata(url)
            duration = metadata.get('duration', 0)
            
            if duration > 45 * 60:
                st.error(f"Video muy largo: {duration/60:.0f} min")
                continue
                
            # Obtener transcript via cluster local
            transcript = _fetch_transcript_from_cluster(url, duration_seconds=duration)
            
            valid_videos.append({
                'id': video_id,
                'transcript': transcript,
                'duration': duration
            })
            
        except Exception as e:
            st.warning(f"Error procesando {url}: {e}")
            
    return valid_videos
```

---

## ✅ Despliegue en Producción

**Antes de entregar a Blackboard, verificar:**

1. ✅ Repositorio es **público** (cualquiera puede verlo)
2. ✅ Link a app desplegada es **accesible** (sin autenticación)
3. ✅ `app.py`, `requirements.txt` y `README.md` en raíz del repo
4. ✅ Variable de entorno `STANDUP_SHOW_TEST_LINKS` = `false` o no configurada
5. ✅ `GOOGLE_API_KEY` está en Streamlit Cloud Secrets (no en .env del repo)
6. ✅ Screenshots de la app funcionando están en `docs/screenshots/`

---

## 🌐 Publicación en GitHub

El repositorio ya está configurado. Para futuras actualizaciones:

```bash
# Ver estado actual
git status

# Agregar cambios
git add .

# Hacer commit con mensaje descriptivo
git commit -m "chore: update README for Blackboard submission"

# Hacer push a main
git push origin main
```

---

## ⚡ Despliegue en Streamlit Community Cloud

## Limitaciones conocidas

- Dependencia de servicios externos (Gemini y YouTube).
- Transcripciones/metadata pueden fallar por restricciones del video o red.
- La calidad final depende de la calidad de respuestas en la entrevista.

## Roadmap sugerido

- Persistencia de sesiones por usuario.
- Historial de versiones de rutina.
- Ajustes manuales de tono/estructura con controles UI dedicados.
- Exportacion adicional (Markdown/Docx).
