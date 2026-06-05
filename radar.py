import os
import json
import anthropic
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from rich.console import Console
from rich.panel import Panel
import memory

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
console = Console()

def run_radar():
    p = memory.get_profile()
    main_goal = p.get("main_goal", "")
    projects = p.get("projects", "")
    location = p.get("location", "")
    market = p.get("market", "")
    console.print("[cyan]Gerando termos de busca...[/cyan]")
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system="Você gera termos de busca estratégicos. Responda APENAS com JSON válido.",
            messages=[{"role": "user", "content": f"Perfil: objetivo={main_goal}, projetos={projects}, localização={location}, mercado={market}\nGere 5 termos de busca em inglês para encontrar oportunidades reais e acionáveis.\nJSON: {{\"terms\": [\"termo1\", \"termo2\", \"termo3\", \"termo4\", \"termo5\"]}}"}]
        )
        text = r.content[0].text.strip().replace("```json","").replace("```","")
        terms = json.loads(text).get("terms", [])
    except:
        terms = [main_goal, market, f"{market} opportunity", "AI automation business", "online business 2025"]

    console.print(f"[cyan]Buscando {len(terms)} termos...[/cyan]")
    all_results = []
    ddgs = DDGS()
    for term in terms:
        try:
            results = list(ddgs.text(term, max_results=5))
            for res in results:
                all_results.append(f"TÍTULO: {res.get('title','')}\nSNIPPET: {res.get('body','')}\nURL: {res.get('href','')}")
        except:
            pass

    if not all_results:
        console.print("[red]Não foi possível buscar resultados.[/red]")
        return []

    results_text = "\n\n".join(all_results[:20])
    console.print("[cyan]Analisando oportunidades...[/cyan]")
    try:
        r2 = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system="Você identifica oportunidades reais e acionáveis. Responda APENAS com JSON válido sem markdown.",
            messages=[{"role": "user", "content": f"Perfil: {main_goal} | {projects} | {location}\n\nResultados:\n{results_text}\n\nIdentifique as 3 melhores oportunidades reais.\nJSON: {{\"opportunities\": [{{\"title\": \"título\", \"description\": \"descrição\", \"action\": \"próximo passo concreto hoje\", \"score\": 8, \"window\": \"estimativa\"}}]}}"}]
        )
        text2 = r2.content[0].text.strip().replace("```json","").replace("```","")
        opps = json.loads(text2).get("opportunities", [])
    except:
        opps = []

    for opp in opps:
        memory.save_opportunity(opp.get("title",""), opp.get("description",""), opp.get("action",""), opp.get("score",5), opp.get("window","indefinida"))
        console.print(Panel(
            f"[bold]{opp.get('description','')}[/bold]\n\n[green]AÇÃO AGORA:[/green] {opp.get('action','')}\n[yellow]Janela:[/yellow] {opp.get('window','')} | [cyan]Score: {opp.get('score',0)}/10[/cyan]",
            title=f"🎯 {opp.get('title','')}",
            border_style="green"
        ))
    return opps

def show_saved_opportunities():
    opps = memory.get_opportunities()
    if not opps:
        console.print("[yellow]Nenhuma oportunidade salva ainda.[/yellow]")
        return
    for opp in opps:
        console.print(Panel(
            f"{opp['description']}\n\n[green]AÇÃO:[/green] {opp['action']}\n[yellow]Janela:[/yellow] {opp['window']}",
            title=f"🎯 {opp['title']} | Score: {opp['score']}/10",
            border_style="green"
        ))
