import streamlit as st
from google import genai

# Configuración de la página
st.set_page_config(
    page_title="Mi Chatbot con Gemini",
    page_icon="💬",
    layout="centered"
)

st.title("💬 Chatbot con Gemini y Streamlit")
st.markdown("Pregúntale lo que quieras al modelo oficial de Google.")

# Inicializar el cliente de Gemini usando los secrets de Streamlit
# Asegúrate de haber configurado tu API key en Streamlit Cloud o en .streamlit/secrets.toml
try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("⚠️ No se encontró la API Key. Por favor, configúrala en los Secrets de Streamlit.")
    st.stop()

# Seleccionar el modelo por defecto (gemini-2.5-flash es excelente para chat rápido y eficiente)
MODEL_ID = "gemini-3.6-flash"

# Inicializar el historial de chat en la sesión de Streamlit
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar los mensajes anteriores del historial al recargar la página
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Capturar la entrada del usuario en el campo de chat inferior
if prompt := st.chat_input("¿En qué puedo ayudarte hoy?"):
    # Guardar y mostrar el mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generar la respuesta del asistente
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # Construir el historial para la API utilizando el formato adecuado
            chat_history = [
                {"role": m["role"], "parts": [m["content"]]} 
                for m in st.session_state.messages[:-1]
            ]
            
            # Iniciar una sesión de chat con el historial previo
            chat = client.chats.create(model=MODEL_ID, history=chat_history)
            
            # Enviar el nuevo mensaje y obtener la respuesta en streaming
            response = chat.send_message(prompt)
            full_response = response.text
            
            message_placeholder.markdown(full_response)
            
        except Exception as e:
            full_response = f"Ocurrió un error al procesar tu solicitud: {e}"
            message_placeholder.error(full_response)

    # Guardar la respuesta del asistente en el historial
    st.session_state.messages.append({"role": "assistant", "content": full_response})
