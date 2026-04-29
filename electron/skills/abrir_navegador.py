import webbrowser

def run(**kwargs):
    url = kwargs.get('url')
    navegador = kwargs.get('navegador')
    if navegador:
        navegador = navegador.lower()
        if navegador in ['google-chrome', 'chrome', 'firefox', 'edge', 'opera', 'brave']:
            navegador = {'google-chrome': 'chrome', 'chrome': 'chrome', 'firefox': 'firefox', 'edge': 'edge', 'opera': 'opera', 'brave': 'brave'}.get(navegador)
            try:
                import subprocess
                subprocess.run([navegador, '--new-window', url], shell=True)
            except Exception as e:
                print(f'Erro ao abrir navegador: {e}')
        else:
            print('Navegador não suportado.')
    else:
        print('URL não fornecida.')