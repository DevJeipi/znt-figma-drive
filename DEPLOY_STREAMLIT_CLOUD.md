# Como Publicar o Exportador da ZNT na Nuvem (Streamlit Cloud)

Este guia ensina como colocar o sistema no ar para que qualquer pessoa da agência possa acessar através de um link no navegador (Chrome, Edge, Safari, Mac ou Windows), sem precisar instalar nada!

---

## 1. Testar no seu computador primeiro

Para ver como ficou a versão web rodando agora na sua máquina:
1. Dê dois cliques em [`Iniciar_Web_Local.bat`](file:///C:/Users/joaoh/.gemini/antigravity/scratch/figma-to-drive/Iniciar_Web_Local.bat).
2. Ele abrirá automaticamente o navegador em `http://localhost:8501`.

---

## 2. Publicar na Nuvem (Gratuito e Permanente)

### Passo A — Criar o Repositório no GitHub
1. Acesse [github.com](https://github.com/) e crie um novo repositório (ex: `znt-figma-drive`).
   * Pode marcar como **Privado** ou **Público**.
2. Suba os arquivos desta pasta para o repositório:
   * `web_app.py`
   * `figma_client.py`
   * `drive_client.py`
   * `requirements.txt`
   * `.streamlit/config.toml`
   * `.gitignore`
   *(Observação: o arquivo `.gitignore` já garante que suas senhas e tokens não sobem publicamente).*

### Passo B — Conectar no Streamlit Cloud
1. Acesse [share.streamlit.io](https://share.streamlit.io/) e faça login com seu GitHub.
2. Clique no botão **"New app"**.
3. Selecione o repositório `znt-figma-drive`.
4. Em **Main file path**, digite: `web_app.py`.
5. Em **App URL**, você pode personalizar o link da agência (ex: `znt-exportador.streamlit.app`).

### Passo C — Colocar os Segredos (Secrets)
1. Antes ou logo após o app iniciar, clique em **Advanced settings > Secrets** (ou vá no menu do app em `Settings > Secrets`).
2. Abra o arquivo local [`.streamlit/secrets.toml`](file:///C:/Users/joaoh/.gemini/antigravity/scratch/figma-to-drive/.streamlit/secrets.toml) no Bloco de Notas, copie todo o texto e cole dentro da caixa de Secrets no Streamlit Cloud.
3. Clique em **Save**.

---

## Pronto! 🎉
O aplicativo reiniciará em segundos com seu link oficial (ex: `https://znt-exportador.streamlit.app`).

Agora qualquer pessoa da sua agência só precisa:
1. Abrir o link no navegador.
2. Colar o link do Figma e clicar em **"Subir Artes para o Google Drive"**.
3. Nenhum funcionário precisa configurar token, nem logar no Google Cloud!
