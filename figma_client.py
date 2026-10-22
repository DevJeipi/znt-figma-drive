import re
import unicodedata
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Optional, Tuple
import requests


def normalize_str(text: str) -> str:
    """Normaliza string para comparação ignorando caixa, acentos e espaços extras."""
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"\s+", " ", text)
    return text


class FigmaError(Exception):
    """Erro personalizado para falhas na API do Figma."""
    pass


class FigmaClient:
    BASE_URL = "https://api.figma.com/v1"

    def __init__(self, access_token: str):
        self.access_token = access_token.strip()
        self.headers = {
            "X-Figma-Token": self.access_token
        }

    @staticmethod
    def is_id_visual_page(page_name: str) -> bool:
        """Verifica se a página é de Formatação Visual / Identidade Visual."""
        norm = normalize_str(page_name)
        return "formatacao visual" in norm or "id visual" in norm or "identidade visual" in norm

    @staticmethod
    def parse_figma_url(url_or_key: str) -> Tuple[str, Optional[str]]:
        """
        Extrai o file_key e opcionalmente o node_id de um link do Figma.
        Suporta URLs /file/, /design/, /proto/ ou a chave direta.
        """
        text = url_or_key.strip()
        if not text:
            raise FigmaError("O link do Figma está vazio.")

        if re.match(r"^[a-zA-Z0-9]{15,35}$", text):
            return text, None

        parsed = urlparse(text)
        path_parts = [p for p in parsed.path.split("/") if p]

        file_key = None
        for i, part in enumerate(path_parts):
            if part in ("file", "design", "proto", "board") and i + 1 < len(path_parts):
                if i + 2 < len(path_parts) and path_parts[i + 2] == "branch" and i + 3 < len(path_parts):
                    file_key = path_parts[i + 3]
                else:
                    file_key = path_parts[i + 1]
                break

        if not file_key:
            raise FigmaError(
                "Não foi possível identificar o arquivo no link informado.\n"
                "Exemplo de link válido: https://www.figma.com/design/ABC123XYZ/Nome-do-Projeto"
            )

        query = parse_qs(parsed.query)
        node_id = None
        if "node-id" in query and query["node-id"]:
            node_id = query["node-id"][0].replace("-", ":")

        return file_key, node_id

    @staticmethod
    def extract_post_prefix_and_card_num(frame_name: str) -> Tuple[str, Optional[int]]:
        """
        Extrai o nome base do post e o número do card a partir do nome do Frame.
        Exemplos:
          'BLOG - CD 1'    -> ('BLOG', 1)
          'BLOG - CD 02'   -> ('BLOG', 2)
          'DICAS - CARD 3' -> ('DICAS', 3)
          'INSTITUCIONAL'  -> ('INSTITUCIONAL', None)
        """
        cleaned = re.sub(r"\s+", " ", frame_name.strip())
        if not cleaned:
            return "ARTE", None

        # Padrão 1: "PREFIXO - CD 1", "PREFIXO - CARD 2", "PREFIXO - SLIDE 3", "PREFIXO - 01"
        match = re.match(
            r"^(.+?)\s*[-–—|/]\s*(?:cd|card|slide|arte|pag|pág|pt)?\s*0*(\d+)\s*$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if match:
            prefix = match.group(1).strip()
            card_num = int(match.group(2))
            return prefix, card_num

        # Padrão 2: "PREFIXO CD 1" (sem hífen, mas com marcador explícito CD/CARD/SLIDE)
        match2 = re.match(
            r"^(.+?)\s+(?:cd|card|slide)\s*0*(\d+)\s*$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if match2:
            prefix = match2.group(1).strip()
            card_num = int(match2.group(2))
            return prefix, card_num

        return cleaned, None

    @classmethod
    def assign_post_groups(cls, frames: List[Dict]) -> List[Dict]:
        """
        Agrupa os frames por prefixo na ordem em que aparecem na página e atribui:
          - 'post_index': 1, 2, 3...
          - 'post_prefix': ex: 'BLOG'
          - 'post_folder_name': ex: 'Post 1 - BLOG'
          - 'card_num': número do card (1, 2, 3...) se houver
        Retorna a lista de frames ordenada por post_index e depois por card_num.
        """
        prefix_to_index: Dict[str, int] = {}
        prefix_display: Dict[str, str] = {}

        enriched = []
        for f in frames:
            prefix, card_num = cls.extract_post_prefix_and_card_num(f.get("name", ""))
            norm_key = prefix.lower().strip()
            if norm_key not in prefix_to_index:
                prefix_to_index[norm_key] = len(prefix_to_index) + 1
                prefix_display[norm_key] = cls.sanitize_filename(prefix)

            p_idx = prefix_to_index[norm_key]
            p_disp = prefix_display[norm_key]
            folder_name = f"Post {p_idx} - {p_disp}"

            f_copy = dict(f)
            f_copy["post_index"] = p_idx
            f_copy["post_prefix"] = p_disp
            f_copy["post_folder_name"] = folder_name
            f_copy["card_num"] = card_num
            enriched.append(f_copy)

        # Ordena os frames por Post (1, 2, 3...) e, dentro do mesmo Post, pelo número do CD (CD 1, CD 2...)
        enriched.sort(
            key=lambda item: (
                item["post_index"],
                item["card_num"] if item["card_num"] is not None else 9999,
                round(item.get("y", 0) / 100.0),
                item.get("x", 0),
            )
        )
        return enriched

    @classmethod
    def assign_id_visual_groups(cls, frames: List[Dict]) -> List[Dict]:
        """
        Para páginas de Formatação Visual / ID Visual:
        Agrupa os frames nas categorias:
          - 'Destaques' (se tiver 'DESTAQUE' no nome)
          - 'Perfil'    (se tiver 'PERFIL' no nome)
          - 'Banners'   (se tiver 'BANNER' no nome)
          - 'ID Visual' (outros frames)
        """
        enriched = []
        category_order = {"Perfil": 1, "Destaques": 2, "Banners": 3, "ID Visual": 4}

        for f in frames:
            name = f.get("name", "")
            norm = normalize_str(name)

            if "destaque" in norm:
                cat = "Destaques"
                tag = "DESTAQUE"
            elif "perfil" in norm:
                cat = "Perfil"
                tag = "PERFIL"
            elif "banner" in norm:
                cat = "Banners"
                tag = "BANNER"
            else:
                cat = "ID Visual"
                tag = "ARTE"

            num_match = re.search(r'(?:destaque|perfil|banner|cd|card|slide|arte)?\s*0*(\d+)', norm)
            card_num = int(num_match.group(1)) if num_match else None

            f_copy = dict(f)
            f_copy["post_index"] = category_order.get(cat, 99)
            f_copy["post_prefix"] = tag
            f_copy["post_folder_name"] = cat
            f_copy["card_num"] = card_num
            f_copy["is_id_visual"] = True
            enriched.append(f_copy)

        enriched.sort(
            key=lambda item: (
                item["post_index"],
                item["card_num"] if item["card_num"] is not None else 9999,
                round(item.get("y", 0) / 100.0),
                item.get("x", 0),
            )
        )
        return enriched

    def get_file_structure(self, file_key: str) -> Dict:
        """
        Busca a estrutura do arquivo (Nome do Projeto, Páginas e Frames).
        """
        if not self.access_token:
            raise FigmaError("Token do Figma não configurado.")

        url = f"{self.BASE_URL}/files/{file_key}?depth=3"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
        except requests.RequestException as exc:
            raise FigmaError(f"Erro de conexão com o Figma: {exc}") from exc

        if response.status_code == 403:
            raise FigmaError("Acesso negado (403). Verifique se o seu Token do Figma é válido e tem acesso a este arquivo.")
        if response.status_code == 404:
            raise FigmaError("Arquivo não encontrado (404). Verifique se o link do Figma está correto.")
        if response.status_code != 200:
            raise FigmaError(f"Erro na API do Figma ({response.status_code}): {response.text}")

        data = response.json()
        project_name = data.get("name", "Cliente Sem Nome").strip()
        document = data.get("document", {})
        pages_raw = document.get("children", [])

        pages = []
        for page in pages_raw:
            if page.get("type") != "CANVAS":
                continue

            page_name = page.get("name", "").strip()
            frames = self._extract_frames_from_page(page, page_name=page_name)
            pages.append({
                "id": page.get("id"),
                "name": page_name,
                "is_id_visual": self.is_id_visual_page(page_name),
                "frames": frames,
            })

        return {
            "file_key": file_key,
            "project_name": project_name,
            "pages": pages,
        }

    def _extract_frames_from_page(self, page_node: Dict, page_name: str = "") -> List[Dict]:
        """
        Extrai todos os Frames de primeiro nível na página (e também dentro de Sections, se houver).
        Ordena pela posição visual no canvas e agrupa em 'Post 1 - NOME' ou categorias de 'ID Visual'.
        """
        frames = []
        valid_frame_types = {"FRAME", "COMPONENT"}

        def add_frame(node: Dict, section_name: Optional[str] = None):
            if node.get("visible", True) is False:
                return
            bbox = node.get("absoluteBoundingBox") or {}
            width = int(round(bbox.get("width", 0)))
            height = int(round(bbox.get("height", 0)))
            x = bbox.get("x", 0)
            y = bbox.get("y", 0)

            frames.append({
                "id": node.get("id"),
                "name": node.get("name", "Arte").strip(),
                "type": node.get("type"),
                "section": section_name,
                "width": width,
                "height": height,
                "x": x,
                "y": y,
            })

        for child in page_node.get("children", []):
            if child.get("visible", True) is False:
                continue
            c_type = child.get("type")
            if c_type in valid_frame_types:
                add_frame(child)
            elif c_type == "SECTION":
                sec_name = child.get("name", "").strip()
                for sec_child in child.get("children", []):
                    if sec_child.get("type") in valid_frame_types:
                        add_frame(sec_child, section_name=sec_name)

        # Primeiro ordena pela posição visual no canvas (linha vertical com tolerância de 120px, depois X)
        frames.sort(key=lambda f: (round(f["y"] / 120.0), f["x"]))

        # Agrupa conforme o tipo de página
        if self.is_id_visual_page(page_name):
            return self.assign_id_visual_groups(frames)
        else:
            return self.assign_post_groups(frames)

    def get_image_urls(
        self,
        file_key: str,
        node_ids: List[str],
        img_format: str = "png",
        scale: float = 2.0,
    ) -> Dict[str, str]:
        """
        Solicita ao Figma a renderização dos frames e retorna um dicionário {node_id: image_url}.
        Faz em lotes de 20 para evitar timeout em páginas com muitos posts.
        """
        if not node_ids:
            return {}

        result_urls: Dict[str, str] = {}
        batch_size = 20

        for i in range(0, len(node_ids), batch_size):
            batch = node_ids[i:i + batch_size]
            ids_param = ",".join(batch)
            url = f"{self.BASE_URL}/images/{file_key}"
            params = {
                "ids": ids_param,
                "format": img_format.lower(),
                "scale": scale,
            }
            try:
                resp = requests.get(url, headers=self.headers, params=params, timeout=90)
            except requests.RequestException as exc:
                raise FigmaError(f"Erro ao renderizar imagens no Figma: {exc}") from exc

            if resp.status_code != 200:
                raise FigmaError(f"Erro ao exportar imagens ({resp.status_code}): {resp.text}")

            body = resp.json()
            if body.get("err"):
                raise FigmaError(f"Erro retornado pelo Figma: {body['err']}")

            images = body.get("images", {})
            for nid, img_url in images.items():
                if img_url:
                    result_urls[nid] = img_url

        return result_urls

    @staticmethod
    def download_image_bytes(image_url: str) -> bytes:
        """Baixa os bytes da imagem renderizada pelo Figma."""
        try:
            resp = requests.get(image_url, timeout=60)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            raise FigmaError(f"Falha ao baixar imagem renderizada: {exc}") from exc

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Remove caracteres inválidos para nome de arquivo mantendo acentos e legibilidade."""
        cleaned = re.sub(r'[<>:"/\\|?*]', "-", name).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned or "Arte"
