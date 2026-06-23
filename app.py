import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import io

# --- 1. UI SETUP ---
st.set_page_config(layout="wide", page_title="KFB3", page_icon="🦊")

st.markdown(f'''
<link rel="apple-touch-icon" sizes="180x180" href="https://em-content.zobj.net/thumbs/120/apple/325/fox-face_1f98a.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#FF6600"> 
''', unsafe_allow_html=True)

st.title("🦊 KFB3")

# --- 2. SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "rot" not in st.session_state: 
    st.session_state.rot = 0

# --- 3. API KONFIGURATION ---
def get_client():
    if 'gemini_key' not in st.secrets:
        st.error("API Key fehlt. Bitte in den Secrets hinterlegen.")
        st.stop()
    
    retry_options = types.HttpRetryOptions(
        initial_delay=2.0,  
        attempts=6,         
        exp_base=2.0,       
        max_delay=30.0,     
        http_status_codes=[429, 500, 502, 503, 504] 
    )

    return genai.Client(
        api_key=st.secrets["gemini_key"],
        http_options=types.HttpOptions(retry_options=retry_options)
    )

client = get_client()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("📚 Knowledge Base")
    pdfs = st.file_uploader("PDF-Skripte hochladen", type=["pdf"], accept_multiple_files=True)
    if pdfs:
        st.success(f"{len(pdfs)} Skripte geladen.")
    
    if st.button("🗑️ Chat-Verlauf löschen"):
        st.session_state.messages = []
        st.rerun()
        
    st.divider()
    st.info("model: Gemini 3.5 Flash (Code Execution)")

# --- 5. DER MASTER-SOLVER ---
def generate_response(prompt, images, pdf_files):
    try:
        # NEU: Prompt angepasst, um die Nutzung von Code für Mathe zu erzwingen
        sys_instr = """Du bist ein präziser Assistent für Modul 31031 
(Internes Rechnungswesen, FernUniversität Hagen).

PRIORITÄT 1 – DOKUMENTKONTEXT:
Wenn die relevante Information in den Workspace-Dokumenten 
vorhanden ist, beantworte ausschließlich darauf basierend.

PRIORITÄT 2 – FACHWISSEN MIT KENNZEICHNUNG:
Wenn der Dokumentkontext fehlt oder unvollständig ist, 
nutze dein Wissen zu Modul 31031 – kennzeichne diese 
Stellen mit [Fachwissen].

ABSOLUTES VERBOT:
Erfinde niemals fehlende Werte. Wenn Werte fehlen, frage 
nach – rechne NICHT mit angenommenen Beispielwerten.

WICHTIGE REGELN ZUR CODE-EXECUTION:
1. Kündige NIEMALS an, dass du ein Python-Skript schreiben wirst!
2. Sätze wie "I will write a python script..." sind strengstens verboten.
3. Führe Berechnungen sofort, automatisch und ohne Vorwarnung im Hintergrund aus.
4. Antworte durchgehend und ausnahmslos auf Deutsch.

LÖSUNGSPROZESS:
1. Aufgabe analysieren – alle gegebenen Werte auflisten
2. Fehlende Werte sofort benennen – nicht ergänzen
3. Methode aus Modul 31031 anwenden
4. Nutze für komplexe Rechnungen direkt dein Code-Execution-Tool.
5. Ergebnis klar ausgeben

BEI MULTIPLE-CHOICE / WAHR-FALSCH:
Bewerte jede Option zwingend einzeln im folgenden Format:
Option [Buchstabe]:
1. Anomalie-Check: FernUni-Hagen-Besonderheit? Ja/Nein.
2. Behauptung: Was behauptet die Option konkret?
3. Fakt laut Skript/Modul: Was ist die korrekte Aussage?
4. Abgleich: Stimmt Behauptung mit Fakt überein? Ja/Nein.
5. Bewertung: Wahr / Falsch
6. Begründung: Ein Satz.

Vollständigkeitspflicht: Alle Optionen müssen geprüft werden.
Reduziere das Ergebnis NIEMALS auf eine einzige Option, wenn mehrere korrekt sind.

AUSGABEFORMAT:
Aufgabe [Nr.]: [Ergebnis]
Begründung: [Ein Satz auf Basis der FernUni-Methode]

FORMAT: Deutsch, fachlich sauber, Schritt für Schritt."""

        contents = []
        
        for msg in st.session_state.messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])])
            )

        current_parts = []
        
        if pdf_files:
            for pdf in pdf_files:
                pdf_data = pdf.read()
                current_parts.append(types.Part.from_bytes(data=pdf_data, mime_type="application/pdf"))
                pdf.seek(0)
        
        if images:
            for img in images:
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                current_parts.append(types.Part.from_bytes(data=img_byte_arr.getvalue(), mime_type="image/jpeg"))
        
        current_parts.append(types.Part.from_text(text=prompt))
        contents.append(types.Content(role="user", parts=current_parts))

        # NEU: Code Execution explizit in den tools aktiviert
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=sys_instr,
                temperature=0,
                max_output_tokens=15000,
                tools=[{"code_execution": {}}] 
            )
        )

        # NEU: Intelligentes Auslesen von Text, Python-Code UND Rechner-Ergebnissen
        if response.candidates and response.candidates[0].content:
            output_text = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    output_text += part.text
                elif hasattr(part, 'executable_code') and part.executable_code:
                    output_text += f"\n\n**🤖 Python-Rechnung:**\n```python\n{part.executable_code.code}\n```\n"
                elif hasattr(part, 'code_execution_result') and part.code_execution_result:
                    output_text += f"**Ausgabe des Taschenrechners:**\n```text\n{part.code_execution_result.output}\n```\n\n"
            
            if output_text:
                return output_text
            else:
                return "Fehler: Die KI hat eine unerwartete Antwortstruktur zurückgegeben."
        
        return "Fehler: Keine Antwort von der KI erhalten."

    except Exception as e:
        if "503" in str(e) or "overloaded" in str(e).lower():
            return "Fehler: Die Google-Server sind aktuell überlastet. Bitte in 2 Minuten erneut versuchen."
        return f"Fehler: {str(e)}"

# --- 6. UI LAYOUT ---
col1, col2 = st.columns([1, 1.2])

with col1:
    uploaded_files = st.file_uploader("Klausurblätter hochladen...", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    
    processed_images = [] 
    
    if uploaded_files:
        if st.button("🔄 Alle Bilder 90° drehen"): 
            st.session_state.rot = (st.session_state.rot + 90) % 360
        
        for file in uploaded_files:
            img = Image.open(file).convert('RGB')
            img = img.rotate(-st.session_state.rot, expand=True)
            processed_images.append(img)
            st.image(img)

with col2:
    st.subheader("💬 Chat & Lösung")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    auto_prompt = None
    
    if uploaded_files:
        if st.button("🚀 Alle Aufgaben auf den Bildern lösen", type="primary"):
            auto_prompt = "Löse ALLE Aufgaben auf den hochgeladenen Bildern unter strikter Einhaltung deines Lösungsprozesses."
            
    user_input = st.chat_input("Oder stelle eine Frage zu den Dokumenten...")
    
    final_prompt = auto_prompt or user_input
    
    if final_prompt:
        with st.chat_message("user"):
            st.markdown(final_prompt)
        st.session_state.messages.append({"role": "user", "content": final_prompt})
        
        with st.chat_message("assistant"):
            with st.spinner("Gemini analysiert & rechnet..."):
                result = generate_response(final_prompt, processed_images, pdfs)
                st.markdown(result)
        
        st.session_state.messages.append({"role": "assistant", "content": result})
