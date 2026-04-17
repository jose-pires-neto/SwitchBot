"""Realiza buscas na internet usando DuckDuckGo e devolve links e resumos dos primeiros resultados. Útil para qualquer tipo de dúvida externa ou pesquisa. OBRIGATÓRIO: Fornecer a key 'query' dentro de 'args'."""
from duckduckgo_search import DDGS

def run(**kwargs):
    query = kwargs.get("query", "")
    if not query:
        return "Erro: Parâmetro 'query' não fornecido."
    results = []
    try:
        with DDGS() as ddgs:
            # Pega os primeiros 5 resultados para poupar tokens
            for r in ddgs.text(query, max_results=5):
                results.append(f"Título: {r.get('title')}\\nLink: {r.get('href')}\\nResumo: {r.get('body')}")
        if results:
            return "\\n\\n".join(results)
        return "A busca não retornou resultados."
    except Exception as e:
        return f"Erro na busca: {str(e)}"
