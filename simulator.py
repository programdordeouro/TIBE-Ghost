import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from memory import get_profile, save_simulation

console = Console()
MODEL = "claude-haiku-4-5-20251001"

ANALYSTS = {
    "cost": {
        "label": "Analista de Custos",
        "color": "blue",
        "system": (
            "Você analisa APENAS custos e recursos.\n"
            "Seja específico com números quando possível.\n"
            "Para a ideia '{topic}' e perfil '{profile}':\n"
            "Liste: investimento inicial estimado, custos mensais, "
            "tempo necessário, recursos humanos. Máximo 200 palavras."
        ),
    },
    "risk": {
        "label": "Analista de Riscos",
        "color": "yellow",
        "system": (
            "Você analisa APENAS riscos e o que pode dar errado.\n"
            "Seja brutalmente honesto, não otimista.\n"
            "Para a ideia '{topic}' e perfil '{profile}':\n"
            "Liste os 4 principais riscos com probabilidade (alta/média/baixa) "
            "e como mitigar cada um. Máximo 200 palavras."
        ),
    },
    "return": {
        "label": "Analista de Retorno",
        "color": "green",
        "system": (
            "Você analisa APENAS potencial de retorno e upside.\n"
            "Base suas estimativas em dados reais quando possível.\n"
            "Para a ideia '{topic}' e perfil '{profile}':\n"
            "Projete cenário pessimista, realista e otimista para 6 e 12 meses. "
            "Máximo 200 palavras."
        ),
    },
}


def _call_analyst(key: str, topic: str, profile_str: str) -> tuple[str, str]:
    client = anthropic.Anthropic()
    analyst = ANALYSTS[key]
    system = analyst["system"].format(topic=topic, profile=profile_str)

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": f"Analise: {topic}"}],
    )
    return key, response.content[0].text.strip()


def run(topic: str, client: anthropic.Anthropic | None = None):
    if not topic.strip():
        console.print("[red]Informe o que deseja simular. Ex: simular abrir uma loja de roupas[/red]")
        return

    profile = get_profile()
    profile_str = (
        f"Objetivo: {profile.get('main_goal', 'não definido')} | "
        f"Projetos: {profile.get('projects', 'não definido')} | "
        f"Localização: {profile.get('location', 'não definido')}"
    )

    console.print(
        Panel(
            Text(f"Simulando: {topic}", justify="center", style="bold white"),
            border_style="white",
            subtitle="[dim]3 analistas em paralelo...[/dim]",
        )
    )

    results: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_call_analyst, key, topic, profile_str): key
            for key in ANALYSTS
        }
        for future in as_completed(futures):
            key, text = future.result()
            results[key] = text
            label = ANALYSTS[key]["label"]
            console.print(f"[magenta]{label} concluído.[/magenta]")

    # exibe em colunas se o terminal for largo o suficiente, senão em sequência
    panels = []
    for key in ("cost", "risk", "return"):
        analyst = ANALYSTS[key]
        panels.append(
            Panel(
                results.get(key, "Sem resposta."),
                title=f"[bold magenta]{analyst['label']}[/bold magenta]",
                border_style=analyst["color"],
                width=60,
            )
        )

    try:
        console.print(Columns(panels, equal=True, expand=True))
    except Exception:
        for panel in panels:
            console.print(panel)

    save_simulation(
        topic=topic,
        cost=results.get("cost", ""),
        risk=results.get("risk", ""),
        ret=results.get("return", ""),
    )

    console.print()
