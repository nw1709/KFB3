import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import io

st.set_page_config(layout="wide", page_title="KFB3", page_icon="🦊")

st.markdown(f'''
<link rel="apple-touch-icon" sizes="180x180" href="https://em-content.zobj.net/thumbs/120/apple/325/fox-face_1f98a.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#FF6600"> 
''', unsafe_allow_html=True)

st.title("🦊 KFB3")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "rot" not in st.session_state: 
    st.session_state.rot = 0

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
        http_options=types.HttpOptions(retry_options=retry_options, timeout=300000)
    )

client = get_client()

with st.sidebar:
    st.header("📚 Knowledge Base")
    pdfs = st.file_uploader("PDF-Skripte hochladen", type=["pdf"], accept_multiple_files=True)
    if pdfs:
        st.success(f"{len(pdfs)} Skripte geladen.")
    
    if st.button("🗑️ Chat-Verlauf manuell löschen", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
        
    st.divider()
    st.info("Gemini 3.5 Flash")

def generate_response(prompt, images, pdf_files):
    try:
        sys_instr = """Du bist ein präziser Assistent für Modul 31031 
(Internes Rechnungswesen, FernUniversität Hagen).

PRIORITÄT 1 – DOKUMENTKONTEXT:
Wenn die relevante Information in den Workspace-Dokumenten 
vorhanden ist, beantworte ausschließlich darauf basierend.

PRIORITÄT 2 – FACHWISSEN MIT KENNZEICHNUNG:
Wenn Dokumentkontext fehlt, nutze dein Wissen zu Modul 31031 – kennzeichne 
diese Stellen mit [Fachwissen].

ABSOLUTES VERBOT:
Erfinde niemals fehlende Werte. Wenn Werte fehlen, frage 
nach – rechne NICHT mit angenommenen Beispielwerten.

WICHTIGE REGELN ZUR CODE-EXECUTION (Zwingend beachten!):
1. ISOLIERTE UMGEBUNG: Dein Python-Code hat absolut KEINEN Zugriff auf die hochgeladenen Bilder (wie z.B. .jpeg) oder PDFs!
2. DER RICHTIGE WORKFLOW: Du musst zuerst mit deinen Fähigkeiten zur Bilderkennung alle Vektoren, Matrizen und Zahlen aus dem Klausurblatt ablesen. 
3. HARDCODING: Trage diese abgelesenen Zahlen dann als feste Variablen in deinen Python-Code ein, um die Mathematik zu lösen. 
4. KEIN CHAT-GEPLÄNKEL: Kündige dein Vorhaben nicht an. Führe den Code sofort aus!
5. SPRACHE: Antworte immer auf Deutsch.
6. UNSICHTBARER CODE: Der Benutzer kann deinen Code und das Rechner-Ergebnis NICHT sehen! Du MUSST das finale Ergebnis nach der Berechnung zwingend noch einmal als normalen Text ausformulieren!

LÖSUNGSPROZESS:
1. Aufgabe analysieren – alle gegebenen Werte auflisten
2. Fehlende Werte sofort benennen – nicht ergänzen
3. Methode aus Modul 31031 anwenden
4. Code Execution ausführen (mit den hardcodierten Zahlen!)
5. Ergebnis klar ausgeben

BEI MULTIPLE-CHOICE / WAHR-FALSCH:
Bewerte jede Option zwingend einzeln:
Option [Buchstabe]:
1. Anomalie-Check: FernUni-Besonderheit? Ja/Nein.
2. Behauptung: Was behauptet die Option?
3. Fakt laut Skript/Modul: Was ist die korrekte Aussage?
4. Abgleich: Stimmt Behauptung mit Fakt überein? Ja/Nein.
5. Bewertung: Wahr / Falsch
6. Begründung: Ein Satz.

Vollständigkeitspflicht: Alle Optionen müssen geprüft werden!

AUSGABEFORMAT:
Aufgabe [Nr.]: [Ergebnis]
Begründung: [Ein Satz auf Basis der FernUni-Methode]"""

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

        if response.candidates and response.candidates[0].content:
            output_text = ""
            raw_output = ""
            
            for part in response.candidates[0].content.parts:
                # LÖSUNG 2: Wir fangen hier sauber alles ab!
                if hasattr(part, 'text') and part.text:
                    output_text += part.text
                elif hasattr(part, 'executable_code') and part.executable_code:
                    raw_output += f"\n\n**🤖 Abgebrochener Python-Code:**\n```python\n{part.executable_code.code}\n```\n"
                elif hasattr(part, 'code_execution_result') and part.code_execution_result:
                    raw_output += f"\n> *[Taschenrechner liefert: {part.code_execution_result.output.strip()}]*\n"
            
            if output_text.strip():
                return output_text
            elif raw_output.strip():
                return f"Text nicht fertig formuliert. Hier ist der rohe Zwischenstand der Maschine:\n{raw_output}"
            else:
                return "Fehler: Die KI hat eine leere Antwort zurückgegeben."
        
        return "Fehler: Keine Antwort erhalten."

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
        if st.button("Bilder 90° drehen"): 
            st.session_state.rot = (st.session_state.rot + 90) % 360
        
        for file in uploaded_files:
            img = Image.open(file).convert('RGB')
            img = img.rotate(-st.session_state.rot, expand=True)
            processed_images.append(img)
            st.image(img)

with col2:
    st.subheader("Chat")
    
    if uploaded_files:
        if st.button("Aufgaben lösen & Verlauf auto-clear)", type="primary", use_container_width=True):
            st.session_state.messages = []
            
            auto_prompt = "Löse ALLE Aufgaben auf den hochgeladenen Bildern unter strikter Einhaltung deines Lösungsprozesses."
            st.session_state.messages.append({"role": "user", "content": auto_prompt})
            
            with st.spinner("Gemini rechnet..."):
                answer = generate_response(auto_prompt, processed_images, pdfs)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            
            st.rerun()

    chat_container = st.container(height=600)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    if user_input := st.chat_input("Chat"):
        if not uploaded_files:
            st.warning("Bitte lade zuerst eine Aufgabe hoch!")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(user_input)
            
            with st.chat_message("assistant"):
                with st.spinner("Gemini antwortet..."):
                    result = generate_response(user_input, processed_images, pdfs)
                    st.markdown(result)
                    st.session_state.messages.append({"role": "assistant", "content": result})
