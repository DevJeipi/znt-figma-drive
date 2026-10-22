import json
import os
import threading
import webbrowser
from tkinter import messagebox
from typing import Dict, List, Optional, Tuple

import customtkinter as ctk

from drive_client import DriveClient, DriveError, format_month_standard, normalize_str
from figma_client import FigmaClient, FigmaError


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "figma_token": "",
    "drive_base_folder": "[ZNT] Organização > Agência > 01 - Clientes ativos",
    "drive_subpath_template": "[Cliente] > 01 - Entregas > [Mês] > Artes",
    "export_format": "PNG",
    "export_scale": "2x (Alta Resolução)",
    "overwrite_existing": True,
    "group_by_post": True,
}

# Paleta de Cores em Tons de Azul Profissional
COLORS = {
    "bg_dark": "#0B132B",          # Fundo principal azul-noite profundo
    "panel_bg": "#121E3A",         # Fundo de painéis e cards
    "panel_border": "#1E3158",     # Borda sutil dos painéis
    "accent_blue": "#2563EB",      # Azul vibrante (CTA primário)
    "accent_hover": "#1D4ED8",     # Hover do azul vibrante
    "accent_light": "#38BDF8",     # Azul celeste (destaques e badges)
    "accent_subtle": "#1B2A4A",    # Azul suave para botões secundários
    "accent_subtle_hover": "#263B66",
    "group_header": "#17274B",     # Cabeçalhos de grupos de artes
    "group_header_border": "#284478",
    "text_main": "#F8FAFC",        # Texto branco suave
    "text_muted": "#94A3B8",       # Texto secundário azul-acinzentado
    "success_bg": "#0C2E38",       # Fundo badge de conectado
    "success_text": "#38BDF8",     # Texto badge de conectado
    "warning_bg": "#332211",       # Fundo badge pendente
    "warning_text": "#FBBF24",     # Texto badge pendente
    "banner_bg": "#0D2547",        # Banner informativo de modo
    "banner_border": "#0284C7",    # Borda do banner informativo
}


class FigmaToDriveApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("ZNT Agência — Sincronizador Figma para Google Drive")
        self.geometry("980x820")
        self.minsize(880, 720)
        self.configure(fg_color=COLORS["bg_dark"])

        self.config_data = self.load_config()
        self.drive_client = DriveClient(BASE_DIR)

        self.current_file_data: Optional[Dict] = None
        self.current_pages: List[Dict] = []
        self.frame_CheckVars: List[Tuple[ctk.BooleanVar, Dict]] = []
        self.last_uploaded_folder_url: Optional[str] = None
        self.settings_visible = False

        self._build_ui()
        self._refresh_connection_badges()

    def load_config(self) -> Dict:
        cfg = DEFAULT_CONFIG.copy()
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                cfg.update(saved)
            except Exception:
                pass
        return cfg

    def save_config(self) -> None:
        self.config_data["figma_token"] = self.figma_token_entry.get().strip()
        self.config_data["drive_base_folder"] = self.base_folder_entry.get().strip()
        self.config_data["drive_subpath_template"] = self.subpath_combo.get().strip()
        self.config_data["export_format"] = self.format_OptionMenu.get()
        self.config_data["export_scale"] = self.scale_OptionMenu.get()
        self.config_data["group_by_post"] = self.group_by_post_var.get()
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"Erro ao salvar config: {exc}")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # =========================================================================
        # 1. BARRA SUPERIOR (HEADER) COM IDENTIDADE E STATUS
        # =========================================================================
        header = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["panel_border"],
        )
        header.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")
        header.grid_columnconfigure(1, weight=1)

        # Título e Subtítulo
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=16, pady=10)

        main_title = ctk.CTkLabel(
            title_box,
            text="⚡ ZNT AGÊNCIA",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COLORS["text_main"],
        )
        main_title.pack(side="left", padx=(0, 10))

        sub_title = ctk.CTkLabel(
            title_box,
            text="• Sincronizador Figma ➔ Google Drive",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["accent_light"],
        )
        sub_title.pack(side="left")

        # Badges de Conexão e Botão de Configurações
        actions_box = ctk.CTkFrame(header, fg_color="transparent")
        actions_box.pack(side="right", padx=14, pady=10)

        self.figma_badge = ctk.CTkLabel(
            actions_box,
            text="● Figma",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS["accent_subtle"],
            text_color=COLORS["text_muted"],
            corner_radius=6,
            padx=10,
            pady=4,
        )
        self.figma_badge.pack(side="left", padx=(0, 6))

        self.drive_badge = ctk.CTkLabel(
            actions_box,
            text="● Google Drive",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS["accent_subtle"],
            text_color=COLORS["text_muted"],
            corner_radius=6,
            padx=10,
            pady=4,
        )
        self.drive_badge.pack(side="left", padx=(0, 10))

        self.toggle_settings_btn = ctk.CTkButton(
            actions_box,
            text="⚙️ Configurações",
            width=150,
            height=30,
            fg_color=COLORS["accent_subtle"],
            hover_color=COLORS["accent_subtle_hover"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_settings_panel,
        )
        self.toggle_settings_btn.pack(side="left")

        # =========================================================================
        # 2. PAINEL DE CONFIGURAÇÕES TÉCNICAS (RETRÁTIL)
        # =========================================================================
        self.cfg_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["panel_border"],
        )
        self.cfg_frame.grid_columnconfigure(1, weight=1)
        self.cfg_frame.grid_columnconfigure(3, weight=1)

        cfg_top = ctk.CTkFrame(self.cfg_frame, fg_color="transparent")
        cfg_top.grid(row=0, column=0, columnspan=5, padx=16, pady=(12, 8), sticky="ew")

        ctk.CTkLabel(
            cfg_top,
            text="⚙️  Configurações Técnicas e Acessos",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["accent_light"],
        ).pack(side="left")

        close_cfg_btn = ctk.CTkButton(
            cfg_top,
            text="✕ Fechar Configurações",
            width=165,
            height=28,
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_settings_panel,
        )
        close_cfg_btn.pack(side="right", padx=(8, 0))

        help_btn = ctk.CTkButton(
            cfg_top,
            text="❓ Guia de Configuração",
            width=155,
            height=28,
            fg_color=COLORS["accent_subtle"],
            hover_color=COLORS["accent_subtle_hover"],
            font=ctk.CTkFont(size=11),
            command=self._show_setup_guide,
        )
        help_btn.pack(side="right")

        # Linha 1: Token Figma e Conectar Drive
        ctk.CTkLabel(
            self.cfg_frame,
            text="Token Figma:",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
        ).grid(row=1, column=0, padx=(16, 6), pady=6, sticky="w")

        self.figma_token_entry = ctk.CTkEntry(
            self.cfg_frame,
            placeholder_text="figd_...",
            show="*",
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["panel_border"],
        )
        self.figma_token_entry.grid(row=1, column=1, padx=6, pady=6, sticky="ew")
        self.figma_token_entry.insert(0, self.config_data.get("figma_token", ""))

        ctk.CTkLabel(
            self.cfg_frame,
            text="Conta Drive:",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
        ).grid(row=1, column=2, padx=(16, 6), pady=6, sticky="w")

        self.drive_auth_btn = ctk.CTkButton(
            self.cfg_frame,
            text="Conectar Google Drive",
            width=180,
            height=30,
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_connect_drive,
        )
        self.drive_auth_btn.grid(row=1, column=3, columnspan=2, padx=(6, 16), pady=6, sticky="w")

        # Linha 2: Pasta Base e Subcaminho
        ctk.CTkLabel(
            self.cfg_frame,
            text="Pasta Base:",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
        ).grid(row=2, column=0, padx=(16, 6), pady=(6, 14), sticky="w")

        self.base_folder_entry = ctk.CTkEntry(
            self.cfg_frame,
            placeholder_text="[ZNT] Organização > Agência > 01 - Clientes ativos",
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["panel_border"],
        )
        self.base_folder_entry.grid(row=2, column=1, padx=6, pady=(6, 14), sticky="ew")
        self.base_folder_entry.insert(0, self.config_data.get("drive_base_folder", ""))

        ctk.CTkLabel(
            self.cfg_frame,
            text="Estrutura Padrão:",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
        ).grid(row=2, column=2, padx=(16, 6), pady=(6, 14), sticky="w")

        self.subpath_combo = ctk.CTkComboBox(
            self.cfg_frame,
            values=[
                "[Cliente] > 01 - Entregas > [Mês] > Artes",
                "[Cliente] > 01 - Entregas > [Mês] > Fotos > Artes",
            ],
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["panel_border"],
            button_color=COLORS["accent_subtle"],
            button_hover_color=COLORS["accent_subtle_hover"],
        )
        self.subpath_combo.grid(row=2, column=3, columnspan=2, padx=(6, 16), pady=(6, 14), sticky="ew")
        self.subpath_combo.set(self.config_data.get("drive_subpath_template", DEFAULT_CONFIG["drive_subpath_template"]))

        # =========================================================================
        # 3. PASSO 1: CARREGAR ARQUIVO DO FIGMA
        # =========================================================================
        step1_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["panel_border"],
        )
        step1_frame.grid(row=2, column=0, padx=16, pady=6, sticky="ew")
        step1_frame.grid_columnconfigure(1, weight=1)

        # Cabeçalho do Passo 1
        s1_header = ctk.CTkFrame(step1_frame, fg_color="transparent")
        s1_header.grid(row=0, column=0, columnspan=3, padx=16, pady=(10, 4), sticky="w")

        s1_tag = ctk.CTkLabel(
            s1_header,
            text="PASSO 1",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLORS["accent_blue"],
            text_color=COLORS["text_main"],
            corner_radius=6,
            padx=8,
            pady=2,
        )
        s1_tag.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            s1_header,
            text="Cole o link do Figma e clique em Carregar",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_main"],
        ).pack(side="left")

        # Campo do Link do Figma
        self.figma_url_entry = ctk.CTkEntry(
            step1_frame,
            placeholder_text="https://www.figma.com/design/XXXXX/Nome-do-Cliente-ou-Projeto...",
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["panel_border"],
        )
        self.figma_url_entry.grid(row=1, column=0, columnspan=2, padx=(16, 8), pady=(4, 12), sticky="ew")

        self.load_figma_btn = ctk.CTkButton(
            step1_frame,
            text="🔍 Carregar Projeto",
            height=36,
            width=175,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["accent_hover"],
            command=self._on_load_figma,
        )
        self.load_figma_btn.grid(row=1, column=2, padx=(0, 16), pady=(4, 12), sticky="e")

        # =========================================================================
        # 4. PASSO 2: DESTINO & CONFIGURAÇÃO DA ENTREGA
        # =========================================================================
        step2_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["panel_border"],
        )
        step2_frame.grid(row=3, column=0, padx=16, pady=6, sticky="ew")
        step2_frame.grid_columnconfigure(0, weight=1)
        step2_frame.grid_columnconfigure(1, weight=1)
        step2_frame.grid_columnconfigure(2, weight=1)

        # Cabeçalho do Passo 2
        s2_header = ctk.CTkFrame(step2_frame, fg_color="transparent")
        s2_header.grid(row=0, column=0, columnspan=3, padx=16, pady=(10, 6), sticky="w")

        s2_tag = ctk.CTkLabel(
            s2_header,
            text="PASSO 2",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLORS["accent_blue"],
            text_color=COLORS["text_main"],
            corner_radius=6,
            padx=8,
            pady=2,
        )
        s2_tag.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            s2_header,
            text="Confirme o Cliente, a Página e o Destino no Drive",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_main"],
        ).pack(side="left")

        # Coluna 1: Cliente
        col1 = ctk.CTkFrame(step2_frame, fg_color="transparent")
        col1.grid(row=1, column=0, padx=(16, 8), pady=(4, 8), sticky="nsew")
        col1.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            col1,
            text="Cliente no Drive:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))

        self.client_combo = ctk.CTkComboBox(
            col1,
            values=["Carregue o link do Figma..."],
            fg_color=COLORS["bg_dark"],
            border_color=COLORS["panel_border"],
            button_color=COLORS["accent_subtle"],
            button_hover_color=COLORS["accent_subtle_hover"],
        )
        self.client_combo.grid(row=1, column=0, sticky="ew", padx=(0, 6))

        self.fetch_clients_btn = ctk.CTkButton(
            col1,
            text="📁 Listar",
            width=65,
            height=28,
            fg_color=COLORS["accent_subtle"],
            hover_color=COLORS["accent_subtle_hover"],
            font=ctk.CTkFont(size=11),
            command=self._on_fetch_drive_clients,
        )
        self.fetch_clients_btn.grid(row=1, column=1)

        # Coluna 2: Página do Figma & Mês
        col2 = ctk.CTkFrame(step2_frame, fg_color="transparent")
        col2.grid(row=1, column=1, padx=8, pady=(4, 8), sticky="nsew")
        col2.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            col2,
            text="Página Selecionada:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 3))

        self.page_OptionMenu = ctk.CTkOptionMenu(
            col2,
            values=["Nenhuma página carregada"],
            fg_color=COLORS["bg_dark"],
            button_color=COLORS["accent_subtle"],
            button_hover_color=COLORS["accent_subtle_hover"],
            command=self._on_page_selected,
        )
        self.page_OptionMenu.grid(row=1, column=0, sticky="ew")

        # Coluna 3: Formato e Resolução
        col3 = ctk.CTkFrame(step2_frame, fg_color="transparent")
        col3.grid(row=1, column=2, padx=(8, 16), pady=(4, 8), sticky="nsew")
        col3.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            col3,
            text="Formato & Qualidade:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))

        export_box = ctk.CTkFrame(col3, fg_color="transparent")
        export_box.grid(row=1, column=0, sticky="ew")

        self.format_OptionMenu = ctk.CTkOptionMenu(
            export_box,
            values=["PNG", "JPG"],
            width=80,
            fg_color=COLORS["bg_dark"],
            button_color=COLORS["accent_subtle"],
            button_hover_color=COLORS["accent_subtle_hover"],
        )
        self.format_OptionMenu.pack(side="left", padx=(0, 6))
        self.format_OptionMenu.set(self.config_data.get("export_format", "PNG"))

        self.scale_OptionMenu = ctk.CTkOptionMenu(
            export_box,
            values=["2x (Alta Resolução)", "1x (Original)"],
            fg_color=COLORS["bg_dark"],
            button_color=COLORS["accent_subtle"],
            button_hover_color=COLORS["accent_subtle_hover"],
        )
        self.scale_OptionMenu.pack(side="left", fill="x", expand=True)
        self.scale_OptionMenu.set(self.config_data.get("export_scale", "2x (Alta Resolução)"))

        # Campo oculto para compatibilidade interna de mês
        self.month_entry = ctk.CTkEntry(step2_frame)
        self.month_entry.insert(0, "")

        # Banner Informativo de Modo (Mês ou ID Visual)
        self.mode_banner = ctk.CTkFrame(
            step2_frame,
            fg_color=COLORS["banner_bg"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["banner_border"],
        )
        self.mode_banner.grid(row=2, column=0, columnspan=3, padx=16, pady=(4, 12), sticky="ew")

        self.mode_banner_lbl = ctk.CTkLabel(
            self.mode_banner,
            text="ℹ️  Cole o link do Figma acima e clique em 'Carregar Projeto' para começar.",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["accent_light"],
            anchor="w",
        )
        self.mode_banner_lbl.pack(fill="x", padx=12, pady=7)

        # =========================================================================
        # 5. PASSO 3: ARTES ENCONTRADAS (LISTA COM CHECKBOXES)
        # =========================================================================
        cards_container = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["panel_border"],
        )
        cards_container.grid(row=4, column=0, padx=16, pady=6, sticky="nsew")
        cards_container.grid_columnconfigure(0, weight=1)
        cards_container.grid_rowconfigure(1, weight=1)

        # Barra Superior da Lista
        header_bar = ctk.CTkFrame(cards_container, fg_color="transparent")
        header_bar.grid(row=0, column=0, padx=16, pady=(10, 6), sticky="ew")

        s3_tag = ctk.CTkLabel(
            header_bar,
            text="PASSO 3",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=COLORS["accent_blue"],
            text_color=COLORS["text_main"],
            corner_radius=6,
            padx=8,
            pady=2,
        )
        s3_tag.pack(side="left", padx=(0, 8))

        self.cards_count_lbl = ctk.CTkLabel(
            header_bar,
            text="Artes Encontradas (0)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_main"],
        )
        self.cards_count_lbl.pack(side="left")

        # Opção de Separar em Subpastas
        self.group_by_post_var = ctk.BooleanVar(value=self.config_data.get("group_by_post", True))
        self.group_by_post_cb = ctk.CTkCheckBox(
            header_bar,
            text="Separar em pastas (Post 1 - NOME, Post 2...)",
            variable=self.group_by_post_var,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["accent_hover"],
        )
        self.group_by_post_cb.pack(side="left", padx=(20, 6))

        # Botões Rápidos de Seleção
        ctk.CTkButton(
            header_bar,
            text="Desmarcar Todas",
            width=115,
            height=28,
            fg_color=COLORS["accent_subtle"],
            hover_color=COLORS["accent_subtle_hover"],
            font=ctk.CTkFont(size=11),
            command=lambda: self._toggle_all_frames(False),
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            header_bar,
            text="Marcar Todas",
            width=105,
            height=28,
            fg_color=COLORS["accent_subtle"],
            hover_color=COLORS["accent_subtle_hover"],
            font=ctk.CTkFont(size=11),
            command=lambda: self._toggle_all_frames(True),
        ).pack(side="right")

        # Área de Rolagem das Artes
        self.scrollable_frames = ctk.CTkScrollableFrame(
            cards_container,
            fg_color=COLORS["bg_dark"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["panel_border"],
        )
        self.scrollable_frames.grid(row=1, column=0, padx=16, pady=(4, 14), sticky="nsew")
        self.scrollable_frames.grid_columnconfigure(0, weight=1)

        # Estado Inicial Vazio
        self._show_empty_frames_state()

        # =========================================================================
        # 6. RODAPÉ DE ENVIO & PROGRESSO
        # =========================================================================
        footer = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["panel_border"],
        )
        footer.grid(row=5, column=0, padx=16, pady=(6, 14), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        # Mensagem de Status e Barra de Progresso
        status_box = ctk.CTkFrame(footer, fg_color="transparent")
        status_box.grid(row=0, column=0, padx=16, pady=10, sticky="ew")
        status_box.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(
            status_box,
            text="● Pronto para começar.",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.status_lbl.grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.progress_bar = ctk.CTkProgressBar(
            status_box,
            fg_color=COLORS["bg_dark"],
            progress_color=COLORS["accent_light"],
            height=8,
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew")
        self.progress_bar.set(0)

        # Botões de Ação Final
        btn_bar = ctk.CTkFrame(footer, fg_color="transparent")
        btn_bar.grid(row=0, column=1, padx=16, pady=10, sticky="e")

        self.open_drive_btn = ctk.CTkButton(
            btn_bar,
            text="📂 Abrir no Drive",
            width=150,
            height=40,
            fg_color=COLORS["accent_subtle"],
            hover_color=COLORS["accent_subtle_hover"],
            font=ctk.CTkFont(size=12, weight="bold"),
            state="disabled",
            command=self._on_open_drive_folder,
        )
        self.open_drive_btn.pack(side="left", padx=(0, 10))

        self.upload_btn = ctk.CTkButton(
            btn_bar,
            text="🚀 2. Subir Artes para o Drive",
            width=230,
            height=40,
            fg_color=COLORS["accent_blue"],
            hover_color=COLORS["accent_hover"],
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_start_upload,
        )
        self.upload_btn.pack(side="left")

    # =========================================================================
    # LÓGICA DE UI E EVENTOS
    # =========================================================================

    def _toggle_settings_panel(self):
        """Expande ou recolhe o painel de configurações técnicas."""
        if self.settings_visible:
            self.cfg_frame.grid_forget()
            self.toggle_settings_btn.configure(
                text="⚙️ Configurações",
                fg_color=COLORS["accent_subtle"],
            )
            self.settings_visible = False
            self.save_config()
            self._refresh_connection_badges()
        else:
            self.cfg_frame.grid(row=1, column=0, padx=16, pady=(0, 6), sticky="ew")
            self.toggle_settings_btn.configure(
                text="✕ Fechar Configurações",
                fg_color=COLORS["accent_hover"],
            )
            self.settings_visible = True

    def _show_empty_frames_state(self):
        """Mostra mensagem amigável quando nenhuma arte foi carregada ainda."""
        for widget in self.scrollable_frames.winfo_children():
            widget.destroy()

        empty_box = ctk.CTkFrame(self.scrollable_frames, fg_color="transparent")
        empty_box.pack(pady=60)

        ctk.CTkLabel(
            empty_box,
            text="📋",
            font=ctk.CTkFont(size=36),
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            empty_box,
            text="Nenhuma arte carregada ainda",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLORS["text_main"],
        ).pack()

        ctk.CTkLabel(
            empty_box,
            text="Cole o link do arquivo do Figma no Passo 1 acima e clique em 'Carregar Projeto'.\nTodas as artes e carrosséis aparecerão organizados aqui.",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
            justify="center",
        ).pack(pady=(4, 0))

    def _refresh_connection_badges(self):
        """Atualiza os badges de conexão de Figma e Google Drive no cabeçalho."""
        token = self.config_data.get("figma_token", "").strip()
        if token:
            self.figma_badge.configure(
                text="● Figma Conectado",
                fg_color=COLORS["success_bg"],
                text_color=COLORS["success_text"],
            )
        else:
            self.figma_badge.configure(
                text="⚠️ Figma Sem Token",
                fg_color=COLORS["warning_bg"],
                text_color=COLORS["warning_text"],
            )

        if self.drive_client.is_authenticated():
            self.drive_badge.configure(
                text="● Drive Conectado",
                fg_color=COLORS["success_bg"],
                text_color=COLORS["success_text"],
            )
            self.drive_auth_btn.configure(text="Reconectar Drive")
        else:
            self.drive_badge.configure(
                text="⚠️ Drive Desconectado",
                fg_color=COLORS["warning_bg"],
                text_color=COLORS["warning_text"],
            )
            self.drive_auth_btn.configure(text="Conectar Google Drive")

    def _set_status(self, message: str, progress: Optional[float] = None):
        def _update():
            self.status_lbl.configure(text=f"● {message}")
            if progress is not None:
                self.progress_bar.set(progress)
        self.after(0, _update)

    def _on_connect_drive(self):
        self.save_config()

        def worker():
            try:
                self._set_status("Abrindo navegador para autorizar acesso ao Google Drive...", 0.2)
                self.drive_client.authenticate()
                self.after(0, self._refresh_connection_badges)
                self._set_status("Google Drive conectado com sucesso!", 1.0)
            except Exception as exc:
                self._set_status("Erro ao conectar ao Google Drive.", 0)
                self.after(0, lambda: messagebox.showerror("Erro Google Drive", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetch_drive_clients(self):
        self.save_config()
        base_setting = self.base_folder_entry.get().strip()

        def worker():
            try:
                self._set_status("Buscando pastas de clientes em '01 - Clientes ativos'...", 0.3)
                base_folder = self.drive_client.resolve_base_clients_folder(base_setting)
                subfolders = self.drive_client.list_subfolders(base_folder["id"])
                names = [f["name"] for f in subfolders]
                if not names:
                    self._set_status("Nenhuma pasta de cliente encontrada na pasta base.", 0)
                    return

                def update_combo():
                    current_val = self.client_combo.get().strip()
                    self.client_combo.configure(values=names)
                    matched = self._match_best_client_name(current_val, names)
                    if matched:
                        self.client_combo.set(matched)
                    elif not current_val:
                        self.client_combo.set(names[0])
                    self._refresh_connection_badges()

                self.after(0, update_combo)
                self._set_status(f"{len(names)} pastas de clientes carregadas do Google Drive!", 1.0)
            except Exception as exc:
                self._set_status("Falha ao listar clientes do Drive.", 0)
                self.after(0, lambda: messagebox.showerror("Erro ao listar pastas", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _match_best_client_name(project_name: str, folder_names: List[str]) -> Optional[str]:
        if not project_name or not folder_names:
            return None
        proj_norm = normalize_str(project_name)
        for name in folder_names:
            if normalize_str(name) == proj_norm:
                return name
        for name in folder_names:
            n_norm = normalize_str(name)
            if n_norm and (n_norm in proj_norm or proj_norm in n_norm):
                return name
        return None

    def _on_load_figma(self):
        self.save_config()
        token = self.figma_token_entry.get().strip()
        url = self.figma_url_entry.get().strip()

        if not token:
            self._toggle_settings_panel()
            messagebox.showwarning("Token Necessário", "Informe o seu Token do Figma no campo superior de Configurações.")
            return
        if not url:
            messagebox.showwarning("Link Necessário", "Cole o link do projeto do Figma no campo do Passo 1.")
            return

        self.load_figma_btn.configure(state="disabled", text="Carregando...")

        def worker():
            try:
                self._set_status("Lendo estrutura do arquivo no Figma...", 0.25)
                client = FigmaClient(token)
                file_key, target_node_id = client.parse_figma_url(url)
                file_data = client.get_file_structure(file_key)

                self.current_file_data = file_data
                self.current_pages = file_data.get("pages", [])

                def update_ui():
                    proj_name = file_data.get("project_name", "").strip().upper()
                    existing_vals = self.client_combo.cget("values")
                    matched = self._match_best_client_name(proj_name, existing_vals)
                    self.client_combo.set((matched or proj_name).upper())

                    if not self.current_pages:
                        self.page_OptionMenu.configure(values=["Nenhuma página encontrada"])
                        self.page_OptionMenu.set("Nenhuma página encontrada")
                        self._show_empty_frames_state()
                        return

                    page_names = [p["name"] for p in self.current_pages]
                    self.page_OptionMenu.configure(values=page_names)

                    # Seleciona a página alvo se houver node-id no link
                    selected_page = self.current_pages[0]
                    if target_node_id:
                        for p in self.current_pages:
                            if p["id"] == target_node_id:
                                selected_page = p
                                break

                    self.page_OptionMenu.set(selected_page["name"])
                    self._on_page_selected(selected_page["name"])

                self.after(0, update_ui)
                self._set_status(f"Projeto '{file_data.get('project_name')}' carregado com sucesso!", 1.0)
            except Exception as exc:
                self._set_status("Erro ao carregar projeto do Figma.", 0)
                self.after(0, lambda: messagebox.showerror("Erro Figma", str(exc)))
            finally:
                self.after(0, lambda: self.load_figma_btn.configure(state="normal", text="🔍 Carregar Projeto"))
                self.after(0, self._refresh_connection_badges)

        threading.Thread(target=worker, daemon=True).start()

    def _on_page_selected(self, page_name: str):
        is_id_visual = FigmaClient.is_id_visual_page(page_name)

        self.month_entry.delete(0, "end")
        if is_id_visual:
            self.month_entry.insert(0, "ID Visual (Sem Mês)")
            self.group_by_post_cb.configure(text="Separar em pastas (Destaques, Perfil, Banners)")
            self.mode_banner.configure(fg_color="#082A45", border_color="#0284C7")
            self.mode_banner_lbl.configure(
                text="🎨  MODO FORMATAÇÃO VISUAL ATIVO: As artes serão salvas na pasta 'ID Visual' do cliente (separadas automaticamente em Destaques, Perfil e Banners).",
                text_color="#38BDF8",
            )
        else:
            formatted_m = format_month_standard(page_name)
            self.month_entry.insert(0, formatted_m)
            self.group_by_post_cb.configure(text="Separar em pastas (Post 1 - NOME, Post 2...)")
            self.mode_banner.configure(fg_color="#0D2547", border_color="#1D4ED8")
            self.mode_banner_lbl.configure(
                text=f"📅  MODO POSTS MENSAIS ATIVO: As artes serão salvas na pasta '{formatted_m} > Artes' (organizadas por Post/Carrossel).",
                text_color="#93C5FD",
            )

        for page in self.current_pages:
            if page["name"] == page_name:
                self._populate_frames_list(page.get("frames", []))
                break

    def _populate_frames_list(self, frames: List[Dict]):
        for widget in self.scrollable_frames.winfo_children():
            widget.destroy()
        self.frame_CheckVars.clear()

        if not frames:
            self._show_empty_frames_state()
            return

        row_idx = 0
        current_post_folder = None

        icon_map = {
            "Perfil": "👤",
            "Destaques": "⭐",
            "Banners": "🖼️",
        }

        for frame in frames:
            post_folder = frame.get("post_folder_name", "Post 1")
            if post_folder != current_post_folder:
                current_post_folder = post_folder
                post_cards_count = sum(1 for f in frames if f.get("post_folder_name") == post_folder)

                group_header = ctk.CTkFrame(
                    self.scrollable_frames,
                    fg_color=COLORS["group_header"],
                    corner_radius=8,
                    border_width=1,
                    border_color=COLORS["group_header_border"],
                )
                group_header.grid(row=row_idx, column=0, padx=6, pady=(10, 3), sticky="ew")

                icon = icon_map.get(post_folder, "📁")
                hdr_text = f"{icon}  {post_folder}   •   {post_cards_count} card{'s' if post_cards_count > 1 else ''}"

                hdr_lbl = ctk.CTkLabel(
                    group_header,
                    text=hdr_text,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=COLORS["accent_light"],
                )
                hdr_lbl.pack(side="left", padx=12, pady=6)
                row_idx += 1

            var = ctk.BooleanVar(value=True)
            row_frame = ctk.CTkFrame(self.scrollable_frames, fg_color="transparent")
            row_frame.grid(row=row_idx, column=0, padx=(26, 8), pady=2, sticky="ew")

            sec_prefix = f"[{frame['section']}] " if frame.get("section") else ""
            dims = f"{frame['width']}×{frame['height']} px"

            cb = ctk.CTkCheckBox(
                row_frame,
                text=f"{sec_prefix}{frame['name']}",
                variable=var,
                font=ctk.CTkFont(size=12),
                fg_color=COLORS["accent_blue"],
                hover_color=COLORS["accent_hover"],
                command=self._update_selected_counter,
            )
            cb.pack(side="left", padx=(4, 8), pady=3)

            # Badge com Dimensões
            dims_lbl = ctk.CTkLabel(
                row_frame,
                text=dims,
                font=ctk.CTkFont(size=11),
                text_color=COLORS["text_muted"],
                fg_color=COLORS["panel_bg"],
                corner_radius=4,
                padx=6,
                pady=1,
            )
            dims_lbl.pack(side="left")

            self.frame_CheckVars.append((var, frame))
            row_idx += 1

        self._update_selected_counter()

    def _toggle_all_frames(self, state: bool):
        for var, _ in self.frame_CheckVars:
            var.set(state)
        self._update_selected_counter()

    def _update_selected_counter(self):
        total = len(self.frame_CheckVars)
        selected_frames = [f for v, f in self.frame_CheckVars if v.get()]
        selected = len(selected_frames)

        page_name = self.page_OptionMenu.get()
        if FigmaClient.is_id_visual_page(page_name):
            cats = [f.get("post_folder_name") for f in selected_frames if f.get("post_folder_name")]
            unique_cats = sorted(set(cats), key=lambda c: {"Perfil": 1, "Destaques": 2, "Banners": 3, "ID Visual": 4}.get(c, 9))
            cat_str = ", ".join(unique_cats) if unique_cats else "nenhum"
            self.cards_count_lbl.configure(
                text=f"Artes Encontradas ({selected}/{total} selecionadas: {cat_str})"
            )
        else:
            unique_posts = len({f.get("post_folder_name") for f in selected_frames})
            self.cards_count_lbl.configure(
                text=f"Artes Encontradas ({selected}/{total} selecionadas em {unique_posts} post{'s' if unique_posts != 1 else ''})"
            )

    def _on_open_drive_folder(self):
        if self.last_uploaded_folder_url:
            webbrowser.open(self.last_uploaded_folder_url)

    def _on_start_upload(self):
        self.save_config()

        if not self.current_file_data:
            messagebox.showwarning("Atenção", "Carregue primeiro um projeto do Figma no Passo 1.")
            return

        selected_frames = [f for var, f in self.frame_CheckVars if var.get()]
        if not selected_frames:
            messagebox.showwarning("Atenção", "Selecione pelo menos 1 arte para subir no Drive.")
            return

        page_name = self.page_OptionMenu.get().strip()
        is_id_visual = FigmaClient.is_id_visual_page(page_name)

        client_name = self.client_combo.get().strip()
        month_name = self.month_entry.get().strip()
        base_setting = self.base_folder_entry.get().strip()
        subpath_template = self.subpath_combo.get().strip()
        token = self.figma_token_entry.get().strip()
        group_by_post = self.group_by_post_var.get()

        if not client_name:
            messagebox.showwarning("Atenção", "Informe o nome do Cliente no Passo 2.")
            return
        if not is_id_visual and not month_name:
            messagebox.showwarning("Atenção", "Informe o Mês da entrega no Passo 2.")
            return

        img_format = self.format_OptionMenu.get().lower()
        scale = 2.0 if "2x" in self.scale_OptionMenu.get() else 1.0
        mime_type = "image/png" if img_format == "png" else "image/jpeg"
        ext = ".png" if img_format == "png" else ".jpg"

        self.upload_btn.configure(state="disabled", text="Enviando...")
        self.open_drive_btn.configure(state="disabled")

        def worker():
            try:
                # Passo 1: Localizar / Criar pastas no Google Drive
                self._set_status("Localizando estrutura de pastas no Google Drive...", 0.1)
                base_folder = self.drive_client.resolve_base_clients_folder(base_setting)

                if is_id_visual:
                    target_folder, resolved_steps = self.drive_client.resolve_or_create_id_visual_path(
                        clients_base_folder_id=base_folder["id"],
                        client_name=client_name,
                    )
                else:
                    target_folder, resolved_steps = self.drive_client.resolve_or_create_target_path(
                        clients_base_folder_id=base_folder["id"],
                        client_name=client_name,
                        month_name=month_name,
                        subpath_template=subpath_template,
                    )
                self.last_uploaded_folder_url = target_folder.get("webViewLink")
                path_str = " > ".join(resolved_steps)

                # Passo 2: Renderização em Alta Resolução no Figma
                total = len(selected_frames)
                self._set_status(f"Renderizando {total} arte(s) no Figma em alta resolução...", 0.25)
                figma = FigmaClient(token)
                file_key = self.current_file_data["file_key"]
                node_ids = [f["id"] for f in selected_frames]

                def on_render_progress(b_idx, total_b, b_len):
                    prog = 0.25 + (0.2 * (b_idx / total_b))
                    self._set_status(f"Renderizando lote {b_idx}/{total_b} no Figma ({b_len} artes)...", prog)

                image_urls = figma.get_image_urls(
                    file_key=file_key,
                    node_ids=node_ids,
                    img_format=img_format,
                    scale=scale,
                    batch_size=5,
                    progress_callback=on_render_progress,
                )

                # Passo 3: Baixar e Enviar para as subpastas
                used_filenames_per_folder: Dict[str, Dict[str, int]] = {}
                subfolders_cache: Dict[str, str] = {}
                uploaded_count = 0

                for i, frame in enumerate(selected_frames, start=1):
                    nid = frame["id"]
                    img_url = image_urls.get(nid)
                    if not img_url:
                        continue

                    dest_folder_id = target_folder["id"]
                    subfolder_label = ""

                    if is_id_visual:
                        category_folder = frame.get("post_folder_name", "ID Visual")
                        if category_folder in ("Destaques", "Perfil", "Banners"):
                            subfolder_label = f" > {category_folder}"
                            if category_folder not in subfolders_cache:
                                sub = self.drive_client.get_or_create_subfolder(
                                    parent_id=target_folder["id"],
                                    folder_name=category_folder,
                                )
                                subfolders_cache[category_folder] = sub["id"]
                            dest_folder_id = subfolders_cache[category_folder]
                        else:
                            dest_folder_id = target_folder["id"]
                    else:
                        if group_by_post:
                            post_folder_name = frame.get("post_folder_name") or "Post 1"
                            subfolder_label = f" > {post_folder_name}"
                            if post_folder_name not in subfolders_cache:
                                sub = self.drive_client.get_or_create_subfolder(
                                    parent_id=target_folder["id"],
                                    folder_name=post_folder_name,
                                )
                                subfolders_cache[post_folder_name] = sub["id"]
                            dest_folder_id = subfolders_cache[post_folder_name]

                    folder_used = used_filenames_per_folder.setdefault(dest_folder_id, {})
                    base_name = figma.sanitize_filename(frame["name"])
                    count = folder_used.get(base_name.lower(), 0) + 1
                    folder_used[base_name.lower()] = count
                    final_filename = f"{base_name}{ext}" if count == 1 else f"{base_name} ({count}){ext}"

                    progress = 0.25 + (0.75 * (i / total))
                    self._set_status(
                        f"[{i}/{total}] Subindo '{final_filename}' em {path_str}{subfolder_label}...",
                        progress,
                    )

                    img_bytes = figma.download_image_bytes(img_url)
                    self.drive_client.upload_image_bytes(
                        folder_id=dest_folder_id,
                        filename=final_filename,
                        image_bytes=img_bytes,
                        mime_type=mime_type,
                        overwrite_existing=True,
                    )
                    uploaded_count += 1

                if is_id_visual:
                    folders_created_msg = f" em {len(subfolders_cache)} pasta(s) (Destaques/Perfil/Banners)"
                else:
                    folders_created_msg = f" em {len(subfolders_cache)} pasta(s) de Post" if group_by_post else ""

                self._set_status(
                    f"Concluído com sucesso! {uploaded_count} arte(s) enviada(s){folders_created_msg} para: {path_str}",
                    1.0,
                )
                self.after(0, lambda: self.open_drive_btn.configure(state="normal"))

                success_title = "Upload de ID Visual Concluído!" if is_id_visual else "Upload Concluído!"
                success_msg = (
                    f"{uploaded_count} arte(s) de ID Visual foram salvas com sucesso no Drive{folders_created_msg}!\n\n"
                    f"Caminho:\n{base_folder['name']} > {path_str}"
                    if is_id_visual else
                    f"{uploaded_count} arte(s) foram salvas com sucesso no Drive{folders_created_msg}!\n\n"
                    f"Caminho:\n{base_folder['name']} > {path_str}"
                )
                self.after(
                    0,
                    lambda: messagebox.showinfo(success_title, success_msg),
                )
            except Exception as exc:
                self._set_status("Erro durante o envio.", 0)
                self.after(0, lambda: messagebox.showerror("Erro durante o envio", str(exc)))
            finally:
                self.after(
                    0,
                    lambda: self.upload_btn.configure(state="normal", text="🚀 2. Subir Artes para o Drive"),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _show_setup_guide(self):
        guide = (
            "PASSO 1 — GERAR TOKEN DO FIGMA (1 minuto):\n"
            "1. No Figma, clique no seu perfil (canto superior esquerdo) > Settings.\n"
            "2. Aba 'Security' > role até 'Personal access tokens'.\n"
            "3. Clique em 'Generate new token', dê um nome e copie o código 'figd_...'.\n"
            "4. Cole no campo 'Token Figma' deste aplicativo.\n\n"
            "PASSO 2 — CREDENCIAL DO GOOGLE DRIVE:\n"
            "1. Acesse: https://console.cloud.google.com/\n"
            "2. Crie um projeto > Menu 'APIs e Serviços' > 'Biblioteca' > Ative a 'Google Drive API'.\n"
            "3. Em 'Tela de permissão OAuth', adicione seu e-mail em 'Usuários de teste'.\n"
            "4. Em 'Credenciais' > '+ Criar Credenciais' > 'ID do cliente OAuth' > Tipo: 'App para computador' (Desktop App).\n"
            "5. Baixe o JSON, renomeie para 'credentials.json' e coloque na pasta do aplicativo:\n"
            f"   {BASE_DIR}\n"
            "6. Clique em 'Conectar Google Drive' e autorize no navegador!"
        )
        messagebox.showinfo("Guia de Configuração (ZNT Agência)", guide)


if __name__ == "__main__":
    app = FigmaToDriveApp()
    app.mainloop()
