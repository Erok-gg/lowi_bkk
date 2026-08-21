"""local_llm.py — client Ollama DURCI.

Tout ce que ce fichier impose vient d'une campagne de mesure sur des paires
réelles du dépôt (650+ appels, cf. docs/journal-technique.md). Ne pas assouplir
ces règles sans refaire la mesure — chacune corrige une panne observée.

  1. Le raisonnement se pilote par le paramètre NATIF `think`.
     Le token `/no_think` dans le prompt est SILENCIEUSEMENT IGNORÉ : le modèle
     raisonne quand même, le raisonnement part dans `message.thinking`, et
     `message.content` reste VIDE si `num_predict` est atteint avant la fin.
     Mesuré : 0/10 avec `/no_think`, 8/10 avec `think:false`, prompt identique.

  2. Une réponse vide est une PANNE, pas un résultat. Sans cette détection on
     écrit des `null` en base sans aucun bruit — c'est la panne la plus
     dangereuse du dispositif, parce qu'elle est muette.

  3. Toute sortie est validée contre un schéma déclaré par l'appelant.
     Champ manquant, type faux, valeur hors énumération → rejet.

  4. MODE EXTRACTION par défaut : on demande au modèle de CONSTATER des faits,
     et c'est du code qui décide. Mesuré : le verdict direct atteint 92 % mais
     ne s'abstient JAMAIS (0/30 sur les cas indécidables) ; l'extraction atteint
     91 % et s'abstient correctement (23/30). Un appelant qui veut un verdict
     direct doit le justifier dans son SKILL.md.

  5. La `confidence` auto-déclarée n'est JAMAIS un seuil : qwen2.5:7b rendait
     0,9 sur des réponses fausses. Elle peut être journalisée, jamais utilisée
     pour filtrer.

  6. Pas d'auto-cohérence par défaut : 3 votes ont donné exactement la même
     matrice et les mêmes 8 erreurs que 1 vote, pour 3× le coût. Les erreurs du
     modèle sont déterministes, pas bruitées.

  7. `num_ctx` est FIXÉ, jamais laissé au défaut d'Ollama.
     Sans ça, Ollama dimensionne un grand contexte, le cache d'attention gonfle
     l'empreinte à 8,1 Go — au-delà des 8 Go de VRAM de la 4070 Laptop — et 24 %
     des couches basculent sur le CPU. Mesuré le 2026-08-02 : **49 s par appel
     contre 3,6 s**, soit un facteur 13, pour des prompts de ~250 jetons.
     Avec `num_ctx=2048` : 5,1 Go, 100 % sur GPU.
     C'est une dégradation SILENCIEUSE — les réponses restent justes, seul le
     débit s'effondre. Un lot de 4 000 annonces passe de 4 h à 54 h.
     Augmenter `num_ctx` au-delà du besoin réel n'apporte rien et coûte tout.

  8. Prompts COURTS. Mesuré : règles brèves ordonnées 92 %, procédure numérotée
     verbeuse 69 % — 23 points perdus en ajoutant des consignes.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request

HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:8b"      # mesuré 92 % ; hermes3 82 %, qwen3:4b 3/10
MODELS_WITH_THINKING = {"qwen3:8b", "qwen3:4b", "qwen3:14b", "qwen3:32b"}

# ───────────────────── absence délibérée du modèle local ─────────────────────
# Le 2e poste (24/7) est trop faible pour Ollama. Sans déclaration explicite,
# cette absence se lit comme une PANNE : `ask_safe` journalise un constat de
# sévérité HAUTE à chaque appel, soit jusqu'à 6 par cycle (1 overseer +
# 5 watch-health), tous les jours, indéfiniment. C'est le garde-fou qui crie au
# loup de la règle 2 — le compteur du widget resterait rouge en permanence sans
# jamais rien signaler de vrai.
#
# Le marqueur est un FICHIER, pas une variable d'environnement : il est propre à
# la MACHINE (le poste principal garde son Ollama, le 2e non) alors que le dépôt
# est le même des deux côtés. Il est gitignoré pour cette raison.
MARQUEUR_ABSENT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "t1-absent")


def t1_absent() -> bool:
    """Vrai si CE POSTE n'héberge délibérément aucun modèle local.

    Dans cet état, `ask_safe` rend None SANS journaliser de panne : les deux
    appelants purement rédactionnels (overseer, watch-health) retombent sur leur
    texte brut, et `organize` bascule en dépôt de tickets pour Claude."""
    return os.path.exists(MARQUEUR_ABSENT)


class LLMError(RuntimeError):
    """Panne d'inférence. Le kind est repris tel quel dans le finding."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}" if detail else kind)
        self.kind = kind
        self.detail = detail


# ───────────────────────── validation de schéma ─────────────────────────
def _check(value, spec: str):
    """spec ∈ 'bool' | 'number' | 'str' | 'enum:a|b|c' | 'any', suffixe '?' = nullable.

    Le suffixe `?` a été ajouté le 2026-08-02 : une extraction sur texte libre a
    besoin de dire « ce champ n'est pas mentionné ». Sans lui, un `null` légitime
    était rejeté comme schéma invalide, et l'appelant recevait un objet vide."""
    if spec.endswith("?"):
        if value is None:
            return None
        spec = spec[:-1]
    if spec == "any":
        return value
    if spec == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"attendu bool, reçu {type(value).__name__}")
        return value
    if spec == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"attendu number, reçu {type(value).__name__}")
        return float(value)
    if spec == "str":
        if not isinstance(value, str):
            raise ValueError(f"attendu str, reçu {type(value).__name__}")
        return value
    if spec.startswith("enum:"):
        allowed = spec[5:].split("|")
        if value not in allowed:
            raise ValueError(f"hors énumération ({value!r} ∉ {allowed})")
        return value
    raise ValueError(f"spec inconnue: {spec}")


def validate(obj: dict, schema: dict[str, str]) -> dict:
    if not isinstance(obj, dict):
        raise ValueError("la sortie n'est pas un objet JSON")
    out = {}
    for field, spec in schema.items():
        if field not in obj:
            # Un champ nullable ABSENT vaut « non mentionné » : sur du texte
            # libre, exiger sa présence obligerait le modèle à inventer.
            if spec.endswith("?"):
                out[field] = None
                continue
            raise ValueError(f"champ manquant: {field}")
        try:
            out[field] = _check(obj[field], spec)
        except ValueError as e:
            raise ValueError(f"champ {field}: {e}") from None
    return out


def _extract_json(raw: str) -> dict:
    """Robuste au texte parasite et à un éventuel bloc <think> résiduel."""
    txt = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise LLMError("PAS_DE_JSON", txt[:200])
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise LLMError("JSON_INVALIDE", f"{e} | {m.group(0)[:200]}") from None


# ───────────────────────── appel ─────────────────────────
def _post(path: str, body: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        HOST + path, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.URLError as e:
        raise LLMError("OLLAMA_INJOIGNABLE", str(e)) from None
    except TimeoutError:
        raise LLMError("TIMEOUT", f"{timeout}s") from None


#: Fenêtre de contexte. Nos prompts font ~250 jetons ; 2 048 laisse une marge
#: confortable ET garde le modèle entièrement en VRAM sur 8 Go (cf. RÈGLE 7).
DEFAULT_NUM_CTX = 2048


def ask(system: str, user: str, schema: dict[str, str], *,
        model: str = DEFAULT_MODEL, think: bool = False,
        num_predict: int = 400, temperature: float = 0.0,
        num_ctx: int = DEFAULT_NUM_CTX,
        retries: int = 2, timeout: int = 300) -> dict:
    """Un appel validé. Lève LLMError si aucune tentative ne produit de sortie
    conforme — l'appelant DOIT transformer ça en finding, jamais l'avaler."""
    body = {
        "model": model, "stream": False, "format": "json",
        "options": {"temperature": temperature, "num_predict": num_predict,
                    "num_ctx": num_ctx, "top_p": 0.9},   # RÈGLE 7
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }
    if model in MODELS_WITH_THINKING:
        body["think"] = bool(think)   # RÈGLE 1 — jamais `/no_think` dans le prompt

    last: LLMError | None = None
    for attempt in range(retries + 1):
        try:
            r = _post("/api/chat", body, timeout)
            content = (r.get("message") or {}).get("content") or ""
            if not content.strip():
                # RÈGLE 2 — la panne muette
                thinking = (r.get("message") or {}).get("thinking") or ""
                raise LLMError(
                    "SORTIE_VIDE",
                    f"done_reason={r.get('done_reason')} eval={r.get('eval_count')} "
                    f"thinking={len(thinking)} car. — budget num_predict probablement "
                    f"consommé par le raisonnement")
            return validate(_extract_json(content), schema)   # RÈGLE 3
        except LLMError as e:
            last = e
        except ValueError as e:
            last = LLMError("SCHEMA_INVALIDE", str(e))
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    raise last or LLMError("AUCUNE_SORTIE")


def ask_safe(system: str, user: str, schema: dict[str, str], ledger=None,
             agent: str = "?", run_id: int | None = None, **kw) -> dict | None:
    """Variante qui journalise la panne en finding et rend None.
    À utiliser en traitement de lot : une annonce illisible ne doit pas
    interrompre les 15 000 autres."""
    # Absence DÉCLARÉE : ce n'est pas une panne, donc pas de constat. Voir
    # MARQUEUR_ABSENT — sinon 6 constats hauts par jour, à perpétuité.
    if t1_absent():
        return None
    try:
        return ask(system, user, schema, **kw)
    except LLMError as e:
        if ledger is not None:
            ledger.finding(agent, "high", "llm_panne", f"{e.kind} sur appel local",
                           {"kind": e.kind, "detail": e.detail[:500]}, run_id)
        return None


def available_models() -> list[str]:
    try:
        with urllib.request.urlopen(HOST + "/api/tags", timeout=10) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        return []


def health() -> tuple[bool, str]:
    """Sonde de démarrage : Ollama répond-il, et le modèle par défaut est-il là ?"""
    # Un poste sans modèle DÉCLARÉ est sain. Rendre False ici afficherait une
    # croix permanente au `status`, et une croix permanente ne se lit plus.
    if t1_absent():
        return True, "T1 déclaré absent sur ce poste — comparaison déléguée à Claude (tickets)"
    models = available_models()
    if not models:
        return False, "Ollama injoignable sur " + HOST
    if DEFAULT_MODEL not in models:
        return False, f"{DEFAULT_MODEL} absent (disponibles : {', '.join(models)})"
    return True, f"{DEFAULT_MODEL} disponible"
