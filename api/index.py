import os
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

os.environ.setdefault("DB_PATH", "/tmp/ghost.db")
sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from mangum import Mangum

import memory

app = FastAPI(title="TIBE Ghost API", version="1.0.0")

STATIC_DIR = Path(__file__).parent.parent / "public"


@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"), media_type="text/html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = "claude-haiku-4-5-20251001"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()


def _build_system(profile: dict) -> str:
    return (
        "IDENTIDADE DO GHOST:\n"
        f"Nome do Ghost: {profile.get('ghost_name', 'Ghost')}\n"
        f"Usuário: {profile.get('user_name', 'usuário')}\n"
        f"Objetivo principal: {profile.get('main_goal', 'não definido')}\n"
        f"Projetos ativos: {profile.get('projects', 'não definido')}\n"
        f"Habilidades: {profile.get('skills', 'não definido')}\n"
        f"Localização: {profile.get('location', 'não definido')}\n\n"
        "Você é o Ghost desse usuário.\n"
        "Você trabalha exclusivamente para os objetivos dele.\n"
        "Você lembra de tudo que já conversaram.\n"
        "Seja direto, estratégico e nunca genérico.\n"
        "Nunca diga 'Como posso ajudar hoje?'.\n"
        "Vá direto ao ponto."
    )


# ── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str

class ProfileField(BaseModel):
    key: str
    value: str

class TopicRequest(BaseModel):
    topic: str


# ── Profile ───────────────────────────────────────────────────────────────────

@app.get("/api/profile")
def get_profile():
    return memory.get_profile()

@app.post("/api/profile")
def save_profile(req: ProfileField):
    memory.save_profile(req.key, req.value)
    return {"ok": True}


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
def chat(req: ChatRequest):
    client = _client()
    profile = memory.get_profile()

    memory.save_message("user", req.message, req.session_id)
    history = memory.get_last_n_messages(30)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_build_system(profile),
        messages=messages,
    )

    reply = response.content[0].text
    memory.save_message("assistant", reply, req.session_id)
    return {"reply": reply}


@app.get("/api/history")
def get_history(limit: int = 20):
    return {"messages": memory.get_last_n_messages(limit)}


@app.get("/api/sessions")
def get_sessions():
    return {"count": memory.count_sessions()}


@app.get("/api/briefing")
def get_briefing():
    client = _client()
    last_msgs = memory.get_last_n_messages(5)
    if not last_msgs:
        return {"briefing": None}

    summary = "\n".join(f"{m['role']}: {m['content']}" for m in last_msgs)
    response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": (
                f"Baseado nessas memórias recentes:\n{summary}\n\n"
                "Dê um briefing de 3 linhas sobre onde o usuário estava "
                "e o que pode ser relevante hoje."
            ),
        }],
    )
    return {"briefing": response.content[0].text.strip()}


# ── Radar ─────────────────────────────────────────────────────────────────────

@app.post("/api/radar")
def run_radar():
    client = _client()
    profile = memory.get_profile()

    terms_response = client.messages.create(
        model=MODEL,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": (
                "Com base neste perfil:\n"
                f"Objetivo: {profile.get('main_goal', 'não definido')}\n"
                f"Projetos: {profile.get('projects', 'não definido')}\n"
                f"Localização: {profile.get('location', 'não definido')}\n\n"
                "Gere 5 termos de busca em inglês, curtos e específicos, "
                "que encontrariam oportunidades REAIS para essa pessoa.\n"
                'Responda APENAS com JSON: {"terms": ["termo1", ...]}\n'
                "Sem markdown, sem explicação."
            ),
        }],
    )

    try:
        terms = json.loads(terms_response.content[0].text.strip())["terms"]
    except Exception:
        terms = ["business growth opportunities", "startup funding", "online business 2025"]

    from duckduckgo_search import DDGS
    results = []
    with DDGS() as ddgs:
        for term in terms[:5]:
            try:
                for h in ddgs.text(term, max_results=5):
                    results.append({
                        "title": h.get("title", ""),
                        "snippet": h.get("body", ""),
                        "url": h.get("href", ""),
                    })
            except Exception:
                pass

    if not results:
        raise HTTPException(503, "Sem resultados de busca. Tente novamente.")

    profile_block = (
        f"Objetivo: {profile.get('main_goal', 'não definido')}\n"
        f"Projetos: {profile.get('projects', 'não definido')}\n"
        f"Localização: {profile.get('location', 'não definido')}"
    )
    results_block = "\n\n".join(
        f"[{i+1}] {r['title']}\n{r['snippet']}\n{r['url']}"
        for i, r in enumerate(results[:15])
    )

    analyze_response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": (
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
            ),
        }],
    )

    try:
        opportunities = json.loads(analyze_response.content[0].text.strip())["opportunities"]
        for opp in opportunities:
            memory.save_opportunity(
                opp.get("title", ""),
                opp.get("description", ""),
                float(opp.get("score", 5)),
            )
        return {"opportunities": opportunities, "terms": terms}
    except Exception:
        return {"opportunities": [], "raw": analyze_response.content[0].text, "terms": terms}


# ── Simulate ──────────────────────────────────────────────────────────────────

@app.post("/api/simulate")
def run_simulation(req: TopicRequest):
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(400, "Topic required")

    profile = memory.get_profile()
    profile_str = (
        f"Objetivo: {profile.get('main_goal', 'não definido')} | "
        f"Projetos: {profile.get('projects', 'não definido')} | "
        f"Localização: {profile.get('location', 'não definido')}"
    )

    ANALYSTS = {
        "cost": {
            "label": "Analista de Custos",
            "system": (
                f"Você analisa APENAS custos e recursos.\n"
                f"Seja específico com números quando possível.\n"
                f"Para a ideia '{topic}' e perfil '{profile_str}':\n"
                "Liste: investimento inicial estimado, custos mensais, "
                "tempo necessário, recursos humanos. Máximo 200 palavras."
            ),
        },
        "risk": {
            "label": "Analista de Riscos",
            "system": (
                f"Você analisa APENAS riscos e o que pode dar errado.\n"
                f"Seja brutalmente honesto, não otimista.\n"
                f"Para a ideia '{topic}' e perfil '{profile_str}':\n"
                "Liste os 4 principais riscos com probabilidade (alta/média/baixa) "
                "e como mitigar cada um. Máximo 200 palavras."
            ),
        },
        "return": {
            "label": "Analista de Retorno",
            "system": (
                f"Você analisa APENAS potencial de retorno e upside.\n"
                f"Base suas estimativas em dados reais quando possível.\n"
                f"Para a ideia '{topic}' e perfil '{profile_str}':\n"
                "Projete cenário pessimista, realista e otimista para 6 e 12 meses. "
                "Máximo 200 palavras."
            ),
        },
    }

    def call_analyst(key: str):
        c = anthropic.Anthropic()
        r = c.messages.create(
            model=MODEL,
            max_tokens=512,
            system=ANALYSTS[key]["system"],
            messages=[{"role": "user", "content": f"Analise: {topic}"}],
        )
        return key, r.content[0].text.strip()

    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(call_analyst, k): k for k in ANALYSTS}
        for future in as_completed(futures):
            k, text = future.result()
            results[k] = text

    memory.save_simulation(
        topic,
        results.get("cost", ""),
        results.get("risk", ""),
        results.get("return", ""),
    )

    return {
        "topic": topic,
        "cost":   {"label": ANALYSTS["cost"]["label"],   "text": results.get("cost", "")},
        "risk":   {"label": ANALYSTS["risk"]["label"],   "text": results.get("risk", "")},
        "return": {"label": ANALYSTS["return"]["label"], "text": results.get("return", "")},
    }


# ── Council ───────────────────────────────────────────────────────────────────

@app.post("/api/council")
def run_council(req: TopicRequest):
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(400, "Topic required")

    profile = memory.get_profile()
    profile_str = (
        f"Objetivo: {profile.get('main_goal', 'não definido')} | "
        f"Projetos: {profile.get('projects', 'não definido')} | "
        f"Habilidades: {profile.get('skills', 'não definido')}"
    )

    EXPERTS = [
        {"key": "strategist",  "label": "Estrategista", "system": "Você é um estrategista de crescimento agressivo.\nPensa em escala, vantagem competitiva e timing.\nSeja direto. Sem floreios. Máximo 150 palavras.\nResponda sempre com: ponto principal, por quê agora, próximo passo."},
        {"key": "scientist",   "label": "Cientista",    "system": "Você é um cientista cético que exige evidências.\nQuestione suposições. Peça dados. Aponte o que não foi testado.\nMáximo 150 palavras. Sempre termine com uma pergunta desafiadora."},
        {"key": "investor",    "label": "Investidor",   "system": "Você é um investidor anjo experiente.\nPensa em ROI, risco de capital, exit, competição.\nMáximo 150 palavras. Seja frio e calculista."},
        {"key": "philosopher", "label": "Filósofo",     "system": "Você pensa em consequências de segunda e terceira ordem.\nÉtica, impacto de longo prazo, o que se perde ao ganhar.\nMáximo 150 palavras. Faça o usuário pensar diferente."},
        {"key": "hacker",      "label": "Hacker",       "system": "Você encontra o caminho mais rápido e barato para testar qualquer ideia.\nSem recursos? Sem problema. Pensa em MVP em 48h, gambiarras inteligentes.\nMáximo 150 palavras. Seja prático e criativo."},
    ]

    def call_expert(expert: dict):
        c = anthropic.Anthropic()
        r = c.messages.create(
            model=MODEL,
            max_tokens=384,
            system=expert["system"],
            messages=[{"role": "user", "content": f"Tema: {topic}\nPerfil do usuário: {profile_str}"}],
        )
        return expert["key"], r.content[0].text.strip()

    opinions: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(call_expert, e): e for e in EXPERTS}
        for future in as_completed(futures):
            k, text = future.result()
            opinions[k] = text

    block = "\n\n".join(
        f"{e['label'].upper()}:\n{opinions.get(e['key'], '')}"
        for e in EXPERTS
    )
    synth = _client().messages.create(
        model=MODEL,
        max_tokens=128,
        messages=[{
            "role": "user",
            "content": (
                f"Com base nestas 5 perspectivas sobre '{topic}':\n\n{block}\n\n"
                "Qual é o maior ponto de consenso e o maior ponto de conflito?\n"
                "2 frases apenas."
            ),
        }],
    )

    return {
        "topic": topic,
        "experts": [
            {"key": e["key"], "label": e["label"], "text": opinions.get(e["key"], "")}
            for e in EXPERTS
        ],
        "synthesis": synth.content[0].text.strip(),
    }


# ── Vercel handler ────────────────────────────────────────────────────────────

handler = Mangum(app, lifespan="off")
