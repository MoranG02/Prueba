import streamlit as st
from google import genai
from google.genai import types

# Configuración de la página
st.set_page_config(
    page_title="Mi Chatbot con Gemini",
    page_icon="💬",
    layout="centered"
)

st.title("💬 Chatbot con Gemini y Streamlit")
st.markdown("Pregúntale lo que quieras al modelo oficial de Google.")

# Inicializar el cliente de Gemini usando los secrets de Streamlit
try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("⚠️ No se encontró la API Key en los Secrets de Streamlit.")
    st.stop()

# Usar el identificador oficial exacto
MODEL_ID = "gemini-2.5-flash"

# Inicializar el historial de chat en la sesión
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar mensajes anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Capturar entrada del usuario
if prompt := st.chat_input("¿En qué puedo ayudarte hoy?"):
    # Guardar y mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generar respuesta del asistente
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # Mapear el historial de Streamlit al formato que acepta la API de Gemini
            formatted_contents = []
            for m in st.session_state.messages:
                # La API usa 'user' y 'model' (en lugar de 'assistant')
                role = "user" if m["role"] == "user" else "model"
                formatted_contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=m["content"])]
                    )
                )

            # Llamada directa al modelo usando generate_content con todo el historial de contexto
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=formatted_contents
            )
            
            full_response = response.text
            message_placeholder.markdown(full_response)
            
        except Exception as e:
            full_response = f"Ocurrió un error al procesar tu solicitud: {e}"
            message_placeholder.error(full_response)

    # Guardar la respuesta del asistente en el historial de la sesión
    st.session_state.messages.append({"role": "assistant", "content": full_response})
