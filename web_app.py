import json
import os
from typing import Dict, List, Optional

import streamlit as st

from drive_client import DriveClient, DriveError, format_month_standard, normalize_str
from figma_client import FigmaClient, FigmaError


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_local_config() -> Dict:
    cfg = {
        "figma_token": "",
        "drive_base_folder": "[ZNT] Organização > Agência > 01 - Clientes ativos",
        "drive_subpath_template": "[Cliente] > 01 - Entregas > [Mês] > Artes",
        "export_format": "PNG",
        "export_scale": "2x (Alta Resolução)",
        "overwrite_existing": True,
        "group_by_post": True,
    }
    # Tenta ler de st.secrets primeiro (quando estiver no Streamlit Cloud)
    try:
        if hasattr(st, "secrets"):
            if "FIGMA_TOKEN" in st.secrets:
                cfg["figma_token"] = st.secrets["FIGMA_TOKEN"]
            if "DRIVE_BASE_FOLDER" in st.secrets:
                cfg["drive_base_folder"] = st.secrets["DRIVE_BASE_FOLDER"]
            if "DRIVE_SUBPATH_TEMPLATE" in st.secrets:
                cfg["drive_subpath_template"] = st.secrets["DRIVE_SUBPATH_TEMPLATE"]
    except Exception:
        pass

    # Se não achou em secrets ou está local, lê do config.json
    if not cfg["figma_token"] and os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg.update(saved)
        except Exception:
            pass
    return cfg


# Configuração inicial da página
st.set_page_config(
    page_title="ZNT Agência — Figma ➔ Google Drive",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Estilização Moderna em Tons de Azul
st.markdown(
    """
    <style>
    /* Estilos globais em tons de azul */
    .stApp {
        background-color: #0B132B;
        color: #F8FAFC;
    }
    
    /* Header estilizado */
    .znt-header {
        background: linear-gradient(135deg, #121E3A 0%, #17274B 100%);
        padding: 18px 24px;
        border-radius: 12px;
        border: 1px solid #1E3158;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 20px;
    }
    .znt-title {
        font-size: 22px;
        font-weight: 800;
        color: #FFFFFF;
        letter-spacing: 0.5px;
    }
    .znt-subtitle {
        font-size: 14px;
        color: #38BDF8;
        font-weight: 500;
    }
    
    /* Badge de status */
    .badge-pill {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
    }
    .badge-connected {
        background-color: #0C2E38;
        color: #38BDF8;
        border: 1px solid #0284C7;
    }
    .badge-pending {
        background-color: #332211;
        color: #FBBF24;
        border: 1px solid #D97706;
    }
    
    /* Cards de Passos */
    .step-card {
        background-color: #121E3A;
        border-radius: 12px;
        border: 1px solid #1E3158;
        padding: 20px;
        margin-bottom: 16px;
    }
    .step-tag {
        background-color: #2563EB;
        color: white;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 800;
        text-transform: uppercase;
        margin-right: 8px;
    }
    .step-title {
        font-size: 16px;
        font-weight: 700;
        color: #F8FAFC;
        display: inline;
    }
    
    /* Banners informativos */
    .info-banner-id {
        background-color: #082A45;
        border: 1px solid #0284C7;
        color: #38BDF8;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        margin-top: 10px;
    }
    .info-banner-month {
        background-color: #0D2547;
        border: 1px solid #1D4ED8;
        color: #93C5FD;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 600;
        margin-top: 10px;
    }
    
    /* Grupo de artes */
    .group-header {
        background-color: #17274B;
        border: 1px solid #284478;
        color: #38BDF8;
        padding: 8px 14px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 700;
        margin-top: 14px;
        margin-bottom: 8px;
    }
    
    /* Botão primário customizado */
    div.stButton > button[kind="primary"] {
        background-color: #2563EB;
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        font-weight: 700;
        padding: 10px 20px;
        transition: all 0.2s;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #1D4ED8;
        border: none;
        color: #FFFFFF;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Inicialização do estado de sessão
if "config" not in st.session_state:
    st.session_state.config = load_local_config()

if "drive_client" not in st.session_state:
    st.session_state.drive_client = DriveClient(BASE_DIR)

if "file_data" not in st.session_state:
    st.session_state.file_data = None

if "selected_page" not in st.session_state:
    st.session_state.selected_page = None

if "selected_frames_map" not in st.session_state:
    st.session_state.selected_frames_map = {}

if "client_folders_cache" not in st.session_state:
    st.session_state.client_folders_cache = []

# Status de Conexões
drive_ready = st.session_state.drive_client.is_authenticated()
figma_ready = bool(st.session_state.config.get("figma_token", "").strip())

# Barra de Cabeçalho Superior
drive_badge_class = "badge-connected" if drive_ready else "badge-pending"
drive_badge_text = "● Google Drive Conectado" if drive_ready else "⚠️ Drive Desconectado"

figma_badge_class = "badge-connected" if figma_ready else "badge-pending"
figma_badge_text = "● Figma Conectado" if figma_ready else "⚠️ Figma Sem Token"

st.markdown(
    f"""
    <div class="znt-header">
        <div>
            <div class="znt-title">⚡ ZNT AGÊNCIA</div>
            <div class="znt-subtitle">Sincronizador Automático Figma ➔ Google Drive</div>
        </div>
        <div>
            <span class="badge-pill {figma_badge_class}">{figma_badge_text}</span>
            &nbsp;
            <span class="badge-pill {drive_badge_class}">{drive_badge_text}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# BARRA LATERAL (CONFIGURAÇÕES TÉCNICAS)
# =============================================================================
with st.sidebar:
    st.markdown("### ⚙️ Configurações da Agência")
    st.caption("Ajuste as chaves de acesso e pastas padrão caso necessário.")

    token_input = st.text_input(
        "Token do Figma:",
        value=st.session_state.config.get("figma_token", ""),
        type="password",
        help="Personal Access Token gerado no Figma.",
    )
    if token_input != st.session_state.config.get("figma_token", ""):
        st.session_state.config["figma_token"] = token_input.strip()

    base_folder_input = st.text_input(
        "Pasta Base no Drive:",
        value=st.session_state.config.get("drive_base_folder", ""),
        help="Caminho até a pasta de clientes ativos no Drive.",
    )
    if base_folder_input != st.session_state.config.get("drive_base_folder", ""):
        st.session_state.config["drive_base_folder"] = base_folder_input.strip()

    subpath_input = st.selectbox(
        "Estrutura Padrão:",
        [
            "[Cliente] > 01 - Entregas > [Mês] > Artes",
            "[Cliente] > 01 - Entregas > [Mês] > Fotos > Artes",
        ],
        index=0 if "Fotos" not in st.session_state.config.get("drive_subpath_template", "") else 1,
    )
    st.session_state.config["drive_subpath_template"] = subpath_input

    st.markdown("---")
    st.markdown(
        """
        **💡 Como funciona para a equipe:**
        1. Cole o link da página do Figma no Passo 1.
        2. O sistema detecta o cliente e a página automaticamente.
        3. Para **Formatação Visual**, salva direto em `ID Visual`.
        4. Para **Posts Mensais**, salva no mês organizado por Post.
        """
    )

# =============================================================================
# PASSO 1: CARREGAR PROJETO DO FIGMA
# =============================================================================
st.markdown(
    """
    <div class="step-card">
        <span class="step-tag">PASSO 1</span>
        <div class="step-title">Link do Arquivo no Figma</div>
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2 = st.columns([5, 1])
with c1:
    figma_url = st.text_input(
        "URL do Figma",
        placeholder="https://www.figma.com/design/XXXXX/Nome-do-Cliente...",
        label_visibility="collapsed",
    )
with c2:
    load_btn = st.button("🔍 Carregar", use_container_width=True, type="primary")

if load_btn and figma_url:
    token = st.session_state.config.get("figma_token", "").strip()
    if not token:
        st.error("⚠️ Token do Figma não configurado! Insira o token na barra lateral esquerda.")
    else:
        with st.spinner("Lendo estrutura do arquivo no Figma..."):
            try:
                figma = FigmaClient(token)
                file_key, target_node_id = figma.parse_figma_url(figma_url)
                file_data = figma.get_file_structure(file_key)
                st.session_state.file_data = file_data

                pages = file_data.get("pages", [])
                if pages:
                    selected = pages[0]["name"]
                    if target_node_id:
                        for p in pages:
                            if p["id"] == target_node_id:
                                selected = p["name"]
                                break
                    st.session_state.selected_page = selected
                st.success(f"Projeto '{file_data.get('project_name')}' carregado com sucesso!")
            except Exception as e:
                st.error(f"Erro ao carregar do Figma: {e}")

# =============================================================================
# PASSO 2: DESTINO & CONFIGURAÇÃO DA ENTREGA
# =============================================================================
if st.session_state.file_data:
    file_data = st.session_state.file_data
    pages = file_data.get("pages", [])
    page_names = [p["name"] for p in pages]

    st.markdown(
        """
        <div class="step-card">
            <span class="step-tag">PASSO 2</span>
            <div class="step-title">Destino & Organização no Google Drive</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_client, col_page, col_export = st.columns([2, 2, 2])

    with col_client:
        default_client_name = file_data.get("project_name", "").strip().upper()
        client_name = st.text_input(
            "Cliente no Drive:",
            value=default_client_name,
            help="Nome da pasta do cliente dentro de 01 - Clientes ativos.",
        )

    with col_page:
        current_page_idx = 0
        if st.session_state.selected_page in page_names:
            current_page_idx = page_names.index(st.session_state.selected_page)

        selected_page_name = st.selectbox(
            "Página do Figma:",
            page_names,
            index=current_page_idx,
        )
        st.session_state.selected_page = selected_page_name

    with col_export:
        c_fmt, c_scale = st.columns(2)
        with c_fmt:
            img_format = st.selectbox("Formato:", ["PNG", "JPG"], index=0)
        with c_scale:
            scale_choice = st.selectbox("Qualidade:", ["2x (Alta)", "1x (Normal)"], index=0)
            scale = 2.0 if "2x" in scale_choice else 1.0

    # Detecção inteligente do modo
    is_id_visual = FigmaClient.is_id_visual_page(selected_page_name)

    if is_id_visual:
        st.markdown(
            """
            <div class="info-banner-id">
                🎨 <b>MODO FORMATAÇÃO VISUAL ATIVO:</b> As artes serão salvas na pasta <b>ID Visual</b> do cliente dentro de <i>01 - Entregas</i> (separadas automaticamente em <b>Destaques</b>, <b>Perfil</b> e <b>Banners</b>).
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        formatted_m = format_month_standard(selected_page_name)
        st.markdown(
            f"""
            <div class="info-banner-month">
                📅 <b>MODO POSTS MENSAIS ATIVO:</b> As artes serão salvas na pasta <b>{formatted_m} &gt; Artes</b> (organizadas por Post/Carrossel).
            </div>
            """,
            unsafe_allow_html=True,
        )

    # =========================================================================
    # PASSO 3: SELEÇÃO DAS ARTES
    # =========================================================================
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="step-card">
            <span class="step-tag">PASSO 3</span>
            <div class="step-title">Artes & Cards Encontrados</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Encontra os frames da página selecionada
    active_page = next((p for p in pages if p["name"] == selected_page_name), None)
    frames = active_page.get("frames", []) if active_page else []

    if not frames:
        st.info("Nenhum frame ou card encontrado nesta página.")
    else:
        # Ações em lote
        action_c1, action_c2, action_c3 = st.columns([2, 1, 1])
        with action_c1:
            group_subfolders = st.checkbox(
                "Separar em subpastas de Post/Categoria",
                value=True,
                help="Cria subpastas para cada post ou categoria no Drive.",
            )
        with action_c2:
            if st.button("Marcar Todas", use_container_width=True):
                for f in frames:
                    st.session_state.selected_frames_map[f["id"]] = True
                st.rerun()
        with action_c3:
            if st.button("Desmarcar Todas", use_container_width=True):
                for f in frames:
                    st.session_state.selected_frames_map[f["id"]] = False
                st.rerun()

        # Renderização visual dos cards agrupados
        current_folder = None
        icon_map = {"Perfil": "👤", "Destaques": "⭐", "Banners": "🖼️"}

        for frame in frames:
            post_folder = frame.get("post_folder_name", "Post 1")
            if post_folder != current_folder:
                current_folder = post_folder
                count_in_group = sum(1 for f in frames if f.get("post_folder_name") == post_folder)
                icon = icon_map.get(post_folder, "📁")
                st.markdown(
                    f'<div class="group-header">{icon} {post_folder} • {count_in_group} card(s)</div>',
                    unsafe_allow_html=True,
                )

            fid = frame["id"]
            if fid not in st.session_state.selected_frames_map:
                st.session_state.selected_frames_map[fid] = True

            sec_prefix = f"[{frame['section']}] " if frame.get("section") else ""
            dims = f"{frame['width']}×{frame['height']} px"

            card_col1, card_col2 = st.columns([5, 1])
            with card_col1:
                checked = st.checkbox(
                    f"{sec_prefix}{frame['name']}",
                    value=st.session_state.selected_frames_map[fid],
                    key=f"chk_{fid}",
                )
                st.session_state.selected_frames_map[fid] = checked
            with card_col2:
                st.caption(f"`{dims}`")

        # Selecionados
        selected_frames = [f for f in frames if st.session_state.selected_frames_map.get(f["id"], False)]
        st.markdown(f"**Total selecionado:** {len(selected_frames)} de {len(frames)} arte(s).")

        # =========================================================================
        # BOTÃO DE ENVIO & PROCESSAMENTO
        # =========================================================================
        st.markdown("<br>", unsafe_allow_html=True)
        upload_btn = st.button(
            "🚀 Subir Artes para o Google Drive",
            type="primary",
            use_container_width=True,
            disabled=len(selected_frames) == 0,
        )

        if upload_btn and selected_frames:
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                base_setting = st.session_state.config.get("drive_base_folder", "")
                subpath_template = st.session_state.config.get("drive_subpath_template", "")
                token = st.session_state.config.get("figma_token", "").strip()

                # Passo 1: Localizar pastas no Drive
                status_text.info("Localizando estrutura de pastas no Google Drive...")
                progress_bar.progress(10)

                drive = st.session_state.drive_client
                base_folder = drive.resolve_base_clients_folder(base_setting)

                if is_id_visual:
                    target_folder, resolved_steps = drive.resolve_or_create_id_visual_path(
                        clients_base_folder_id=base_folder["id"],
                        client_name=client_name,
                    )
                else:
                    month_name = format_month_standard(selected_page_name)
                    target_folder, resolved_steps = drive.resolve_or_create_target_path(
                        clients_base_folder_id=base_folder["id"],
                        client_name=client_name,
                        month_name=month_name,
                        subpath_template=subpath_template,
                    )

                path_str = " > ".join(resolved_steps)

                # Passo 2: Renderização das imagens no Figma
                total = len(selected_frames)
                status_text.info(f"Renderizando {total} arte(s) no Figma em alta resolução...")
                progress_bar.progress(25)

                figma = FigmaClient(token)
                file_key = file_data["file_key"]
                node_ids = [f["id"] for f in selected_frames]
                image_urls = figma.get_image_urls(
                    file_key=file_key,
                    node_ids=node_ids,
                    img_format=img_format.lower(),
                    scale=scale,
                )

                # Passo 3: Envio de cada imagem
                subfolders_cache: Dict[str, str] = {}
                used_filenames: Dict[str, Dict[str, int]] = {}
                uploaded_count = 0
                ext = ".png" if img_format.lower() == "png" else ".jpg"
                mime = "image/png" if img_format.lower() == "png" else "image/jpeg"

                for i, frame in enumerate(selected_frames, start=1):
                    nid = frame["id"]
                    img_url = image_urls.get(nid)
                    if not img_url:
                        continue

                    dest_folder_id = target_folder["id"]
                    sub_label = ""

                    if is_id_visual:
                        cat_folder = frame.get("post_folder_name", "ID Visual")
                        if cat_folder in ("Destaques", "Perfil", "Banners"):
                            sub_label = f" > {cat_folder}"
                            if cat_folder not in subfolders_cache:
                                sub = drive.get_or_create_subfolder(
                                    parent_id=target_folder["id"],
                                    folder_name=cat_folder,
                                )
                                subfolders_cache[cat_folder] = sub["id"]
                            dest_folder_id = subfolders_cache[cat_folder]
                    elif group_subfolders:
                        post_folder = frame.get("post_folder_name", "Post 1")
                        sub_label = f" > {post_folder}"
                        if post_folder not in subfolders_cache:
                            sub = drive.get_or_create_subfolder(
                                parent_id=target_folder["id"],
                                folder_name=post_folder,
                            )
                            subfolders_cache[post_folder] = sub["id"]
                        dest_folder_id = subfolders_cache[post_folder]

                    folder_used = used_filenames.setdefault(dest_folder_id, {})
                    base_name = figma.sanitize_filename(frame["name"])
                    count = folder_used.get(base_name.lower(), 0) + 1
                    folder_used[base_name.lower()] = count
                    final_filename = f"{base_name}{ext}" if count == 1 else f"{base_name} ({count}){ext}"

                    cur_progress = int(25 + (75 * (i / total)))
                    progress_bar.progress(cur_progress)
                    status_text.info(f"[{i}/{total}] Subindo '{final_filename}' em {path_str}{sub_label}...")

                    img_bytes = figma.download_image_bytes(img_url)
                    drive.upload_image_bytes(
                        folder_id=dest_folder_id,
                        filename=final_filename,
                        image_bytes=img_bytes,
                        mime_type=mime,
                        overwrite_existing=True,
                    )
                    uploaded_count += 1

                progress_bar.progress(100)
                status_text.empty()
                st.balloons()
                st.success(
                    f"🎉 **Sucesso!** {uploaded_count} arte(s) foram enviadas para o Google Drive!\n\n"
                    f"📁 **Caminho:** `{base_folder['name']} > {path_str}`"
                )

                folder_link = target_folder.get("webViewLink")
                if folder_link:
                    st.link_button("📂 Abrir Pasta no Google Drive", folder_link, type="primary")

            except Exception as e:
                status_text.empty()
                st.error(f"Erro durante o envio: {e}")
