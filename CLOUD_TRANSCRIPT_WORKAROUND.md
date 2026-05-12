# 📝 Solución: Transcripts Manuales en Streamlit Cloud

## ❓ ¿Por qué falla en Streamlit Cloud pero funciona localmente?

**Razón:** YouTube bloquea solicitudes automatizadas desde servidores cloud por:
- IP de datacenter identificada como bot
- Rate limiting específico para Streamlit Cloud
- Protección Cloudflare contra automatización
- Restricciones regionales

**Solución:** Descargar transcripts localmente y pegarlos manualmente en la app de Streamlit Cloud.

---

## 🎯 Paso 1: Obtener Transcripts Localmente

### Opción A: Desde YouTube (Interfaz Web)

1. **Abre el video en YouTube**
   - Ejemplo: https://www.youtube.com/watch?v=8pLi57wn0m0

2. **Click en "Mostrar transcripción"**
   - En la esquina superior derecha del video, click en `⋯` (más opciones)
   - Selecciona "Mostrar transcripción"

3. **Copiar toda la transcripción**
   - Click derecho en la transcripción
   - "Seleccionar todo" (Ctrl+A)
   - "Copiar" (Ctrl+C)

### Opción B: Desde Python en tu Computador

```python
from youtube_transcript_api import YouTubeTranscriptApi

# Video ID sin URL
video_ids = [
    '8pLi57wn0m0',
    '8AiulsAi_bM',
    'bFqu9YVuAgI'
]

for vid in video_ids:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(vid, languages=['es', 'en'])
        text = " ".join([item['text'] for item in transcript])
        
        # Guardar en archivo
        with open(f"{vid}.txt", "w", encoding="utf-8") as f:
            f.write(text)
        
        print(f"✅ {vid}: {len(text)} caracteres")
    except Exception as e:
        print(f"❌ {vid}: {e}")
```

### Opción C: Usar Herramienta Online

- **Rev.com Caption Extractor**: https://www.rev.com/captions
- **Google Sheets Script**: =GETFEED("https://www.youtube.com/watch?v=VIDEO_ID")

---

## 📤 Paso 2: Usar en Streamlit Cloud

### En la App:

1. **Ir a Paso 1: Referencias de Comedia**

2. **Click en "Alternativa: Pegar transcripts manualmente"** (aparece cuando fallan descargas automáticas)

3. **Formato correcto:**

```
[VIDEO_ID o URL]
[TEXTO DEL TRANSCRIPT AQUI]
---

[VIDEO_ID SIGUIENTE]
[TRANSCRIPT DEL SIGUIENTE VIDEO]
---
```

### Ejemplo completo:

```
8pLi57wn0m0
Buenas noches pues pues ya te digo nada que os voy a dar un consejo 
un consejo para toda vuestra vida observad Ese es el consejo no que 
hay que observar tenéis que observar Porque esos son todo ventajas 
aparte Dios nos d
---

8AiulsAi_bM
Hoy les quiero contar una anécdota que me pasó el otro día en el supermercado
Estaba comprando pan y de repente llega una persona con un carrito lleno
---
```

4. **Click en "Usar transcripts pegados manualmente"**

5. **¡Listo!** La app indexará los transcripts y continuarás al Paso 2

---

## ⚡ Tips Rápidos

| Problema | Solución |
|----------|----------|
| **Transcript muy largo** | Usar los primeros 5000-8000 caracteres |
| **Múltiples idiomas** | Transcripts en español funcionan mejor |
| **Caracteres extraños** | Copiar desde YouTube directamente evita encoding issues |
| **No funciona el pegado** | Asegurar que el formato sea exacto (---) entre videos |

---

## 🔧 Alternativa: Ejecutar Localmente

Si necesitas la experiencia completa de descarga automática sin intervención manual:

```bash
# Clonar el repo
git clone https://github.com/techboycr/StanUpNator.git
cd StandUp-AI

# Activar venv y instalar
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt

# Ejecutar localmente (con descarga automática de transcripts)
streamlit run app.py
```

Localmente los transcripts se descargarán automáticamente sin problemas.

---

## 📞 Futura Mejora

Se está investigando:
- Usar proxies residenciales para Streamlit Cloud
- Integrar con Rev.com API (de pago)
- Implementar caching de transcripts
- Usar yt-dlp con configuración especializada

Por ahora, la solución manual es pragmática y funciona perfecto.

---

**Última actualización:** May 12, 2026
**Estado:** ✅ Implementado en app.py

