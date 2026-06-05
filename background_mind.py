import os
import anthropic
import schedule
import time
import threading
import json
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import memory

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def think_daily():
    profile_text = memory.get_profile_text()
    last = memory.get_last_messages(20)
    memories_text = "\n".join([f"{m['role']}: {m['content'][:150]}" for m in last])
    patterns = memory.get_patterns_text()
    contradictions = memory.get_contradictions_text()

    tasks = [
        ("conexoes", "Você encontra conexões não óbvias entre informações dispersas.", f"Memórias:\n{memories_text}\nPerfil:\n{profile_text}\n\nIdentifique UMA conexão entre dois assuntos que a pessoa mencionou que ela provavelmente não percebeu. Uma frase de insight + uma frase de ação. Máximo 80 palavras."),
        ("padrao", "Você detecta padrões comportamentais com evidências.", f"Padrões: {patterns}\nContradições: {contradictions}\nMemórias: {memories_text}\n\nExiste padrão ficando mais frequente que merece atenção? Com evidências. Máximo 80 palavras. Se não houver responda exatamente: NENHUM"),
        ("janela", "Você identifica janelas de oportunidade específicas.", f"Perfil: {profile_text}\nData: {datetime.now().strftime('%Y-%m-%d')}\n\nExiste ação mais poderosa se feita nos próximos 7 dias? Por que agora? Máximo 80 palavras. Se não houver responda exatamente: NENHUMA")
    ]

    def call_thought(name, system, user):
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system=system,
            messages=[{"role": "user", "content": user}]
        )
        return name, r.content[0].text

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(call_thought, *t) for t in tasks]
        for future in as_completed(futures):
            name, thought = future.result()
            if thought.strip() not in ["NENHUM", "NENHUMA"]:
                memory.save_thought(thought, f"think_daily_{name}")

def detect_contradiction(user_message):
    p = memory.get_profile()
    patterns = memory.get_patterns_text()
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system="Você detecta contradições entre declarações e comportamentos. Responda APENAS com JSON válido.",
            messages=[{"role": "user", "content": f"Objetivo declarado: {p.get('main_goal','')}\nProjetos: {p.get('projects','')}\nPadrões: {patterns}\nMensagem atual: {user_message}\n\nExiste contradição?\nJSON: {{\"has_contradiction\": false, \"declared\": \"\", \"observed\": \"\", \"confidence\": \"baixo\"}}"}]
        )
        text = r.content[0].text.strip().replace("```json","").replace("```","")
        result = json.loads(text)
        if result.get("has_contradiction") and result.get("confidence") in ["alto", "medio"]:
            memory.save_contradiction(result.get("declared",""), result.get("observed",""))
            return True
    except:
        pass
    return False

def get_morning_briefing():
    thoughts = memory.get_unshown_thoughts()
    if not thoughts:
        return ""
    thoughts_text = "\n".join([t["thought"] for t in thoughts])
    try:
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system="Você apresenta insights de forma impactante e pessoal. Tom: presente, direto, pessoal.",
            messages=[{"role": "user", "content": f"Insights gerados enquanto o usuário estava ausente:\n{thoughts_text}\nPerfil: {memory.get_profile_text()}\n\nApresente como se o Ghost estivesse relatando o que pensou durante a ausência. Máximo 150 palavras."}]
        )
        for t in thoughts:
            memory.mark_thought_shown(t["id"])
        return r.content[0].text
    except:
        return thoughts_text

def start_background_mind():
    schedule.every().day.at("06:00").do(think_daily)
    think_daily()
    def run():
        while True:
            schedule.run_pending()
            time.sleep(60)
    t = threading.Thread(target=run, daemon=True)
    t.start()
