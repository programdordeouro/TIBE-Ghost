import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from memory import get_profile

console = Console()
MODEL = "claude-haiku-4-5-20251001"

EXPERTS = [
    {
        "key":    "strategist",
        "label":  "Estrategista",
        "color":  "cyan",
        "system": (
            "Você é um estrategista de crescimento agressivo.\n"
            "Pensa em escala, vantagem competitiva e timing.\n"
            "Seja direto. Sem floreios. Máximo 150 palavras.\n"
            "Responda sempre com: ponto principal, por quê agora, próximo passo."
        ),
    },
    {
        "key":    "scientist",
        "label":  "Cientista",
        "color":  "blue",
        "system": (
            "Você é um cientista cético que exige evidências.\n"
            "Questione suposições. Peça dados. Aponte o que não foi testado.\n"
            "Máximo 150 palavras. Sempre termine com uma pergunta desafiadora."
        ),
    },
    {
        "key":    "investor",
        "label":  "Investidor",
        "color":  "yellow",
        "system": (
            "Você é um investidor anjo experiente.\n"
            "Pensa em ROI, risco de capital, exit, competição.\n"
            "Máximo 150 palavras. Seja frio e calculista."
        ),
    },
    {
        "key":    "philosopher",
        "label":  "Filósofo",
        "color":  "magenta",
        "system": (
            "Você pensa em consequências de segunda e terceira ordem.\n"
            "Ética, impacto de longo prazo, o que se perde ao ganhar.\n"
            "Máximo 150 palavras. Faça o usuário pensar diferente."
        ),
    },
    {
        "key":    "hacker",
        "label":  "Hacker",
        "color":  "green",
        "system": (
            "Você encontra o caminho mais rápido e barato para testar qualquer ideia.\n"
            "Sem recursos? Sem problema. Pensa em MVP em 48h, gambiarras inteligentes.\n"
            "Máximo 150 palavras. Seja prático e criativo."
        ),
    },
]


def _call_expert(expert: dict, topic: str, profile_str: str) -> tuple[str, str]:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=384,
        system=expert["system"],
        messages=[{"role": "user", "content": f"Tema: {topic}\nPerfil do usuário: {profile_str}"}],
    )
    return expert["key"], response.content[0].text.strip()


def _synthesize(client: anthropic.Anthropic, topic: str, opinions: dict[str, str]) -> str:
    block = "\n\n".join(
        f"{e['label'].upper()}:\n{opinions[e['key']]}"
        for e in EXPERTS
        if e["key"] in opinions
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=128,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Com base nestas 5 perspectivas sobre '{topic}':\n\n"
                    f"{block}\n\n"
                    "Qual é o maior ponto de consenso e o maior ponto de conflito?\n"
                    "2 frases apenas."
                ),
            }
        ],
    )
    return response.content[0].text.strip()


def run(topic: str, client: anthropic.Anthropic | None = None):
    if not topic.strip():
        console.print("[red]Informe o tema. Ex: conselho lançar curso online[/red]")
        return

    if client is None:
        client = anthropic.Anthropic()

    profile = get_profile()
    profile_str = (
        f"Objetivo: {profile.get('main_goal', 'não definido')} | "
        f"Projetos: {profile.get('projects', 'não definido')} | "
        f"Habilidades: {profile.get('skills', 'não definido')}"
    )

    console.print(
        Panel(
            Text(f"Conselho Estratégico: {topic}", justify="center", style="bold white"),
            border_style="white",
            subtitle="[dim]5 especialistas em paralelo...[/dim]",
        )
    )

    opinions: dict[str, str] = {}
    order: list[str] = [e["key"] for e in EXPERTS]

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_call_expert, expert, topic, profile_str): expert
            for expert in EXPERTS
        }
        for future in as_completed(futures):
            expert = futures[future]
            key, text = future.result()
            opinions[key] = text

    # exibe na ordem original dos especialistas
    for expert in EXPERTS:
        key = expert["key"]
        color = expert["color"]
        label = expert["label"]
        console.print(
            Panel(
                opinions.get(key, "Sem resposta."),
                title=f"[bold magenta]{label}[/bold magenta]",
                border_style=color,
            )
        )

    # síntese final
    console.print(Rule("[dim]síntese[/dim]"))
    synthesis = _synthesize(client, topic, opinions)
    console.print(
        Panel(
            Text(synthesis, justify="center"),
            title="[bold white]Síntese do Conselho[/bold white]",
            border_style="white",
        )
    )
    console.print()
