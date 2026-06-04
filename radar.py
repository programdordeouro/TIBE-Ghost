import json
import anthropic
from duckduckgo_search import DDGS
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from memory import get_profile, save_opportunity

console = Console()
MODEL = "claude-haiku-4-5-20251001"


def _generate_search_terms(client: anthropic.Anthropic, profile: dict) -> list[str]:
    prompt = (
        "Com base neste perfil:\n"
        f"Objetivo: {profile.get('main_goal', 'não definido')}\n"
        f"Projetos: {profile.get('projects', 'não definido')}\n"
        f"Localização: {profile.get('location', 'não definido')}\n\n"
        "Gere 5 termos de busca em inglês, curtos e específicos, "
        "que encontrariam oportunidades REAIS para essa pessoa.\n"
        'Responda APENAS com JSON: {"terms": ["termo1", ...]}\n'
        "Sem markdown, sem explicação."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    try:
        return json.loads(raw)["terms"]
    except (json.JSONDecodeError, KeyError):
        # fallback: extrai linhas que pareçam termos
        console.print("[yellow]Aviso: parse dos termos de busca falhou, usando fallback.[/yellow]")
        lines = [l.strip().strip('"').strip("'").strip("-").strip() for l in raw.split("\n") if l.strip()]
        return [l for l in lines if l and len(l) < 80][:5]


def _search_web(terms: list[str]) -> list[dict]:
    results = []
    with DDGS() as ddgs:
        for term in terms:
            try:
                hits = list(ddgs.text(term, max_results=5))
                for h in hits:
                    results.append({
                        "term": term,
                        "title": h.get("title", ""),
                        "snippet": h.get("body", ""),
                        "url": h.get("href", ""),
                    })
            except Exception as e:
                console.print(f"[yellow]Busca falhou para '{term}': {e}[/yellow]")
    return results


def _analyze_results(
    client: anthropic.Anthropic,
    profile: dict,
    results: list[dict],
) -> list[dict]:
    profile_block = (
        f"Objetivo: {profile.get('main_goal', 'não definido')}\n"
        f"Projetos: {profile.get('projects', 'não definido')}\n"
        f"Localização: {profile.get('location', 'não definido')}"
    )

    results_block = "\n\n".join(
        f"[{i+1}] {r['title']}\n{r['snippet']}\n{r['url']}"
        for i, r in enumerate(results)
    )

    prompt = (
        "Analise estes resultados de busca para alguém com este perfil:\n"
        f"{profile_block}\n\n"
        "Resultados encontrados:\n"
        f"{results_block}\n\n"
        "Identifique as 3 oportunidades mais acionáveis e específicas.\n"
        "Para cada uma retorne JSON:\n"
        '{"opportunities": [\n'
        '  {"title": "...", "description": "...", "action": "próximo passo concreto", "score": 1-10}\n'
        "]}\n"
        "Apenas JSON, sem markdown."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    try:
        return json.loads(raw)["opportunities"]
    except (json.JSONDecodeError, KeyError):
        console.print("[yellow]Aviso: parse das oportunidades falhou, exibindo resposta bruta.[/yellow]")
        console.print(Panel(raw, title="[yellow]Resposta do Claude[/yellow]", border_style="yellow"))
        return []


def run(client: anthropic.Anthropic):
    profile = get_profile()

    console.print(
        Panel(
            Text("Radar de Oportunidades", justify="center", style="bold green"),
            border_style="green",
            subtitle="[dim]analisando seu perfil...[/dim]",
        )
    )

    # passo 1 — gerar termos de busca
    console.print("[dim]Gerando termos de busca...[/dim]")
    terms = _generate_search_terms(client, profile)
    console.print(f"[dim]Termos: {', '.join(terms)}[/dim]\n")

    # passo 2 — buscar na web
    console.print("[dim]Buscando oportunidades na web...[/dim]")
    results = _search_web(terms)

    if not results:
        console.print("[red]Nenhum resultado encontrado. Verifique sua conexão.[/red]")
        return

    console.print(f"[dim]{len(results)} resultados coletados. Analisando...[/dim]\n")

    # passo 3 — analisar com Claude
    opportunities = _analyze_results(client, profile, results)

    if not opportunities:
        return

    # passo 4 — salvar e exibir
    for opp in opportunities:
        title = opp.get("title", "Sem título")
        description = opp.get("description", "")
        action = opp.get("action", "")
        score = float(opp.get("score", 5))

        save_opportunity(title, description, score)

        body = Text()
        body.append(description, style="white")
        if action:
            body.append(f"\n\nPróximo passo: ", style="bold green")
            body.append(action, style="green")

        score_str = f"Score: {score:.0f}/10"
        console.print(
            Panel(
                body,
                title=f"[bold green]{title}[/bold green]",
                subtitle=f"[dim]{score_str}[/dim]",
                border_style="green",
            )
        )

    console.print()
