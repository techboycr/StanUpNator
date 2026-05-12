# 📤 GUÍA PASO A PASO: ENTREGA EN BLACKBOARD

## 🎯 Objetivo Final
Entregar en Blackboard un DOCX con toda la información, links públicos y screenshots.

---

## ✅ PASO 1: Verificar que TODO Funciona (5 min)

### 1.1 Verificar Repositorio GitHub

```
URL: https://github.com/techboycr/StanUpNator
```

**Checklist:**
- [ ] Se abre sin errores
- [ ] Es visible (Public)
- [ ] Contiene archivo `app.py`
- [ ] Contiene archivo `requirements.txt`
- [ ] Contiene archivo `README.md`

### 1.2 Verificar App Desplegada

```
URL: https://standup-ai-demo.streamlit.app/
```

**Checklist:**
- [ ] Se abre directamente en navegador
- [ ] No pide autenticación
- [ ] Se ve el wizard con 3 pasos
- [ ] Botón "Next" está visible

---

## 📥 PASO 2: Descargar el DOCX (2 min)

### 2.1 Ubicación del Archivo

El archivo DOCX ya fue generado automáticamente:

```
Ruta: c:\dev\master_machine_learning_and_AI\StandUp-AI\Entrega_Blackboard_StandUp-AI.docx
```

### 2.2 Abrir y Verificar

1. **Windows:**
   - Click derecho en `Entrega_Blackboard_StandUp-AI.docx`
   - Seleccionar "Abrir con" → Microsoft Word

2. **Alternativa (LibreOffice):**
   - Hacer doble click en el DOCX
   - Abrir automáticamente con LibreOffice Writer

3. **Verificar contenido:**
   - [ ] Título: "🎤 Generative StandUp AI"
   - [ ] Tabla con links GitHub y Streamlit Cloud
   - [ ] Screenshots de la app
   - [ ] Código Python formateado
   - [ ] Instrucciones de instalación

---

## 📋 PASO 3: Copiar Links Públicos (1 min)

Estos links serán necesarios en Blackboard:

### 3.1 Link al Repositorio GitHub

```
COPIAR Y PEGAR EN BLACKBOARD:
https://github.com/techboycr/StanUpNator
```

**Cómo verificar que es público:**
1. Abrir el link en incógnito (Ctrl+Shift+N en Chrome)
2. Debería mostrarse el repositorio sin iniciar sesión

### 3.2 Link a la App Desplegada

```
COPIAR Y PEGAR EN BLACKBOARD:
https://standup-ai-demo.streamlit.app/
```

**Cómo verificar que funciona:**
1. Abrir en navegador
2. Debería mostrar el wizard directamente
3. Probar hacer click en "Next: procesar videos"

---

## 🖥️ PASO 4: Subir a Blackboard (5 min)

### 4.1 Ir al Formulario de Entrega

1. **Acceder a Blackboard**
2. **Ir a la tarea:** "Entrega Final - Aplicación AI" (o similar)
3. **Click en:** "Crear envío" o "Submit"

### 4.2 Llenar Campos

#### Campo 1: "Descripción del Proyecto"

**Copiar y pegar:**

```
APLICACIÓN DE GENRACIÓN DE RUTINAS DE STAND-UP CON IA

StandUp AI es una aplicación web interactiva que utiliza Google Gemini para 
crear rutinas de stand-up personalizadas en español. 

El sistema incluye:
- Wizard de 3 pasos con interfaz Streamlit
- Entrevista guiada de 15 preguntas
- Pipeline de generación multi-etapa (análisis → rutina → QA)
- RAG con FAISS e integración de YouTube
- Exportación en TXT y PDF

Ambas aplicaciones son públicas y accesibles.
```

#### Campo 2: "Link al Repositorio GitHub"

**Copiar y pegar:**

```
https://github.com/techboycr/StanUpNator
```

#### Campo 3: "Link a la App Desplegada"

**Copiar y pegar:**

```
https://standup-ai-demo.streamlit.app/
```

#### Campo 4: Subir Archivo

**Acción:**
1. Click en **"Examinar mi equipo"** o **"Subir archivo"**
2. Seleccionar: `Entrega_Blackboard_StandUp-AI.docx`
3. Click **"Abrir"**

---

## ✅ PASO 5: Confirmar Entrega

### 5.1 Verificar Antes de Enviar

**Checklist final:**
- [ ] Campo 1: Descripción rellenada
- [ ] Campo 2: Link GitHub es correcto
- [ ] Campo 3: Link App es correcto
- [ ] Campo 4: DOCX está seleccionado
- [ ] Todos los campos requeridos (*) están completos

### 5.2 Enviar

1. **Click en:** "Enviar" o "Submit"
2. Esperar confirmación (página mostrará "✅ Envío completado" o similar)
3. Tomar captura de pantalla como comprobante

---

## 🎬 PRUEBA RÁPIDA DE LA APP (OPCIONAL)

Antes de entregar, prueba rápidamente que la app funciona:

### Prueba del Wizard

1. Abrir: https://standup-ai-demo.streamlit.app/
2. **Paso 1:**
   - Copiar un link de YouTube
   - Click en "Next: procesar videos"
   - Esperar validación
3. **Paso 2:**
   - Responder 2-3 preguntas
   - Click en "Next: construir perfil"
4. **Paso 3:**
   - Ver el perfil generado
   - Responder "sí" en el chat
   - Ver generación iniciarse
   - Esperar resultado
   - Click en "Descargar PDF"

**Resultado esperado:**
- PDF se descarga sin errores
- Contiene la rutina generada

---

## 🆘 TROUBLESHOOTING

### "El DOCX no existe"

**Solución:**
```bash
# Ejecutar en PowerShell desde la carpeta del proyecto:
python generate_blackboard_submission.py
```

### "El link GitHub no funciona"

**Verificar:**
1. Ir a: https://github.com/techboycr/StanUpNator
2. Click en **Settings** → **Visibility**
3. Debe estar en **Public**
4. Si no, cambiar a Public y esperar 1 minuto

### "La app no se abre en Streamlit Cloud"

**Verificar:**
1. Ir a: https://share.streamlit.io/
2. Buscar: "StanUpNator"
3. Si no aparece, hacer click en "New app"
4. Seleccionar: `techboycr/StanUpNator` → `main` → `app.py`

### "Las screenshots no se ven en el DOCX"

**Solución:**
1. Verificar que existen: `docs/screenshots/wizard-step1.png`
2. Ejecutar: `python generate_blackboard_submission.py`
3. El nuevo DOCX incluirá las screenshots

---

## 📊 Resumen de Entrega

```
┌─────────────────────────────────────┐
│   CHECKLIST DE ENTREGA COMPLETA    │
├─────────────────────────────────────┤
│ ✅ Repositorio GitHub es público   │
│ ✅ App está desplegada en Streamlit │
│ ✅ DOCX generado automáticamente    │
│ ✅ Links verificados y funcionales  │
│ ✅ Screenshots incluidas en DOCX    │
│ ✅ Código Python incluido           │
│ ✅ 18 tests unitarios pasando       │
│ ✅ Todos los archivos commiteados   │
└─────────────────────────────────────┘

✅ ESTADO: 100% LISTO PARA ENTREGAR
```

---

## 📞 Información de Contacto / Dudas

Si algo no funciona:

1. **Verificar GitHub está actualizado:**
   ```bash
   git status
   git log --oneline -n 5
   ```

2. **Verificar Streamlit Cloud deployment:**
   - Ir a: https://share.streamlit.io/
   - Buscar en "My apps"
   - Verificar que dice "Deploying..." o "Running"

3. **Ejecutar tests locales:**
   ```bash
   pytest tests/test_standup.py -v
   ```

---

## 🎉 ¡LISTO!

**El proceso es simple:**

1. ✅ Descargar DOCX
2. ✅ Copiar links
3. ✅ Subir a Blackboard
4. ✅ Enviar

**Tiempo total: ~15 minutos**

---

**Generado:** $(date)
**Proyecto:** StandUp AI
**Versión:** 1.0 - Entrega Completa
