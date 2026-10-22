# Exportador Figma -> Google Drive (ZNT Organização)

Ferramenta visual em Python que lê o projeto do Figma, identifica o **Cliente**, o **Mês** (ou **Formatação Visual**) e os **Cards/Posts**, exporta em alta resolução e envia direto para o Google Drive seguindo o padrão da agência.

---

## Estrutura de Pastas Suportada no Drive

### 1. Posts Mensais
`[ZNT] Organização > Agência > 01 - Clientes ativos > [CLIENTE] > 01 - Entregas > [Mês] > Artes > [Post X - NOME]`

### 2. Formatação Visual (Página "Formatação Visual" / "ID Visual")
Não usa pasta de mês! Salva direto em:
`[ZNT] Organização > Agência > 01 - Clientes ativos > [CLIENTE] > 01 - Entregas > ID Visual`
- Cards com `DESTAQUE` no nome ➔ Subpasta **`Destaques`**
- Cards com `PERFIL` no nome ➔ Subpasta **`Perfil`**
- Cards com `BANNER` no nome ➔ Subpasta **`Banners`**
- Outros cards ➔ Salvos diretamente na pasta **`ID Visual`**

---

## Como Iniciar

Basta dar **dois cliques** no arquivo [`Iniciar_Exportador.bat`](file:///C:/Users/joaoh/.gemini/antigravity/scratch/figma-to-drive/Iniciar_Exportador.bat).

---

## Configuração Inicial (Apenas na 1ª vez)

### 1. Gerar o Token do Figma (1 minuto)
1. Abra o Figma e clique no seu perfil (canto superior esquerdo) > **Settings**.
2. Vá na aba **Security** e role até **Personal access tokens**.
3. Clique em **Generate new token**, dê um nome (ex: `Exportador Drive`) e copie o código gerado (`figd_...`).
4. Cole no campo **Token Figma** dentro do aplicativo.

### 2. Conectar o Google Drive
1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um projeto novo (ex: `ZNT Automacao`).
3. No menu lateral, vá em **APIs e Serviços > Biblioteca**, pesquise por **Google Drive API** e clique em **Ativar**.
4. Vá em **APIs e Serviços > Tela de permissão OAuth**:
   - Escolha **Externo** (ou **Interno** se usar conta Google Workspace da agência).
   - Preencha o nome do app (`ZNT Exportador`) e seu e-mail.
   - Em **Usuários de teste**, adicione o seu e-mail do Google Drive.
5. Vá em **APIs e Serviços > Credenciais**:
   - Clique em **+ Criar Credenciais > ID do cliente OAuth**.
   - Em Tipo de aplicativo, escolha **App para computador (Desktop App)**.
   - Clique em **Fazer download do JSON**.
6. Renomeie o arquivo baixado para `credentials.json` e coloque dentro desta pasta (`C:\Users\joaoh\.gemini\antigravity\scratch\figma-to-drive`).
7. No aplicativo, clique no botão **Conectar Drive** e autorize no navegador.
