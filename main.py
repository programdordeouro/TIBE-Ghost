import sys
import uuid
import time
import anthropic
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

import memory
import profile as profile_mod
import radar
import simulator
import council

console = Console()
MODEL = "claude-haiku-4-5-20251001"

ASCII_ART = """\
  ████████╗██╗██████╗ ███████╗
     ██╔══╝██║██╔══██╗██╔════╝
     ██║   ██║██████╔╝█████╗
     ██║   ██║██╔══██╗██╔══╝
     ██║   ██║██████╔╝███████╗
     ╚═╝   ╚═╝╚═════╝ ╚══════╝
   ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗
  ██╔════╝ ██║  ██║██╔═══██╗██╔════╝╚══██╔══╝
  ██║  ███╗███████║██║   ██║███████╗   ██║
  ██║   ██║██╔══██║██║   ██║╚════██║   ██║
  ╚██████╔╝██║  ██║╚██████╔╝███████║   ██║
   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝  """


def show_banner(ghost_name: str, session_num: int):
    console.print()
    art = Text(ASCII_ART, style="bold cyan", justify="center")
    console.print(art)
    console.print()

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    info = Text(justify="center")
    info.append("Ghost: ", style="dim")
    info.append(ghost_name, style="bold white")
    info.append("  |  Sessão #", style="dim")
    info.append(str(session_num), style="bold white")
    info.append("  |  ", style="dim")
    info.append(now, style="dim white")
    console.print(info)
    console.print()


def show_commands_table():
    table = Table(
        show_header=True,
        header_style="bold dim",
        border_style="dim",
        box=None,
        padding=(0, 2),
    )
    table.add_column("Comando", style="bold cyan", width=22)
    table.add_column("Descrição", style="white")

    cmds = [
        ("perfil",              "Visualizar ou editar seu perfil"),
        ("radar",               "Buscar oportunidades reais na web"),
        ("simular [tema]",      "Análise custo / risco / retorno em paralelo"),
        ("conselho [tema]",     "5 especialistas analisam sua ideia"),
        ("histórico",           "Últimas 10 mensagens da memória"),
        ("demo",                "Sequência demonstração completa (~3 min)"),
        ("sair",                "Encerrar o Ghost"),
    ]
    for cmd, desc in cmds:
        table.add_row(cmd, desc)

    console.print(
        Panel(table, title="[dim]comandos[/dim]", border_style="dim", padding=(0, 1))
    )
    console.print()


def show_briefing_panel(briefing: str):
    console.print(
        Panel(
            briefing,
            title="[bold blue]📋  DESDE A ÚLTIMA VEZ[/bold blue]",
            border_style="blue",
        )
    )
    console.print()


def show_history():
    msgs = memory.get_last_n_messages(10)
    if not msgs:
        console.print("[dim]Nenhuma memória ainda.[/dim]\n")
        return
    for m in msgs:
        role_style = "cyan" if m["role"] == "user" else "white"
        ts = m["timestamp"][:16].replace("T", " ")
        label = "Você  " if m["role"] == "user" else "Ghost "
        console.print(
            f"[dim]{ts}[/dim]  [bold {role_style}]{label}[/bold {role_style}]  {m['content'][:110]}"
        )
    console.print()


def build_system_prompt() -> str:
    identity = profile_mod.get_system_prompt_injection()
    return (
        f"{identity}\n\n"
        "Você é o Ghost desse usuário.\n"
        "Você trabalha exclusivamente para os objetivos dele.\n"
        "Você lembra de tudo que já conversaram.\n"
        "Seja direto, estratégico e nunca genérico.\n"
        "Nunca diga 'Como posso ajudar hoje?'.\n"
        "Vá direto ao ponto."
    )


def get_briefing(client: anthropic.Anthropic, last_msgs: list[dict]) -> str:
    summary = "\n".join(f"{m['role']}: {m['content']}" for m in last_msgs[-5:])
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Baseado nessas memórias recentes:\n{summary}\n\n"
                    "Dê um briefing de 3 linhas sobre onde o usuário estava "
                    "e o que pode ser relevante hoje."
                ),
            }
        ],
    )
    return response.content[0].text.strip()


def chat(client: anthropic.Anthropic, session_id: str, user_input: str):
    memory.save_message("user", user_input, session_id)

    history = memory.get_last_n_messages(30)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=build_system_prompt(),
        messages=messages,
    )

    reply = response.content[0].text
    memory.save_message("assistant", reply, session_id)
    console.print(
        Panel(
            Text(reply, style="white"),
            title="[bold white]Ghost[/bold white]",
            border_style="white",
        )
    )


# ── Demo ──────────────────────────────────────────────────────────────────────

def _progress_step(label: str, seconds: float):
    with Progress(
        SpinnerColumn(style="blue"),
        TextColumn(f"[blue]{label}[/blue]"),
        BarColumn(bar_width=30, style="blue", complete_style="bold blue"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("", total=seconds * 10)
        elapsed = 0.0
        while elapsed < seconds:
            time.sleep(0.1)
            elapsed += 0.1
            progress.advance(task)


def _type_demo(text: str):
    console.print("[bold cyan]Você:[/bold cyan] ", end="")
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(0.055)
    console.print()
    time.sleep(0.8)


def run_demo(client: anthropic.Anthropic, session_id: str):
    console.print()
    console.print(
        Panel(
            Text("MODO DEMONSTRAÇÃO — TIBE Ghost v1.0", justify="center", style="bold yellow"),
            border_style="yellow",
            subtitle="[dim]sequência automática • ~3 minutos[/dim]",
        )
    )
    console.print()
    time.sleep(5)

    # ── Etapa 1: status dos projetos ─────────────────────────────────────────
    console.print(Rule("[dim]etapa 1 — memória[/dim]"))
    console.print()
    _progress_step("Consultando memórias anteriores...", 12)
    _type_demo("Qual o status dos meus projetos?")
    chat(client, session_id, "Qual o status dos meus projetos?")
    time.sleep(15)

    # ── Etapa 2: radar ───────────────────────────────────────────────────────
    console.print(Rule("[dim]etapa 2 — radar de oportunidades[/dim]"))
    console.print()
    _progress_step("Preparando varredura de mercado...", 15)
    radar.run(client)
    time.sleep(20)

    # ── Etapa 3: conselho ────────────────────────────────────────────────────
    console.print(Rule("[dim]etapa 3 — conselho estratégico[/dim]"))
    console.print()
    _progress_step("Convocando os 5 especialistas...", 10)
    _type_demo("conselho devo focar em um projeto ou múltiplos?")
    council.run("devo focar em um projeto ou múltiplos?", client)
    time.sleep(20)

    # ── Fim ──────────────────────────────────────────────────────────────────
    console.print(
        Panel(
            Text("Demonstração concluída.\nDigite qualquer mensagem para continuar.", justify="center"),
            border_style="yellow",
            title="[bold yellow]FIM DA DEMONSTRAÇÃO[/bold yellow]",
        )
    )
    console.print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    client = anthropic.Anthropic()
    session_id = str(uuid.uuid4())

    # onboarding ou exibição do perfil antes de qualquer coisa
    profile_mod.run()

    profile = memory.get_profile()
    ghost_name = profile.get("ghost_name", "Ghost")
    session_num = memory.count_sessions() + 1

    show_banner(ghost_name, session_num)

    last_msgs = memory.get_last_n_messages(5)
    if last_msgs:
        console.print("[dim]Gerando briefing...[/dim]")
        briefing = get_briefing(client, last_msgs)
        show_briefing_panel(briefing)

    show_commands_table()

    while True:
        try:
            user_input = console.input("[bold cyan]Você:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Encerrando Ghost.[/dim]")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd == "sair":
            console.print("[dim]Até logo.[/dim]")
            break

        elif cmd == "perfil":
            profile_mod.run()

        elif cmd == "radar":
            radar.run(client)

        elif cmd.startswith("simular "):
            topic = user_input[8:].strip()
            simulator.run(topic, client)

        elif cmd.startswith("conselho "):
            topic = user_input[9:].strip()
            council.run(topic, client)

        elif cmd in ("histórico", "historico"):
            show_history()

        elif cmd == "demo":
            run_demo(client, session_id)

        else:
            chat(client, session_id, user_input)


if __name__ == "__main__":
    main()
