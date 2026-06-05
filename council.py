import os
import json
import anthropic
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.panel import Panel
import memory

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
console = Console()

SPECIALISTS = [
    {"name": "ESTRATEGISTA", "color": "bold blue",    "prompt": "Você é um estrategista de crescimento agressivo. Pensa em vantagem competitiva, timing e posicionamento. Seja direto. Sem floreios. Máximo 180 palavras. Formato: PONTO CENTRAL / POR QUE AGORA / PRÓXIMO PASSO"},
    {"name": "CIENTISTA",    "color": "bold cyan",    "prompt": "Você é um cientista cético que exige evidências. Questione suposições. Identifique o que não foi testado. Máximo 180 palavras. Termine sempre com uma pergunta desafiadora."},
    {"name": "INVESTIDOR",   "color": "bold green",   "prompt": "Você é um investidor anjo experiente e frio. Pensa em ROI, risco de capital, competição, exit. Máximo 180 palavras. Dê um veredito claro no final."},
    {"name": "FILÓSOFO",     "color": "bold magenta", "prompt": "Você pensa em consequências de segunda e terceira ordem. O que se perde ao ganhar? Quais os efeitos invisíveis? Máximo 180 palavras. Faça o usuário pensar diferente."},
    {"name": "ADVERSÁRIO",   "color": "bold red",     "prompt": "Você pensa como o maior concorrente dessa pessoa pensaria. O que você faria para destruir o que ela está construindo? Onde está a vulnerabilidade real? Máximo 180 palavras."},
    {"name": "HACKER",       "color": "bold yellow",  "prompt": "Você encontra o caminho mais rápido e mais barato para testar qualquer ideia. MVP em 48h. Gambiarras inteligentes. Zero recursos. Máximo 180 palavras. Seja concreto e criativo."}
]

def _call_specialist(specialist, question):
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=specialist["prompt"],
            messages=[{"role": "user", "content": question}]
        )
        return {"name": specialist["name"], "color": specialist["color"], "response": r.content[0].text}
    except Exception as e:
        return {"name": specialist["name"], "color": specialist["color"], "response": f"Erro: {e}"}

def run_council(question):
    profile_text = memory.get_profile_text()
    last = memory.get_last_messages(10)
    context = "\n".join([f"{m['role']}: {m['content'][:100]}" for m in last])
    full_question = f"Contexto do usuário:\n{profile_text}\n\nHistórico recente:\n{context}\n\nPergunta: {question}"
    console.print("[cyan]Consultando 6 especialistas em paralelo...[/cyan]")
    results = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_call_specialist, s, full_question): s for s in SPECIALISTS}
        for future in as_completed(futures):
            result = future.result()
            results[result["name"]] = result
            console.print(Panel(
                result["response"],
                title=f"[{result['color']}]{result['name']}[/{result['color']}]",
                border_style=result["color"].replace("bold ", "")
            ))
    all_responses = "\n\n".join([f"{k}:\n{v['response']}" for k, v in results.items()])
    p = memory.get_profile()
    synthesis = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        system="Você sintetiza múltiplas perspectivas de forma cirúrgica.",
        messages=[{"role": "user", "content": f"Pergunta: {question}\n\nRespostas:\n{all_responses}\n\nEm exatamente 3 linhas:\nLinha 1: Maior CONSENSO\nLinha 2: Maior CONFLITO\nLinha 3: O que {p.get('user_name','você')} deve fazer PRIMEIRO"}]
    )
    console.print(Panel(synthesis.content[0].text, title="SÍNTESE", border_style="bold white"))
    memory.save_action(question, synthesis.content[0].text, "council.py")
    return results

def run_simulation(topic):
    profile_text = memory.get_profile_text()
    tasks = [
        ("CUSTO",    "yellow", "Você analisa APENAS custos e recursos necessários. Seja específico com números. Máximo 200 palavras. Liste investimento inicial, custos mensais, tempo, equipe."),
        ("RISCO",    "red",    "Você analisa APENAS riscos. Seja brutalmente honesto. Nunca seja otimista. Liste 4 riscos principais com probabilidade alta/media/baixa e como mitigar. Máximo 200 palavras."),
        ("RETORNO",  "green",  "Você analisa APENAS potencial de retorno. Use dados reais quando possível. Projete cenário pessimista, realista e otimista para 6 e 12 meses. Máximo 200 palavras.")
    ]
    console.print("[cyan]Simulando em 3 dimensões paralelas...[/cyan]")
    results = {}
    def call_analysis(name, color, system):
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": f"Perfil: {profile_text}\nIdeia: {topic}"}]
        )
        return name, color, r.content[0].text
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(call_analysis, *t) for t in tasks]
        for future in as_completed(futures):
            name, color, response = future.result()
            results[name] = response
            console.print(Panel(response, title=f"[bold {color}]{name}[/bold {color}]", border_style=color))
    causal = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system="Você pensa em engenharia reversa da realidade. Seja específico e acionável.",
        messages=[{"role": "user", "content": f"Objetivo: {topic}\nPerfil: {profile_text}\n\nQuais 3 condições precisam ser verdadeiras HOJE para que esse futuro seja uma consequência inevitável em 18 meses? Máximo 150 palavras."}]
    )
    console.print(Panel(causal.content[0].text, title="[bold blue]CAUSALIDADE INVERTIDA[/bold blue]", border_style="blue"))
    memory.save_simulation(topic, results.get("CUSTO",""), results.get("RISCO",""), results.get("RETORNO",""), causal.content[0].text)
    return results
