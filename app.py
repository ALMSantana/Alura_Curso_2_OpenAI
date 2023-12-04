from flask import Flask,render_template, request, Response
from openai import OpenAI
from dotenv import load_dotenv
import os
from time import sleep
from helpers import *
from selecionar_documento import *
from selecionar_persona import *
from assistentes_ecomart import *
from tools_ecomart import *
import json
from vision_ecomart import analisar_imagem

load_dotenv()

cliente = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
modelo = "gpt-4-1106-preview"

app = Flask(__name__)
app.secret_key = 'alura'


thread = criar_thread()
file_ids = criar_lista_arquivo_ids() 
assistente = criar_assistente(file_ids)

STATUS_COMPLETED = "completed"
STATUS_REQUIRES_ACTION = "requires_action"

def bot(prompt):
    maxima_repeticao = 1
    repeticao = 0
    while True:
        try:
            personalidade = personas[selecionar_persona(prompt)]

            # adiciona aqui
            cliente.beta.threads.messages.create(
                thread_id=thread.id, 
                role = "user",
                content =  f"""
                Assuma, de agora em diante, a personalidade abaixo. 
                Ignore as personalidades anteriores.

                # Persona
                {personalidade}
                """
            )

            resposta_vision = ""
            global imagem_enviada
            if imagem_enviada != None:

                 resposta_vision = analisar_imagem("dados/new_caneca.png")
                 imagem_enviada = None

            cliente.beta.threads.messages.create(
                thread_id=thread.id, 
                role = "user",
                content =  prompt,
                file_ids=file_ids
            )

            run = cliente.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistente.id
            )


            while run.status != STATUS_COMPLETED:
                run = cliente.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id    
                )
                if run.status == STATUS_REQUIRES_ACTION:
                    tools_acionadas = run.required_action.submit_tool_outputs.tool_calls
                    respostas_tools_acionadas = []
                    for uma_tool in tools_acionadas:
                        nome_funcao = uma_tool.function.name
                        funcao_escolhida = minhas_funcoes[nome_funcao]
                        argumentos = json.loads(uma_tool.function.arguments)
                        print(argumentos)
                        resposta_funcao = funcao_escolhida(argumentos)

                        respostas_tools_acionadas.append({
                            "tool_call_id": uma_tool.id,
                            "output": resposta_funcao
                        })

                    run = cliente.beta.threads.runs.submit_tool_outputs(
                        thread_id = thread.id,
                        run_id = run.id,
                        tool_outputs=respostas_tools_acionadas
                    )

            historico = list(cliente.beta.threads.messages.list(thread_id=thread.id).data)
            resposta = historico[0]
            return resposta
        except Exception as erro:
                repeticao += 1
                if repeticao >= maxima_repeticao:
                        return "Erro no GPT: %s" % erro
                print('Erro de comunicação com OpenAI:', erro)
                sleep(1)

@app.route("/")
def home():
    return render_template("index.html")

@app.route('/upload_imagem', methods=['POST'])
def upload_imagem():
    if 'imagem' in request.files:
        global imagem_enviada 
        imagem_enviada = request.files['imagem']
        return 'Imagem recebida com sucesso!', 200
    return 'Nenhum arquivo foi enviado', 400

@app.route("/chat", methods=["POST"])
def chat():
    prompt = request.json["msg"]
    resposta = bot(prompt = prompt)
    texto_resposta = resposta.content[0].text.value
    return texto_resposta

if __name__ == "__main__":
    app.run(debug = True)
