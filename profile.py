from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from memory import get_profile, save_profile

console = Console()

FIELDS = {
    "ghost_name": "Nome do Ghost",
    "user_name":  "Seu nome real",
    "main_goal":  "Objetivo principal (12 meses)",
    "projects":   "Projetos ativos",
    "skills":     "Habilidades principais",
    "location":   "País / Cidade",
}

QUESTIONS = [
    ("ghost_name", "Como você quer que seu Ghost se chame?"),
    ("user_name",  "Qual é o seu nome real?"),
    ("main_goal",  "Em uma frase: qual é o seu maior objetivo nos próximos 12 meses?"),
    ("projects",   "Liste até 3 projetos ativos (separe por vírgula):"),
    ("skills",     "Quais são suas 3 principais habilidades?"),
    ("location",   "Em qual país/cidade você está?"),
]


def _onboarding():
    console.print(
        Panel(
            Text("Bem-vindo ao TIBE Ghost\nVamos configurar seu perfil.", justify="center"),
            border_style="cyan",
            title="[bold cyan]Onboarding[/bold cyan]",
        )
    )
    console.print()

    for key, question in QUESTIONS:
        answer = Prompt.ask(f"[bold cyan]{question}[/bold cyan]").strip()
        while not answer:
            console.print("[red]Campo obrigatório.[/red]")
            answer = Prompt.ask(f"[bold cyan]{question}[/bold cyan]").strip()
        save_profile(key, answer)

    console.print()
    console.print(Panel("[green]Perfil criado. Seu Ghost está pronto.[/green]", border_style="green"))
    console.print()


def _show_table(profile: dict):
    table = Table(show_header=True, header_style="bold magenta", border_style="magenta")
    table.add_column("Campo", style="cyan", width=30)
    table.add_column("Valor", style="white")

    for key, label in FIELDS.items():
        table.add_row(label, profile.get(key, "[dim]não definido[/dim]"))

    console.print(table)


def _edit(profile: dict):
    label_to_key = {label.lower(): key for key, label in FIELDS.items()}
    key_set = set(FIELDS.keys())

    while True:
        console.print(
            "\n[dim]Digite o nome do campo para editar (ex: ghost_name, main_goal) "
            "ou [bold]Enter[/bold] para sair:[/dim]"
        )
        field = Prompt.ask("Campo").strip().lower()

        if not field:
            break

        # aceita tanto a chave direta quanto o label parcial
        matched_key = None
        if field in key_set:
            matched_key = field
        else:
            for label, key in label_to_key.items():
                if field in label:
                    matched_key = key
                    break

        if not matched_key:
            console.print(f"[red]Campo '{field}' não encontrado.[/red] Campos disponíveis: {', '.join(FIELDS.keys())}")
            continue

        current = profile.get(matched_key, "")
        label = FIELDS[matched_key]
        new_value = Prompt.ask(f"[bold cyan]{label}[/bold cyan]", default=current).strip()

        if new_value and new_value != current:
            save_profile(matched_key, new_value)
            profile[matched_key] = new_value
            console.print(f"[green]'{label}' atualizado.[/green]")

    console.print()


def run():
    profile = get_profile()
    is_empty = not any(k in profile for k in FIELDS)

    if is_empty:
        _onboarding()
    else:
        console.print(
            Panel(
                Text("Perfil Ghost", justify="center", style="bold"),
                border_style="magenta",
            )
        )
        _show_table(profile)
        _edit(profile)


def get_system_prompt_injection() -> str:
    profile = get_profile()

    ghost_name = profile.get("ghost_name", "Ghost")
    user_name  = profile.get("user_name",  "usuário")
    main_goal  = profile.get("main_goal",  "não definido")
    projects   = profile.get("projects",   "não definido")
    skills     = profile.get("skills",     "não definido")
    location   = profile.get("location",   "não definido")

    return (
        "IDENTIDADE DO GHOST:\n"
        f"Nome do Ghost: {ghost_name}\n"
        f"Usuário: {user_name}\n"
        f"Objetivo principal: {main_goal}\n"
        f"Projetos ativos: {projects}\n"
        f"Habilidades: {skills}\n"
        f"Localização: {location}"
    )


if __name__ == "__main__":
    run()
