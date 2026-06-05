import os
import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ.setdefault("DB_PATH", "/tmp/ghost.db")
sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from mangum import Mangum

import memory
import profile as ghost_profile
import background_mind

app = FastAPI(title="TIBE Ghost API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MODEL = "claude-haiku-4-5-20251001"
STATIC_DIR = Path(__file__).parent / "static"

_HTML: str | None = None
_html_path = STATIC_DIR / "index.html"
if _html_path.exists():
    _HTML = _html_path.read_text(encoding="utf-8")


@app.get("/")
def serve_index():
    if _HTML:
        return HTMLResponse(_HTML)
    tree = [str(p) for p in Path(__file__).parent.parent.rglob("*") if p.is_file()]
    return HTMLResponse("<pre>index.html not found\n" + "\n".join(tree[:30]) + "</pre>")


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
def save_profile_field(req: ProfileField):
    memory.save_profile(req.key, req.value)
    return {"ok": True}

@app.post("/api/profile/analyze")
def analyze_profile():
    profile_text = memory.get_profile_text()
    if not memory.get_profile():
        raise HTTPException(400, "Profile not set up yet")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system="Você é um estrategista e psicólogo. Analise este perfil e identifique em exatamente 3 parágrafos: 1) O padrão central desta pessoa como ela realmente opera. 2) O maior risco invisível para seus objetivos. 3) A maior alavanca disponível que ela provavelmente não está usando. Seja direto, específico e profundo. Não seja genérico.",
        messages=[{"role": "user", "content": f"Perfil:\n{profile_text}"}]
    )
    analysis = response.content[0].text
    memory.save_profile("deep_analysis", analysis)
    return {"analysis": analysis}


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.post("/api/chat")
def chat(req: ChatRequest):
    client = anthropic.Anthropic()
    emotion = ghost_profile.detect_emotion(req.message)
    background_mind.detect_contradiction(req.message)

    history = memory.get_last_messages(35)
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history if m["role"] in ["user", "assistant"]
    ]
    messages.append({"role": "user", "content": req.message})

    system_prompt = ghost_profile.get_system_prompt()
    unshown = memory.get_unshown_thoughts()
    if unshown:
        extra = "\n".join([t["thought"] for t in unshown])
        system_prompt += f"\n\nINSIGHT PARA COMPARTILHAR NATURALMENTE SE RELEVANTE:\n{extra}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=system_prompt,
        messages=messages,
    )
    reply = response.content[0].text
    memory.save_message(req.session_id, "user", req.message, emotion)
    memory.save_message(req.session_id, "assistant", reply)
    for t in unshown:
        memory.mark_thought_shown(t["id"])

    return {"reply": reply, "emotion": emotion}


@app.get("/api/history")
def get_history(limit: int = 20):
    return {"messages": memory.get_last_messages(limit)}


@app.get("/api/sessions")
def get_sessions():
    return {"count": memory.count_sessions()}


@app.get("/api/briefing")
def get_briefing():
    briefing = background_mind.get_morning_briefing()
    return {"briefing": briefing or None}


@app.get("/api/patterns")
def get_patterns():
    return {"patterns": memory.get_patterns_text()}


@app.get("/api/contradictions")
def get_contradictions():
    return {"contradictions": memory.get_contradictions_text()}


# ── Radar ─────────────────────────────────────────────────────────────────────

@app.post("/api/radar")
def run_radar():
    client = anthropic.Anthropic()
    p = memory.get_profile()

    try:
        r = client.messages.create(
            model=MODEL,
            max_tokens=200,
            system="Você gera termos de busca estratégicos. Responda APENAS com JSON válido.",
            messages=[{"role": "user", "content": (
                f"Perfil: objetivo={p.get('main_goal','')}, projetos={p.get('projects','')}, "
                f"localização={p.get('location','')}, mercado={p.get('market','')}\n"
                "Gere 5 termos de busca em inglês para encontrar oportunidades reais.\n"
                '{"terms": ["termo1","termo2","termo3","termo4","termo5"]}'
            )}],
        )
        text = r.content[0].text.strip().replace("```json","").replace("```","")
        terms = json.loads(text).get("terms", [])
    except Exception:
        terms = [p.get("main_goal","business"), p.get("market","technology"),
                 "AI automation 2025", "online business opportunity", "startup growth"]

    from duckduckgo_search import DDGS
    all_results = []
    with DDGS() as ddgs:
        for term in terms[:5]:
            try:
                for res in ddgs.text(term, max_results=5):
                    all_results.append(
                        f"TÍTULO: {res.get('title','')}\nSNIPPET: {res.get('body','')}\nURL: {res.get('href','')}"
                    )
            except Exception:
                pass

    if not all_results:
        raise HTTPException(503, "Sem resultados de busca.")

    results_text = "\n\n".join(all_results[:20])
    try:
        r2 = client.messages.create(
            model=MODEL,
            max_tokens=600,
            system="Você identifica oportunidades reais e acionáveis. Responda APENAS com JSON válido sem markdown.",
            messages=[{"role": "user", "content": (
                f"Perfil: {p.get('main_goal','')} | {p.get('projects','')} | {p.get('location','')}\n\n"
                f"Resultados:\n{results_text}\n\n"
                "Identifique as 3 melhores oportunidades reais.\n"
                '{"opportunities": [{"title":"","description":"","action":"próximo passo concreto hoje","score":8,"window":"estimativa"}]}'
            )}],
        )
        text2 = r2.content[0].text.strip().replace("```json","").replace("```","")
        opps = json.loads(text2).get("opportunities", [])
    except Exception:
        opps = []

    for opp in opps:
        memory.save_opportunity(
            opp.get("title",""), opp.get("description",""),
            opp.get("action",""), opp.get("score",5), opp.get("window","indefinida"),
        )
    return {"opportunities": opps, "terms": terms}


# ── Council ───────────────────────────────────────────────────────────────────

@app.post("/api/council")
def run_council(req: TopicRequest):
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(400, "Topic required")

    profile_text = memory.get_profile_text()
    last = memory.get_last_messages(10)
    context = "\n".join([f"{m['role']}: {m['content'][:100]}" for m in last])
    full_question = f"Contexto do usuário:\n{profile_text}\n\nHistórico recente:\n{context}\n\nPergunta: {topic}"

    SPECIALISTS = [
        {"name": "ESTRATEGISTA", "color": "blue",    "prompt": "Você é um estrategista de crescimento agressivo. Pensa em vantagem competitiva, timing e posicionamento. Seja direto. Sem floreios. Máximo 180 palavras. Formato: PONTO CENTRAL / POR QUE AGORA / PRÓXIMO PASSO"},
        {"name": "CIENTISTA",    "color": "cyan",    "prompt": "Você é um cientista cético que exige evidências. Questione suposições. Identifique o que não foi testado. Máximo 180 palavras. Termine sempre com uma pergunta desafiadora."},
        {"name": "INVESTIDOR",   "color": "green",   "prompt": "Você é um investidor anjo experiente e frio. Pensa em ROI, risco de capital, competição, exit. Máximo 180 palavras. Dê um veredito claro no final."},
        {"name": "FILÓSOFO",     "color": "magenta", "prompt": "Você pensa em consequências de segunda e terceira ordem. O que se perde ao ganhar? Quais os efeitos invisíveis? Máximo 180 palavras. Faça o usuário pensar diferente."},
        {"name": "ADVERSÁRIO",   "color": "red",     "prompt": "Você pensa como o maior concorrente dessa pessoa pensaria. O que você faria para destruir o que ela está construindo? Onde está a vulnerabilidade real? Máximo 180 palavras."},
        {"name": "HACKER",       "color": "yellow",  "prompt": "Você encontra o caminho mais rápido e mais barato para testar qualquer ideia. MVP em 48h. Gambiarras inteligentes. Zero recursos. Máximo 180 palavras. Seja concreto e criativo."},
    ]

    def call_specialist(s):
        c = anthropic.Anthropic()
        r = c.messages.create(
            model=MODEL, max_tokens=300, system=s["prompt"],
            messages=[{"role": "user", "content": full_question}],
        )
        return s["name"], s["color"], r.content[0].text

    opinions: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(call_specialist, s): s for s in SPECIALISTS}
        for future in as_completed(futures):
            name, color, text = future.result()
            opinions[name] = {"text": text, "color": color}

    all_responses = "\n\n".join(f"{k}:\n{v['text']}" for k, v in opinions.items())
    p = memory.get_profile()
    synth = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=150,
        system="Você sintetiza múltiplas perspectivas de forma cirúrgica.",
        messages=[{"role": "user", "content": (
            f"Pergunta: {topic}\n\nRespostas:\n{all_responses}\n\n"
            f"Em exatamente 3 linhas:\nLinha 1: Maior CONSENSO\nLinha 2: Maior CONFLITO\n"
            f"Linha 3: O que {p.get('user_name','você')} deve fazer PRIMEIRO"
        )}],
    )

    memory.save_action(topic, synth.content[0].text, "council")
    order = [s["name"] for s in SPECIALISTS]
    return {
        "topic": topic,
        "specialists": [
            {"name": k, "color": opinions[k]["color"], "text": opinions[k]["text"]}
            for k in order if k in opinions
        ],
        "synthesis": synth.content[0].text,
    }


# ── Simulation ────────────────────────────────────────────────────────────────

@app.post("/api/simulate")
def run_simulation(req: TopicRequest):
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(400, "Topic required")

    profile_text = memory.get_profile_text()
    ANALYSTS = [
        ("CUSTO",   "blue",   "Você analisa APENAS custos e recursos necessários. Seja específico com números. Máximo 200 palavras. Liste investimento inicial, custos mensais, tempo, equipe."),
        ("RISCO",   "yellow", "Você analisa APENAS riscos. Seja brutalmente honesto. Nunca seja otimista. Liste 4 riscos principais com probabilidade alta/media/baixa e como mitigar. Máximo 200 palavras."),
        ("RETORNO", "green",  "Você analisa APENAS potencial de retorno. Use dados reais quando possível. Projete cenário pessimista, realista e otimista para 6 e 12 meses. Máximo 200 palavras."),
    ]

    def call_analyst(name, color, system):
        c = anthropic.Anthropic()
        r = c.messages.create(
            model=MODEL, max_tokens=300, system=system,
            messages=[{"role": "user", "content": f"Perfil: {profile_text}\nIdeia: {topic}"}],
        )
        return name, color, r.content[0].text

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(call_analyst, *a) for a in ANALYSTS]
        for future in as_completed(futures):
            name, color, text = future.result()
            results[name] = {"text": text, "color": color}

    causal = anthropic.Anthropic().messages.create(
        model=MODEL, max_tokens=200,
        system="Você pensa em engenharia reversa da realidade. Seja específico e acionável.",
        messages=[{"role": "user", "content": (
            f"Objetivo: {topic}\nPerfil: {profile_text}\n\n"
            "Quais 3 condições precisam ser verdadeiras HOJE para que esse futuro seja "
            "uma consequência inevitável em 18 meses? Máximo 150 palavras."
        )}],
    )

    memory.save_simulation(
        topic,
        results.get("CUSTO", {}).get("text", ""),
        results.get("RISCO", {}).get("text", ""),
        results.get("RETORNO", {}).get("text", ""),
        causal.content[0].text,
    )

    order = ["CUSTO", "RISCO", "RETORNO"]
    return {
        "topic": topic,
        "analysts": [
            {"name": k, "color": results[k]["color"], "text": results[k]["text"]}
            for k in order if k in results
        ],
        "causal_inversion": causal.content[0].text,
    }


# ── Vercel handler ────────────────────────────────────────────────────────────

handler = Mangum(app, lifespan="off")
