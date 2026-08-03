"""gpu.py — partager la carte graphique avec l'utilisateur, au lieu de la prendre.

DEUX DÉFAUTS OBSERVÉS LE 2026-08-02 et une précaution, chacun une brique d'ici.

1. **L'agent prenait le GPU sans rien demander.** Un jeu tournait ; le modèle
   local a débordé de la VRAM et 24 % de ses couches sont passées sur le CPU.
   Personne n'a rien vu — les réponses restaient justes, seul le débit
   s'effondrait. C'est une panne MUETTE, la même famille que la sortie vide.

2. **Rien n'empêchait deux exemplaires de tourner ensemble.** C'est une
   PRÉCAUTION, pas la correction d'un incident : j'ai d'abord cru en observer un,
   c'était en réalité la chaîne lanceur/interpréteur du venv (deux entrées, même
   ligne de commande, l'une père de l'autre). Le verrou reste justifié — rien
   n'interdisait la collision — mais il ne répare rien de constaté.

3. **Un traitement interrompu repartait de zéro.** Exigence posée dès le départ :
   « je dois être capable de couper et reprendre l'analyse ».

LE SEUIL SE DÉDUIT, IL NE S'INVENTE PAS. Le modèle tient dans ~5 100 MiB, la
carte en offre 8 188 : au-delà de ~2 500 MiB pris par un tiers, le modèle ne
rentre plus. On ne compare donc pas à un pourcentage arbitraire, mais à ce qui
reste RÉELLEMENT libre une fois l'occupation tierce retirée.

On mesure l'occupation tierce par SOUSTRACTION — `nvidia-smi` total moins ce
qu'Ollama déclare détenir. La mémoire par processus est souvent illisible sous
Windows (« Insufficient Permissions »), la soustraction ne l'est jamais.

CE QUE CE MODULE NE COUVRE PAS — constaté le 2026-08-02 au soir. Il surveille la
VRAM, et RIEN D'AUTRE. Or l'inférence a aussi besoin du processeur : pendant que
quatre scrapers tournaient en parallèle, le débit du modèle s'est effondré alors
que la VRAM était largement disponible (633 MiB pris par des tiers sur 8 188).
La contention était sur le CPU. Un `ceder_si_besoin()` qui ne regarde que la
carte laisse donc passer ce cas — à traiter, ou à contourner en n'ordonnançant
jamais un lot de modèle en même temps qu'un scrap.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

HOST = "http://localhost:11434"

#: Coussin pour les fluctuations d'affichage (fenêtre déplacée, vidéo, veille
#: d'écran). Sans lui on bascule en cession sur du bruit.
MARGE_MIB = 400

#: Empreinte du modèle, VRAM comprise. Mesurée avec `num_ctx=2048` : 5,1 Go.
#: Sans `num_ctx` fixé, Ollama monte à 8,1 Go et ne tient plus (cf. local_llm
#: RÈGLE 7).
MODELE_MIB = 5200

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _run(args: list[str]) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=15,
                              creationflags=CREATE_NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def etat() -> dict:
    """(total, utilisé, part d'Ollama, part des tiers) en MiB.

    `disponible` est ce qui resterait si Ollama rendait tout : c'est LUI qui
    décide si le modèle peut se charger, pas la mémoire libre à l'instant t.
    """
    out = _run(["nvidia-smi", "--query-gpu=memory.used,memory.total",
                "--format=csv,noheader,nounits"])
    if not out.strip():
        return {"disponible": None}          # pas de carte NVIDIA : on ne bride rien
    try:
        utilise, total = (int(x.strip()) for x in out.strip().splitlines()[0].split(","))
    except ValueError:
        return {"disponible": None}
    ollama = 0
    try:
        d = json.load(urllib.request.urlopen(f"{HOST}/api/ps", timeout=5))
        ollama = sum(m.get("size_vram", 0) for m in d.get("models", [])) // 1048576
    except Exception:
        pass
    tiers = max(0, utilise - ollama)
    return {"total": total, "utilise": utilise, "ollama": ollama, "tiers": tiers,
            "disponible": total - tiers}


def gpu_libre(modele_mib: int = MODELE_MIB) -> tuple[bool, str]:
    """Le modèle peut-il tenir ENTIÈREMENT en VRAM à côté des tiers ?"""
    e = etat()
    if e["disponible"] is None:
        return True, "pas de carte NVIDIA détectée — aucune restriction"
    besoin = modele_mib + MARGE_MIB
    ok = e["disponible"] >= besoin
    return ok, (f"tiers {e['tiers']} MiB, disponible {e['disponible']} MiB, "
                f"besoin {besoin} MiB → {'libre' if ok else 'OCCUPÉ'}")


def liberer_modele(model: str = "qwen3:8b") -> None:
    """Décharge le modèle de la VRAM. `keep_alive: 0` le fait immédiatement.

    Se mettre en pause ne suffirait pas : Ollama garde le modèle chargé cinq
    minutes par défaut, donc 5 Go resteraient pris pendant qu'on « cède ».
    """
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"{HOST}/api/chat",
            json.dumps({"model": model, "messages": [], "keep_alive": 0}).encode(),
            {"Content-Type": "application/json"}), timeout=30).read()
    except Exception:
        pass


def ceder_si_besoin(model: str = "qwen3:8b", *, periode: int = 30,
                    attente_max: int | None = None, journal=print) -> bool:
    """Rend la main tant que la carte est prise. True si on peut reprendre.

    `attente_max=None` attend indéfiniment : c'est le comportement voulu pour un
    traitement de fond, qui n'a aucune raison de forcer le passage.
    """
    ok, detail = gpu_libre()
    if ok:
        return True
    journal(f"[gpu] cession — {detail}")
    liberer_modele(model)
    t0 = time.time()
    while True:
        time.sleep(periode)
        ok, detail = gpu_libre()
        if ok:
            journal(f"[gpu] reprise après {time.time()-t0:.0f} s — {detail}")
            return True
        if attente_max is not None and time.time() - t0 > attente_max:
            journal(f"[gpu] abandon après {attente_max} s — {detail}")
            return False


# ────────────────────────────── instance unique ───────────────────────────────
class Verrou:
    """Empêche deux exemplaires du même traitement de tourner ensemble.

    Verrou POSÉ PAR LE SYSTÈME sur un descripteur ouvert, pas un fichier témoin :
    si le processus meurt — plantage, coupure, arrêt forcé — le système le relâche
    tout seul. Un fichier témoin, lui, survit à la mort de son propriétaire et
    bloque tous les suivants.
    """

    def __init__(self, nom: str, dossier: str | None = None):
        base = dossier or os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "state")
        os.makedirs(base, exist_ok=True)
        self.chemin = os.path.join(base, f"{nom}.lock")
        self._fd = None

    def __enter__(self):
        self._fd = os.open(self.chemin, os.O_RDWR | os.O_CREAT)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(self._fd)
            self._fd = None
            raise RuntimeError(
                f"Un autre exemplaire tourne déjà ({self.chemin}). "
                f"Deux traitements qui chargent le modèle en même temps le font "
                f"déborder de la VRAM : chacun ralentit sans que rien ne le dise.")
        os.truncate(self._fd, 0)
        os.write(self._fd, f"{os.getpid()}\n".encode())
        return self

    def __exit__(self, *_):
        if self._fd is not None:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    os.lseek(self._fd, 0, os.SEEK_SET)
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            finally:
                os.close(self._fd)
                self._fd = None


# ───────────────────────────── reprise après coupure ──────────────────────────
class Reprise:
    """Journal des éléments DÉJÀ traités, pour repartir où on s'est arrêté.

    Un fichier en ajout seul, une clé par ligne. Volontairement bête : il doit
    survivre à une coupure de courant au milieu d'une écriture, et une ligne
    tronquée ne doit coûter qu'un élément retraité — jamais un fichier illisible.
    """

    def __init__(self, chemin: str):
        self.chemin = chemin
        os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
        self.faits: set[str] = set()
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                self.faits = {l.strip() for l in f if l.strip()}
        self._f = open(chemin, "a", encoding="utf-8")

    def __contains__(self, cle) -> bool:
        return str(cle) in self.faits

    def marquer(self, cle) -> None:
        self.faits.add(str(cle))
        self._f.write(f"{cle}\n")
        self._f.flush()
        os.fsync(self._f.fileno())      # une coupure ne doit pas perdre la trace

    def fermer(self) -> None:
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fermer()


def traiter(elements, action, *, nom: str, reprise: str, model: str = "qwen3:8b",
            journal=print):
    """Boucle de traitement de lot : instance unique, cession, reprise.

    C'est le point d'entrée que tout agent T1 doit utiliser — les trois garanties
    y sont réunies, plutôt que réinventées à chaque appelant.
    """
    with Verrou(nom), Reprise(reprise) as r:
        total, faits, cedes = len(elements), 0, 0
        for i, el in enumerate(elements, 1):
            cle = el[0] if isinstance(el, tuple) else el
            if cle in r:
                continue
            if not ceder_si_besoin(model, journal=journal):
                journal(f"[gpu] arrêt volontaire à {i}/{total}")
                break
            cedes += 0
            action(el)
            r.marquer(cle)
            faits += 1
            if faits % 20 == 0:
                journal(f"    … {faits} traités ({i}/{total})")
        journal(f"[fin] {faits} traités, {len(r.faits)} connus au total sur {total}")
        return faits
