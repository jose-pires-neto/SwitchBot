# **☁️ SwitchBot \- Seu Assistente Autônomo para Desktop**

O **SwitchBot** é um Agente de Inteligência Artificial (Agentic AI) projetado para rodar localmente no seu computador (Windows). Mais do que apenas conversar, o SwitchBot pode **agir** no seu sistema através de *Skills* (habilidades) escritas em Python, funcionando como um verdadeiro assistente pessoal que executa tarefas por você.

<img width="1500" height="500" alt="Image" src="https://github.com/user-attachments/assets/4d6a7319-6a33-4fa0-bf68-2a7c4b72b627" />

## 

## **Funcionalidades Principais**

* **Inteligência Híbrida:** Funciona tanto na Nuvem (via [Groq API](https://groq.com) para respostas ultrarrápidas com Llama 3\) quanto Localmente (via [Ollama](https://ollama.com) para total privacidade e uso offline).  
* **Sistema de Skills Dinâmicas:** A IA pode utilizar ferramentas existentes (como abrir programas, ler a área de transferência, ler sites) ou **criar e salvar novas skills** em tempo real se precisar.  
* **Modos de Visualização:**  
  * **Modo Chat (Desenvolvedor):** Mostra o "Chain of Thought" (linha de raciocínio) do modelo, exibindo exatamente o que a IA está pensando e executando.  
  * **Modo Mascote:** Uma interface minimalista onde um mascote animado flutua na sua tela, com balões de fala e expressões.  
* **Memória Persistente:** Usa um banco de dados SQLite local para lembrar das conversas anteriores e aprender as suas preferências.  
* **Gamificação:** Sistema de "XP" e Níveis integrado. Ganhe pontos ao concluir tarefas com o assistente\!  
* **Segurança Integrada:** Possui verificações (regex) para impedir que a IA crie códigos maliciosos ou destrutivos.

## **Como Começar (Instalação)**

Siga os passos abaixo para clonar e rodar o SwitchBot na sua máquina.

### **Pré-requisitos**

1. [Python 3.10 ou superior](https://www.python.org/downloads/) instalado no Windows.  
2. (Opcional, mas recomendado) [Ollama](https://ollama.com/download) instalado, caso queira rodar modelos locais sem depender de internet.

### **Passo a Passo**

**1\. Clone o repositório:**

git clone \[https://github.com/jose-pires-neto/SwitchBot.git\](https://github.com/jose-pires-neto/SwitchBot.git)  
cd switchbot

**2\. Crie e ative um Ambiente Virtual (Recomendado):**

python \-m venv venv  
\# Ative o ambiente:  
venv\\Scripts\\activate

**3\. Instale as dependências:**

pip install \-r requirements.txt

**4\. Configure as Variáveis de Ambiente:**

Crie um arquivo chamado .env na raiz do projeto (mesma pasta do main.py) e adicione a sua chave de API do Groq (necessária se for usar o provedor Cloud).

GROQ\_API\_KEY=sua\_chave\_api\_aqui\_sk\_...

**5\. Rode o Servidor:**

python main.py

*O SwitchBot abrirá automaticamente uma interface web como um "App" no seu navegador padrão.*

## **Como Usar**

Com o app aberto, você pode interagir com o SwitchBot de forma natural.

### **Atalhos e Dicas**

* **Alt \+ O:** Esconde ou mostra a janela do assistente de forma rápida (Overlay).  
* **Configurações (⚙️):** Clique no ícone da engrenagem para alternar entre Groq (Nuvem) e Ollama (Local), e gerenciar o download de novos modelos de IA.  
* **Troca de Modo:** Clique no ícone ao lado das configurações para alternar entre o Modo Chat e o Modo Mascote.

### 

### **Testando as Skills Iniciais**

Tente enviar estes comandos no chat para ver a IA agindo:

1. *"Abra a calculadora"*  
2. *"Copiei um texto longo, leia a minha área de transferência e faça um resumo em 3 tópicos."*  
3. *"Acesse o site https://www.google.com/search?q=https://pt.wikipedia.org/wiki/Intelig%C3%AAncia\_artificial e me dê um resumo."*  
4. *"Crie um formulário de login moderno usando Tailwind e mostre no visualizador."*

## 

## **Criando Novas Skills**

A arquitetura do SwitchBot permite que você crie novas habilidades muito facilmente. O motor da IA analisa a pasta /skills automaticamente.

Para criar uma skill manualmente:

1. Crie um arquivo .py na pasta skills/ (ex: tocar\_musica.py).  
2. Adicione uma docstring na primeira linha do arquivo. A IA usa esse texto para entender o que a skill faz.  
3. Crie uma função def run(\*\*kwargs):. Esta é a função que será executada.

**Exemplo básico:**

"""  
Toca um som de bipe simples para alertar o usuário.  
"""  
import winsound

def run(frequencia: int \= 1000, duracao: int \= 500, \*\*kwargs):  
    try:  
        winsound.Beep(int(frequencia), int(duracao))  
        return f"Sucesso: Bipe tocado (Freq: {frequencia}Hz, Duração: {duracao}ms)"  
    except Exception as e:  
        return f"Erro ao tocar bipe: {str(e)}"

## **📁 Estrutura de Arquivos**

* main.py: Servidor Flask e rotas da API, além da lógica de renderização da janela (App Mode).  
* jarvis\_core.py: O "Cérebro". Lida com a comunicação com os modelos (Groq/Ollama) e força as respostas no formato JSON necessário para o roteamento de ações.  
* model\_manager.py: Gerencia os provedores, incluindo download e exclusão de modelos Ollama via UI.  
* memory.py: Lida com o banco de dados SQLite para salvar histórico de chat e "fatos/preferências" do usuário.  
* skill\_manager.py: Lê, valida (Syntax Check) e executa as funções Python da pasta /skills.  
* security.py: Camada de regex que previne a execução de comandos destrutivos no Windows.  
* /ui: Contém os arquivos de interface (index.html, script.js, style.css).  
* /skills: Pasta onde todas as ferramentas da IA ficam guardadas.

## 

## **Tecnologias Utilizadas**

* **Backend:** Python, Flask, SQLite.  
* **Frontend:** HTML5, CSS3, Vanilla JavaScript.  
* **Integrações AI:** [Groq API](https://console.groq.com/) (Llama 3, DeepSeek), [Ollama](https://ollama.com/) (Local Models).

*Feito por JOSÉ PIRES O.N para tornar a automação local acessível, facil e inteligente.*
