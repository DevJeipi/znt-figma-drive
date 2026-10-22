import io
import json
import os
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


SCOPES = ["https://www.googleapis.com/auth/drive"]

MONTHS_PT = [
    ("01 - Janeiro", ["janeiro", "jan"]),
    ("02 - Fevereiro", ["fevereiro", "fev"]),
    ("03 - Março", ["marco", "março", "mar"]),
    ("04 - Abril", ["abril", "abr"]),
    ("05 - Maio", ["maio", "mai"]),
    ("06 - Junho", ["junho", "jun"]),
    ("07 - Julho", ["julho", "jul"]),
    ("08 - Agosto", ["agosto", "ago"]),
    ("09 - Setembro", ["setembro", "set"]),
    ("10 - Outubro", ["outubro", "out"]),
    ("11 - Novembro", ["novembro", "nov"]),
    ("12 - Dezembro", ["dezembro", "dez"]),
]


class DriveError(Exception):
    """Erro personalizado para operações do Google Drive."""
    pass


def normalize_str(text: str) -> str:
    """Normaliza string para comparação ignorando caixa, acentos e espaços extras."""
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_alnum(text: str) -> str:
    """Normaliza mantendo apenas letras e números (ignora colchetes, traços, pontos)."""
    norm = normalize_str(text)
    return re.sub(r"[^a-z0-9]+", " ", norm).strip()


def format_month_standard(raw_month: str) -> str:
    """
    Converte qualquer nome de página/mês (ex: 'Outubro', 'Outubro 2026', '10 - Outubro', 'Out/26')
    para o padrão da agência: '01 - Janeiro' ... '10 - Outubro' ... '12 - Dezembro'.
    """
    if not raw_month or not raw_month.strip():
        return ""

    norm = normalize_str(raw_month)

    # 1. Busca pelo nome completo do mês (ex: "outubro")
    for canonical, aliases in MONTHS_PT:
        full_name = aliases[0]
        if re.search(rf"\b{full_name}\b", norm) or full_name in norm:
            return canonical

    # 2. Busca pela abreviação de 3 letras como palavra isolada (ex: "out/26", "out 2026")
    for canonical, aliases in MONTHS_PT:
        abbr = aliases[1]
        if re.search(rf"\b{abbr}\b", norm):
            return canonical

    # 3. Se informou apenas número de 1 a 12
    match_num = re.match(r"^0?([1-9]|1[0-2])\b", norm)
    if match_num:
        idx = int(match_num.group(1)) - 1
        return MONTHS_PT[idx][0]

    return raw_month.strip()


class DriveClient:
    def __init__(
        self,
        base_dir: str,
        credentials_info: Optional[dict] = None,
        token_info: Optional[dict] = None,
    ):
        self.base_dir = base_dir
        self.credentials_path = os.path.join(base_dir, "credentials.json")
        self.token_path = os.path.join(base_dir, "token.json")
        self.credentials_info = credentials_info
        self.token_info = token_info
        self.service = None

        # Tenta carregar credenciais do Streamlit Secrets se estiver rodando em nuvem
        self._load_from_streamlit_secrets()

    def _load_from_streamlit_secrets(self):
        try:
            import streamlit as st
            if not self.token_info and hasattr(st, "secrets") and "google_token" in st.secrets:
                self.token_info = dict(st.secrets["google_token"])
            if not self.credentials_info and hasattr(st, "secrets"):
                if "google_credentials" in st.secrets:
                    self.credentials_info = dict(st.secrets["google_credentials"])
                elif "google_service_account" in st.secrets:
                    self.credentials_info = dict(st.secrets["google_service_account"])
        except Exception:
            pass

    def is_authenticated(self) -> bool:
        """Verifica se já existe um token válido ou credencial pronta."""
        if self.service is not None:
            return True
        if self.token_info or self.credentials_info:
            return True
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
                if creds and (creds.valid or (creds.expired and creds.refresh_token)):
                    return True
            except Exception:
                return False
        return False

    def authenticate(self) -> None:
        """Autentica no Google Drive via OAuth 2.0 (ou Service Account se aplicável)."""
        creds = None

        # 1. Tenta autenticar a partir de token_info em memória (Streamlit Cloud Secrets)
        if self.token_info:
            try:
                creds = Credentials.from_authorized_user_info(self.token_info, SCOPES)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
            except Exception:
                creds = None

        # 2. Tenta autenticar a partir de credentials_info (Service Account ou Client Secrets)
        if not creds and self.credentials_info:
            try:
                if self.credentials_info.get("type") == "service_account":
                    creds = service_account.Credentials.from_service_account_info(
                        self.credentials_info, scopes=SCOPES
                    )
            except Exception:
                creds = None

        # 3. Se não veio de Secrets, tenta o token.json local no disco
        if not creds and os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception:
                creds = None

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                if os.path.exists(self.base_dir):
                    with open(self.token_path, "w", encoding="utf-8") as token_file:
                        token_file.write(creds.to_json())
            except Exception:
                creds = None

        # 4. Se ainda não tem creds, tenta credentials.json local
        if not creds or not creds.valid:
            alt_cred_path = os.path.join(self.base_dir, "credentials.json.json")
            if not os.path.exists(self.credentials_path) and os.path.exists(alt_cred_path):
                os.replace(alt_cred_path, self.credentials_path)

            if not os.path.exists(self.credentials_path):
                raise DriveError(
                    "Credenciais do Google Drive não encontradas.\n"
                    "Certifique-se de que o arquivo 'credentials.json' está presente ou configurado nos Secrets."
                )

            with open(self.credentials_path, "r", encoding="utf-8") as f:
                cred_data = json.load(f)

            if cred_data.get("type") == "service_account":
                creds = service_account.Credentials.from_service_account_file(
                    self.credentials_path, scopes=SCOPES
                )
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(self.token_path, "w", encoding="utf-8") as token_file:
                    token_file.write(creds.to_json())

        self.service = build("drive", "v3", credentials=creds)

    def ensure_service(self):
        if self.service is None:
            self.authenticate()

    @staticmethod
    def extract_folder_id_from_url(url_or_id: str) -> Optional[str]:
        """Extrai o ID de uma pasta do Google Drive a partir de um link ou ID puro."""
        text = url_or_id.strip()
        if not text:
            return None
        match = re.search(r"/folders/([a-zA-Z0-9_-]+)", text)
        if match:
            return match.group(1)
        if re.match(r"^[a-zA-Z0-9_-]{15,60}$", text) and "/" not in text and ">" not in text:
            return text
        return None

    def list_subfolders(self, parent_id: str) -> List[Dict[str, str]]:
        """Lista todas as subpastas diretas dentro de uma pasta pai."""
        self.ensure_service()
        query = (
            f"'{parent_id}' in parents and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            f"trashed = false"
        )
        folders = []
        page_token = None
        while True:
            resp = self.service.files().list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, webViewLink)",
                pageToken=page_token,
                pageSize=200,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            folders.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        folders.sort(key=lambda x: x.get("name", "").lower())
        return folders

    def find_folder_by_name(
        self,
        name: str,
        parent_id: Optional[str] = None,
        fuzzy_match: bool = True,
    ) -> Optional[Dict[str, str]]:
        """
        Procura uma pasta pelo nome (ignorando maiúsculas/minúsculas, acentos e pequenas diferenças de pontuação).
        """
        self.ensure_service()
        target_norm = normalize_str(name)
        target_alnum = normalize_alnum(name)

        if parent_id:
            subfolders = self.list_subfolders(parent_id)
            # 1. Busca correspondência exata normalizada
            for folder in subfolders:
                if normalize_str(folder["name"]) == target_norm:
                    return folder

            # 2. Busca ignorando pontuação/colchetes/traços (ex: "01. Clientes ativos" == "01 - Clientes ativos")
            for folder in subfolders:
                if normalize_alnum(folder["name"]) == target_alnum and target_alnum:
                    return folder

            # 3. Busca parcial se habilitado
            if fuzzy_match and target_alnum:
                for folder in subfolders:
                    f_alnum = normalize_alnum(folder["name"])
                    if f_alnum and (target_alnum in f_alnum or f_alnum in target_alnum):
                        return folder
            return None
        else:
            # Busca de pasta raiz no Drive
            escaped_name = name.strip().replace("'", "\\'")
            query = (
                f"mimeType = 'application/vnd.google-apps.folder' and "
                f"name = '{escaped_name}' and trashed = false"
            )
            resp = self.service.files().list(
                q=query,
                spaces="drive",
                fields="files(id, name, webViewLink)",
                pageSize=20,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            files = resp.get("files", [])
            if files:
                return files[0]

            # Fallback caso o nome tenha colchetes como "[ZNT] Organização" vs "ZNT Organização"
            tokens = [t for t in target_alnum.split() if len(t) >= 3]
            if tokens:
                first_token = tokens[0].replace("'", "\\'")
                fallback_q = (
                    f"mimeType = 'application/vnd.google-apps.folder' and "
                    f"name contains '{first_token}' and trashed = false"
                )
                resp2 = self.service.files().list(
                    q=fallback_q,
                    spaces="drive",
                    fields="files(id, name, webViewLink)",
                    pageSize=50,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                ).execute()
                for f in resp2.get("files", []):
                    f_alnum = normalize_alnum(f["name"])
                    if f_alnum == target_alnum or (target_alnum in f_alnum):
                        return f
            return None

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Dict[str, str]:
        """Cria uma pasta no Google Drive e retorna {'id', 'name', 'webViewLink'}."""
        self.ensure_service()
        metadata = {
            "name": name.strip(),
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        folder = self.service.files().create(
            body=metadata,
            fields="id, name, webViewLink",
            supportsAllDrives=True,
        ).execute()
        return folder

    def get_or_create_subfolder(self, parent_id: str, folder_name: str) -> Dict[str, str]:
        """Localiza uma subpasta exata dentro de parent_id ou cria se não existir."""
        self.ensure_service()
        existing = self.find_folder_by_name(folder_name, parent_id=parent_id, fuzzy_match=False)
        if existing:
            return existing
        return self.create_folder(folder_name, parent_id=parent_id)

    def resolve_base_clients_folder(self, base_setting: str) -> Dict[str, str]:
        """
        Localiza a pasta '01 - Clientes ativos'.
        Aceita tanto um Link/ID direto da pasta quanto o caminho '[ZNT] Organização > Agência > 01 - Clientes ativos'.
        """
        self.ensure_service()
        direct_id = self.extract_folder_id_from_url(base_setting)
        if direct_id:
            try:
                folder = self.service.files().get(
                    fileId=direct_id,
                    fields="id, name, webViewLink",
                    supportsAllDrives=True,
                ).execute()
                return folder
            except Exception as exc:
                raise DriveError(f"Não foi possível acessar a pasta de ID '{direct_id}': {exc}") from exc

        parts = [p.strip() for p in re.split(r"[>/\\]", base_setting) if p.strip()]
        if not parts:
            raise DriveError("Configure o caminho da pasta base (ex: [ZNT] Organização > Agência > 01 - Clientes ativos).")

        current_folder = self.find_folder_by_name(parts[0], parent_id=None, fuzzy_match=True)
        if not current_folder:
            raise DriveError(
                f"Não foi encontrada a pasta inicial '{parts[0]}' no seu Google Drive.\n"
                "Dica: Você também pode colar o link direto da pasta '01 - Clientes ativos' no campo Pasta Base."
            )

        for part in parts[1:]:
            next_folder = self.find_folder_by_name(part, parent_id=current_folder["id"], fuzzy_match=True)
            if not next_folder:
                raise DriveError(
                    f"Não foi encontrada a subpasta '{part}' dentro de '{current_folder['name']}'.\n"
                    "Verifique o nome ou cole o link direto da pasta '01 - Clientes ativos'."
                )
            current_folder = next_folder

        return current_folder

    def resolve_or_create_target_path(
        self,
        clients_base_folder_id: str,
        client_name: str,
        month_name: str,
        subpath_template: str = "[Cliente] > 01 - Entregas > [Mês] > Artes",
    ) -> Tuple[Dict[str, str], List[str]]:
        """
        Navega a partir da pasta '01 - Clientes ativos' seguindo o template e cria as pastas que ainda não existirem.
        Garante que [Cliente] fique em MAIÚSCULAS e [Mês] no formato '01 - Janeiro' ... '10 - Outubro'.
        """
        self.ensure_service()
        raw_steps = [s.strip() for s in re.split(r"[>/\\]", subpath_template) if s.strip()]
        resolved_names = []
        current_parent_id = clients_base_folder_id
        current_folder = None

        formatted_client = client_name.strip().upper()
        formatted_month = format_month_standard(month_name)

        for step in raw_steps:
            is_month_step = "[mês]" in step.lower() or "[mes]" in step.lower()
            is_client_step = "[cliente]" in step.lower()

            actual_name = step
            actual_name = re.sub(r"\[cliente\]", formatted_client, actual_name, flags=re.IGNORECASE)
            actual_name = re.sub(r"\[m[eê]s\]", formatted_month, actual_name, flags=re.IGNORECASE)

            existing = self.find_folder_by_name(
                actual_name,
                parent_id=current_parent_id,
                fuzzy_match=(is_month_step or is_client_step),
            )
            if existing:
                current_folder = existing
            else:
                current_folder = self.create_folder(actual_name, parent_id=current_parent_id)

            current_parent_id = current_folder["id"]
            resolved_names.append(current_folder["name"])

        return current_folder, resolved_names

    def resolve_or_create_id_visual_path(
        self,
        clients_base_folder_id: str,
        client_name: str,
    ) -> Tuple[Dict[str, str], List[str]]:
        """
        Navega até a pasta 'ID Visual' do cliente dentro de '01 - Entregas'.
        Caminho no Drive: [Cliente] > 01 - Entregas > ID Visual
        """
        self.ensure_service()
        formatted_client = client_name.strip().upper()
        resolved_names = []

        # 1. Encontra ou cria a pasta do Cliente
        client_folder = self.find_folder_by_name(formatted_client, parent_id=clients_base_folder_id, fuzzy_match=True)
        if not client_folder:
            client_folder = self.create_folder(formatted_client, parent_id=clients_base_folder_id)
        resolved_names.append(client_folder["name"])

        # 2. Encontra ou cria a pasta '01 - Entregas'
        entregas_folder = self.find_folder_by_name("01 - Entregas", parent_id=client_folder["id"], fuzzy_match=True)
        if not entregas_folder:
            entregas_folder = self.create_folder("01 - Entregas", parent_id=client_folder["id"])
        resolved_names.append(entregas_folder["name"])

        # 3. Encontra ou cria a pasta 'ID Visual'
        id_visual_folder = self.find_folder_by_name("ID Visual", parent_id=entregas_folder["id"], fuzzy_match=True)
        if not id_visual_folder:
            id_visual_folder = self.create_folder("ID Visual", parent_id=entregas_folder["id"])
        resolved_names.append(id_visual_folder["name"])

        return id_visual_folder, resolved_names

    def upload_image_bytes(
        self,
        folder_id: str,
        filename: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        overwrite_existing: bool = True,
    ) -> Dict[str, str]:
        """
        Faz o upload de uma arte para a pasta de destino no Google Drive.
        Se overwrite_existing=True e já houver um arquivo com o mesmo nome na pasta, atualiza-o sem duplicar.
        """
        self.ensure_service()
        media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype=mime_type, resumable=True)

        existing_file_id = None
        if overwrite_existing:
            escaped_name = filename.replace("'", "\\'")
            q = f"'{folder_id}' in parents and name = '{escaped_name}' and trashed = false"
            resp = self.service.files().list(
                q=q,
                spaces="drive",
                fields="files(id, name)",
                pageSize=1,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            files = resp.get("files", [])
            if files:
                existing_file_id = files[0]["id"]

        if existing_file_id:
            updated = self.service.files().update(
                fileId=existing_file_id,
                media_body=media,
                fields="id, name, webViewLink",
                supportsAllDrives=True,
            ).execute()
            return updated
        else:
            metadata = {
                "name": filename,
                "parents": [folder_id],
            }
            created = self.service.files().create(
                body=metadata,
                media_body=media,
                fields="id, name, webViewLink",
                supportsAllDrives=True,
            ).execute()
            return created
