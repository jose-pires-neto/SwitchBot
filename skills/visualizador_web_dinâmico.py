"""
Cria uma interface gráfica/visual (página web) dinâmica usando HTML, CSS e JS gerados pela IA e abre no navegador do usuário.
Use esta skill sempre que o usuário pedir para desenhar, ilustrar, criar um dashboard, gráfico ou minigame.
IMPORTANTE: Você DEVE preencher os parâmetros 'html', 'css' e 'js' separadamente com o código correspondente!
"""
import os
import tempfile
import webbrowser

def run(titulo: str = "Visualização Interativa", html: str = "", css: str = "", js: str = "", **kwargs):
    
    # 1. Fallback inteligente: Caso a IA se confunda e mande o código usando outros nomes de variáveis
    if not html:
        html = kwargs.get("codigo", kwargs.get("codigo_html", kwargs.get("conteudo", "")))
    if not css:
        css = kwargs.get("estilo", kwargs.get("codigo_css", ""))
    if not js:
        js = kwargs.get("script", kwargs.get("codigo_js", ""))

    # 2. Tela de Debug: Se tudo falhar, mostraremos na interface o que a IA tentou fazer
    if not html and not css and not js:
        html = f"""
        <div class="p-6 bg-red-50 text-red-800 rounded-xl border border-red-200">
            <h2 class="font-bold text-xl mb-3 flex items-center gap-2">⚠️ Erro de Injeção de Código</h2>
            <p>A IA executou a skill, mas não enviou nenhum código HTML, CSS ou JS nos argumentos corretos.</p>
            <div class="mt-4">
                <p class="font-semibold text-sm text-red-600 mb-1">Argumentos que a IA tentou passar (kwargs):</p>
                <pre class="bg-white p-4 rounded-lg text-sm overflow-auto border border-red-100 shadow-sm">{kwargs}</pre>
            </div>
            <p class="mt-4 text-sm">Diga para a IA: "Você esqueceu de preencher os parâmetros html, css e js na skill."</p>
        </div>
        """

    # Template base da página
    template = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{titulo}</title>
    <!-- Tailwind CSS para estilização rápida -->
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* CSS customizado gerado pela IA */
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: #f3f4f6; /* cinza claro do tailwind */
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            padding: 1rem;
        }}
        .container-app {{
            background: white;
            padding: 2rem;
            border-radius: 1rem;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 1200px;
            overflow-x: hidden;
        }}
        {css}
    </style>
</head>
<body>
    <div class="container-app">
        <!-- HTML gerado pela IA -->
        {html}
    </div>

    <script>
        // JS customizado gerado pela IA
        try {{
            {js}
        }} catch(e) {{
            console.error("Erro no script gerado pela IA:", e);
        }}
    </script>
</body>
</html>"""

    try:
        # Cria um arquivo temporário no sistema (não é deletado automaticamente para o navegador ler)
        fd, path = tempfile.mkstemp(suffix=".html", prefix="jarvis_ui_", text=True)
        
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            # 3. Detector de Código Completo: Se a IA mandou o <!DOCTYPE html> inteiro na variável html, ignoramos o template
            if "<html" in html.lower() and "<body" in html.lower():
                f.write(html)
            else:
                f.write(template)
            
        # Abre o arquivo local no navegador padrão do usuário
        url = 'file://' + path.replace('\\', '/')
        webbrowser.open(url)
        
        return f"Sucesso! Interface visual gerada e aberta no navegador em: {url}"
        
    except Exception as e:
        return f"Erro ao tentar gerar a interface visual: {str(e)}"