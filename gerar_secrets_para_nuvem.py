import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
OUTPUT_SECRETS_PATH = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")

def generate_secrets():
    os.makedirs(os.path.join(BASE_DIR, ".streamlit"), exist_ok=True)
    
    figma_token = ""
    drive_base = "[ZNT] Organização > Agência > 01 - Clientes ativos"
    drive_subpath = "[Cliente] > 01 - Entregas > [Mês] > Artes"

    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            figma_token = cfg.get("figma_token", "")
            drive_base = cfg.get("drive_base_folder", drive_base)
            drive_subpath = cfg.get("drive_subpath_template", drive_subpath)

    token_data = {}
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            token_data = json.load(f)

    lines = []
    lines.append(f'FIGMA_TOKEN = "{figma_token}"')
    lines.append(f'DRIVE_BASE_FOLDER = "{drive_base}"')
    lines.append(f'DRIVE_SUBPATH_TEMPLATE = "{drive_subpath}"')
    lines.append("")
    lines.append("[google_token]")
    for k, v in token_data.items():
        if isinstance(v, list):
            scopes_formatted = json.dumps(v)
            lines.append(f'{k} = {scopes_formatted}')
        elif isinstance(v, str):
            lines.append(f'{k} = "{v}"')
        else:
            lines.append(f'{k} = {v}')

    content = "\n".join(lines)
    with open(OUTPUT_SECRETS_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("Arquivo de segredos gerado com sucesso em:")
    print(OUTPUT_SECRETS_PATH)

if __name__ == "__main__":
    generate_secrets()
