import requests
from Utils.tools import Tools, CustomException
from Utils.querys import Querys
from Models.IntranetGraphTokenModel import IntranetGraphTokenModel as TokenModel
from datetime import datetime, timedelta

from Utils.constants import (
    MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID,
    MICROSOFT_API_SCOPE, MICROSOFT_URL, MICROSOFT_URL_GRAPH, PARENT_FOLDER,
    TARGET_FOLDER, EMAIL_USER
)

class Graph:

    def __init__(self, db):
        self.db = db
        self.tools = Tools()
        self.querys = Querys(self.db)
        self.token = None

    # Función para obtener el token, validando si está vigente o no
    def obtener_correos(self):
        
        filtered_emails = list()

        # Obtenemos el token desde la base de datos
        result = self.querys.get_token()

        # Validamos si el token existe y está vigente
        self.token = self.validar_existencia_token(result)

        if self.token:
            # Obtenemos el id de la carpeta padre y luego de la hija
            folder_id = self.get_folder_id(TARGET_FOLDER)

            # Obtenemos los correos de la carpeta hija
            emails = self.extraer_correos(folder_id)

            if emails:
                # Filtramos los correos evitando enviar los de spam
                filtered_emails = [
                    email for email in emails
                    if not email['from']['emailAddress']['address'].lower().startswith(('postmaster', 'noreply'))
                    and not email['subject'].startswith(('[!!Spam]', '[!!Massmail]'))
                ]

                # Ordenamos por fecha de la actual a la antigua
                filtered_emails.sort(key=lambda x: x['receivedDateTime'], reverse=True)

        # Retornamos la información.
        return self.tools.output(200, "Datos encontrados.", filtered_emails)

    # Función para validar si el token existe y si está vigente
    def validar_existencia_token(self, result: dict):
        
        # Si hay un token en BD, validar si aún está vigente
        if result:
            fecha_vencimiento_str = result.get('fecha_vencimiento')
            if fecha_vencimiento_str:
                # Convertir string a datetime si es necesario
                if isinstance(fecha_vencimiento_str, str):
                    fecha_vencimiento = datetime.fromisoformat(fecha_vencimiento_str.replace('Z', '+00:00'))
                else:
                    fecha_vencimiento = fecha_vencimiento_str
                
                # Comparar con tiempo actual
                ahora = datetime.now()
                print(f"Fecha vencimiento: {fecha_vencimiento}")
                print(f"Fecha actual: {ahora}")
                
                if ahora < fecha_vencimiento:
                    # Token aún vigente
                    print("Token vigente, retornando desde BD")
                    return result['token']
                else:
                    # Token expirado, desactivar
                    print("Token expirado, desactivando...")
                    token_id = result.get('id')
                    if token_id:
                        # Crear nueva instancia de Querys para desactivar token
                        self.querys.desactivar_token(token_id)
                        print(f"Token {token_id} desactivado")

        # Si no hay token válido, obtener uno nuevo desde Microsoft Graph
        print("Obteniendo nuevo token desde Microsoft Graph API...")
        return self._crear_nuevo_token()

    # Función para obtener el ID de una carpeta específica
    def get_folder_id(self, target_folder: str):

        """Obtiene el ID de una carpeta específica dentro del correo del usuario."""
        result = None
        url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/mailFolders/{target_folder}"
        data = self._make_request(url)
        if data:
            result = data['id']
        return result

    # Función para extraer correos de una carpeta específica
    def extraer_correos(self, folder_id: str):
        """Recupera correos electrónicos de una carpeta específica."""
        emails = []
        max_iterations = 100
        iteration = 0

        if folder_id:
            url = f"{MICROSOFT_URL_GRAPH}{EMAIL_USER}/mailFolders/{folder_id}/messages?$top=100&$select=from,subject,receivedDateTime,bodyPreview,body"

            while url and iteration < max_iterations:
                print(f"Haciendo solicitud a: {url}")
                data = self._make_request(url)
                if not data:
                    break

                new_emails = data.get('value', [])
                if not new_emails:
                    print("No se recuperaron nuevos correos. Deteniendo.")
                    break

                emails.extend(new_emails)
                url = data.get('@odata.nextLink')  # Paginación
                iteration += 1

        return emails

    # Función para realizar peticiones a la API de Microsoft Graph
    def _make_request(self, endpoint):
        """Realiza una petición GET a Microsoft Graph API."""
        if not self.token:
            print("No se pudo obtener el token de acceso.")
            return None

        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(endpoint, headers=headers)

        if response.status_code == 200:
            return response.json()
        print(f"Error en la solicitud: {response.status_code} - {response.text}")
        return None

    # Función para crear un nuevo token desde Microsoft Graph API
    def _crear_nuevo_token(self):
        """Crea un nuevo token desde Microsoft Graph API."""
        url = f"{MICROSOFT_URL}{MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'client_id': MICROSOFT_CLIENT_ID,
            'scope': ' '.join(MICROSOFT_API_SCOPE),
            'client_secret': MICROSOFT_CLIENT_SECRET,
            'grant_type': 'client_credentials'
        }
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            token = response.json().get('access_token')
            expires_in = response.json().get('expires_in')
            
            data_insert = {
                "token": token,
                "fecha_vencimiento": datetime.now() + timedelta(seconds=expires_in)
            }
            # Crear nueva instancia de Querys para insertar token
            self.querys.insertar_datos(TokenModel, data_insert)
            return token
        
        print(f"Error obteniendo el token: {response.status_code} - {response.text}")
        return None
