import os

def run(**kwargs):
    os.system('taskkill /im explorer.exe')
    return 'Gerenciador de arquivos fechado com sucesso'