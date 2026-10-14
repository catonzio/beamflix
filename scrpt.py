import os
import google.oauth2.credentials
from google.assistant.embedded.v1alpha2 import embedded_assistant_pb2
from google.assistant.embedded.v1alpha2 import embedded_assistant_pb2_grpc
import grpc

# 1. Carica le tue credenziali ufficiali salvate in locale
# (Google fornisce utility integrate per fare il login OAuth iniziale)
creds = google.oauth2.credentials.Credentials.from_authorized_user_file('stored_credentials.json')

# 2. Crea il canale gRPC ufficiale verso i server Google
api_endpoint = '://googleapis.com'
channel = grpc.secure_channel(api_endpoint, grpc.composite_channel_credentials(
    grpc.ssl_channel_credentials(),
    grpc.access_token_call_credentials(creds.token)
))

# 3. Prepara il client dell'assistente
assistant = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(channel)

# 4. Configura la richiesta testuale
config = embedded_assistant_pb2.AssistConfig(
    text_query="Riproduci la prima puntata di Wednesday su Netflix in Salotto",
    audio_out_config=embedded_assistant_pb2.AudioOutConfig(encoding='LINEAR16', sample_rate_hertz=16000),
    device_config=embedded_assistant_pb2.DeviceConfig(device_id='tuo_device_id', device_model_id='tuo_modello_id')
)

# Funzione per inviare la richiesta in streaming
def iter_requests():
    yield embedded_assistant_pb2.AssistRequest(config=config)

# 5. Invia il comando
responses = assistant.Assist(iter_requests())
for response in responses:
    if response.dialog_state_out.supplemental_display_text:
        print("Risposta Assistente:", response.dialog_state_out.supplemental_display_text)

