"""Acessa um link (URL) da internet fornecido, extrai os textos pulando o lixo html e retorna o texto limpo para leitura. Essencial acessar sites de respostas. OBRIGATÓRIO: Fornecer a key 'url' dentro de 'args'."""
import requests
from bs4 import BeautifulSoup

def run(**kwargs):
    url = kwargs.get("url", "")
    if not url:
        return "Erro: Parâmetro 'url' não fornecido."
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove scripts e estilos do HTML
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
            
        texto = soup.get_text(separator=' ', strip=True)
        # Limite fixo focado em encaixar no limite de tokens do LLM (aprox 4000 caracteres)
        tamanho_max = 5000
        if len(texto) > tamanho_max:
            return texto[:tamanho_max] + "... (CORTE DE TAMANHO MÁXIMO ATINGIDO)"
        return texto
    except Exception as e:
        return f"Erro ao ler site: {str(e)}"
