"""Commentateur de code C via Ollama (modele local, par defaut mistral:7b).

Lancement :
    python commenter_code.py             -> interface graphique
    python commenter_code.py fichier.c   -> mode ligne de commande

Le resultat est enregistre a cote du fichier source sous le nom
<nom>_commente.c, en ASCII pur (accents et caracteres speciaux retires).
Aucune dependance externe : uniquement la bibliotheque standard Python.
"""

import json
import os
import queue
import re
import sys
import threading
import unicodedata
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434"
MODELE_DEFAUT = "mistral:7b"

PROMPT_SYSTEME = (
    "Tu es un assistant de relecture de code C. "
    "Ajoute des commentaires concis en francais au code C fourni. "
    "Regles strictes : "
    "1) ne modifie jamais le code lui-meme, ajoute seulement des commentaires ; "
    "2) ecris les commentaires sans accents ni caracteres speciaux "
    "(ecris 'fenetre' et non 'fenêtre', 'caractere' et non 'caractère') ; "
    "3) renvoie uniquement le code commente dans un bloc ```c, "
    "sans aucune phrase avant ou apres."
)


# ---------------------------------------------------------------------------
# Nettoyage du texte
# ---------------------------------------------------------------------------

# Caracteres qui ne se decomposent pas proprement avec NFKD.
REMPLACEMENTS = {
    "œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE", "ß": "ss",
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "″": '"',
    "–": "-", "—": "-", "‐": "-", "‑": "-", "−": "-",
    "…": "...", "•": "*", "·": ".", "×": "x", "÷": "/",
    "→": "->", "←": "<-", "⇒": "=>", "≤": "<=", "≥": ">=", "≠": "!=",
    "°": " deg", "€": "EUR", " ": " ", " ": " ",
}


def nettoyer_texte(texte):
    """Retire accents et caracteres speciaux : renvoie un texte 100 % ASCII."""
    for src, dst in REMPLACEMENTS.items():
        texte = texte.replace(src, dst)
    # NFKD separe "e" de son accent, on ne garde ensuite que l'ASCII.
    texte = unicodedata.normalize("NFKD", texte)
    texte = texte.encode("ascii", "ignore").decode("ascii")
    return texte.replace("\r\n", "\n")


def extraire_code(texte):
    """Recupere le contenu du premier bloc ``` si le modele en a produit un."""
    m = re.search(r"```[a-zA-Z+]*[ \t]*\n(.*?)```", texte, re.DOTALL)
    if m:
        return m.group(1).strip() + "\n"
    # Bloc ouvert mais jamais ferme (reponse tronquee).
    m = re.search(r"```[a-zA-Z+]*[ \t]*\n(.*)", texte, re.DOTALL)
    if m:
        return m.group(1).strip() + "\n"
    return texte.strip() + "\n"


def retirer_commentaires(code):
    """Supprime commentaires et espaces pour comparer deux versions du code."""
    sortie, i, n = [], 0, len(code)
    while i < n:
        c = code[i]
        if code.startswith("//", i):
            fin = code.find("\n", i)
            i = n if fin == -1 else fin
        elif code.startswith("/*", i):
            fin = code.find("*/", i + 2)
            i = n if fin == -1 else fin + 2
        elif c in "\"'":
            j = i + 1
            while j < n and code[j] != c:
                j += 2 if code[j] == "\\" else 1
            sortie.append(code[i:j + 1])
            i = j + 1
        else:
            sortie.append(c)
            i += 1
    return re.sub(r"\s+", "", "".join(sortie))


def code_modifie(original, commente):
    """Vrai si le modele a touche au code (et pas seulement aux commentaires)."""
    return retirer_commentaires(nettoyer_texte(original)) != retirer_commentaires(commente)


def chemin_sortie(fichier):
    base, ext = os.path.splitext(fichier)
    return f"{base}_commente{ext or '.c'}"


def lire_fichier(fichier):
    with open(fichier, "rb") as f:
        brut = f.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return brut.decode(enc)
        except UnicodeDecodeError:
            continue
    return brut.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Appels a Ollama
# ---------------------------------------------------------------------------

class ErreurOllama(Exception):
    pass


def lister_modeles():
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except (urllib.error.URLError, OSError, ValueError):
        return None


def commenter(code, modele=MODELE_DEFAUT, sur_morceau=None, annule=None):
    """Envoie le code a Ollama en streaming et renvoie le code commente nettoye.

    sur_morceau(texte) est appele a chaque fragment recu ;
    annule() renvoie True pour interrompre la generation.
    """
    corps = json.dumps({
        "model": modele,
        "messages": [
            {"role": "system", "content": PROMPT_SYSTEME},
            {"role": "user", "content": "Commente ce code C :\n\n```c\n" + code + "\n```"},
        ],
        "stream": True,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }).encode("utf-8")
    requete = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=corps,
                                     headers={"Content-Type": "application/json"})
    reponse = []
    try:
        with urllib.request.urlopen(requete, timeout=600) as r:
            for ligne in r:
                if annule and annule():
                    raise ErreurOllama("Generation annulee.")
                if not ligne.strip():
                    continue
                data = json.loads(ligne)
                if "error" in data:
                    raise ErreurOllama(data["error"])
                morceau = data.get("message", {}).get("content", "")
                reponse.append(morceau)
                if sur_morceau and morceau:
                    sur_morceau(morceau)
                if data.get("done"):
                    break
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise ErreurOllama(f"Ollama a repondu {e.code} : {detail}") from e
    except (urllib.error.URLError, ConnectionError) as e:
        raise ErreurOllama(
            "Impossible de joindre Ollama sur " + OLLAMA_URL +
            ". Verifiez qu'il est lance (commande : ollama serve).") from e
    return nettoyer_texte(extraire_code("".join(reponse)))


# ---------------------------------------------------------------------------
# Interface graphique (Tkinter)
# ---------------------------------------------------------------------------

def lancer_interface():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    # Palette facon terminal : fond noir, touche de vert clair.
    NOIR, GRIS, GRIS_CLAIR, TEXTE, VERT = "#000000", "#121212", "#262626", "#e6e6e6", "#7CFC7C"
    POLICE, POLICE_CODE = ("Segoe UI", 10), ("Consolas", 10)

    # Identifiant propre pour que la barre des taches affiche notre icone, pas celle de Python.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CommentateurC.Ollama")
    except (ImportError, AttributeError, OSError):
        pass

    racine = tk.Tk()
    racine.title("Commentateur C - Ollama")
    dossier = os.path.dirname(os.path.abspath(__file__))
    for icone in (os.path.join(dossier, "commentateur.ico"),
                  os.path.join(dossier, "installer", "commentateur.ico")):
        if os.path.isfile(icone):
            try:
                racine.iconbitmap(default=icone)
            except tk.TclError:
                pass
            break
    racine.geometry("1150x720")
    racine.minsize(800, 500)
    racine.configure(bg=NOIR)

    style = ttk.Style(racine)
    style.theme_use("clam")
    style.configure(".", background=NOIR, foreground=TEXTE, font=POLICE,
                    fieldbackground=GRIS, bordercolor=GRIS_CLAIR)
    style.configure("TLabel", background=NOIR, foreground=TEXTE)
    style.configure("Titre.TLabel", font=("Segoe UI Semibold", 15))
    style.configure("Sous.TLabel", foreground="#9a9a9a")
    style.configure("TEntry", fieldbackground=GRIS, foreground=TEXTE, insertcolor=TEXTE)
    style.configure("TCombobox", fieldbackground=GRIS, foreground=TEXTE, arrowcolor=TEXTE,
                    background=GRIS_CLAIR)
    style.configure("Vertical.TScrollbar", background=GRIS_CLAIR, troughcolor=NOIR,
                    bordercolor=NOIR, arrowcolor=TEXTE, lightcolor=GRIS_CLAIR,
                    darkcolor=GRIS_CLAIR)
    style.map("Vertical.TScrollbar", background=[("active", VERT)], arrowcolor=[("active", NOIR)])
    style.map("TCombobox", fieldbackground=[("readonly", GRIS)],
              foreground=[("readonly", TEXTE)])
    style.configure("TButton", background=GRIS_CLAIR, foreground=TEXTE, padding=(12, 5))
    style.map("TButton", background=[("active", "#4a4a4a"), ("disabled", GRIS)],
              foreground=[("disabled", "#777777")])
    style.configure("Vert.TButton", background=VERT, foreground=NOIR,
                    font=("Segoe UI Semibold", 10), padding=(16, 6))
    style.map("Vert.TButton", background=[("active", "#a8ffa8"), ("disabled", "#2a4a2a")])
    style.configure("Horizontal.TProgressbar", background=VERT, troughcolor=GRIS,
                    bordercolor=GRIS, lightcolor=VERT, darkcolor=VERT)
    racine.option_add("*TCombobox*Listbox.background", GRIS)
    racine.option_add("*TCombobox*Listbox.foreground", TEXTE)

    var_fichier = tk.StringVar()
    var_modele = tk.StringVar(value=MODELE_DEFAUT)
    var_statut = tk.StringVar(value="Choisissez un fichier .c puis cliquez sur Commenter.")
    file_msgs = queue.Queue()
    etat = {"annule": False, "en_cours": False, "sortie": None}

    # --- En-tete -----------------------------------------------------------
    entete = ttk.Frame(racine, padding=(16, 12, 16, 4))
    entete.pack(fill="x")
    tk.Frame(entete, bg=VERT, width=6, height=34).pack(side="left", padx=(0, 10))
    ttk.Label(entete, text="Commentateur de code C", style="Titre.TLabel").pack(side="left")
    ttk.Label(entete, text="  via Ollama (local)", style="Sous.TLabel").pack(side="left", pady=(6, 0))

    # --- Formulaire --------------------------------------------------------
    form = ttk.Frame(racine, padding=(16, 8))
    form.pack(fill="x")
    form.columnconfigure(1, weight=1)

    ttk.Label(form, text="Fichier .c :").grid(row=0, column=0, sticky="w", padx=(0, 8))
    champ = ttk.Entry(form, textvariable=var_fichier)
    champ.grid(row=0, column=1, sticky="ew", ipady=3)
    ttk.Button(form, text="Parcourir...", command=lambda: parcourir()).grid(row=0, column=2, padx=(8, 0))

    ttk.Label(form, text="Modele :").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
    combo = ttk.Combobox(form, textvariable=var_modele, width=30)
    combo.grid(row=1, column=1, sticky="w", pady=(8, 0), ipady=2)

    actions = ttk.Frame(form)
    actions.grid(row=1, column=2, pady=(8, 0), sticky="e")
    bouton_go = ttk.Button(actions, text="Commenter", style="Vert.TButton",
                           command=lambda: demarrer())
    bouton_go.pack(side="left")
    bouton_stop = ttk.Button(actions, text="Annuler", state="disabled",
                             command=lambda: etat.update(annule=True))
    bouton_stop.pack(side="left", padx=(8, 0))

    # --- Zones de code -----------------------------------------------------
    panneaux = ttk.Panedwindow(racine, orient="horizontal")
    panneaux.pack(fill="both", expand=True, padx=16, pady=8)

    def zone(titre):
        cadre = ttk.Frame(panneaux)
        ttk.Label(cadre, text=titre, style="Sous.TLabel").pack(anchor="w", pady=(0, 4))
        texte = tk.Text(cadre, wrap="none", font=POLICE_CODE, bg=GRIS, fg=TEXTE,
                        insertbackground=TEXTE, relief="flat", padx=8, pady=6,
                        selectbackground=VERT, selectforeground=NOIR, state="disabled")
        barre = ttk.Scrollbar(cadre, orient="vertical", command=texte.yview)
        texte.configure(yscrollcommand=barre.set)
        barre.pack(side="right", fill="y")
        texte.pack(fill="both", expand=True)
        panneaux.add(cadre, weight=1)
        return texte

    zone_orig = zone("Code original")
    zone_res = zone("Code commente")
    zone_res.tag_configure("commentaire", foreground=VERT)

    # --- Barre d'etat ------------------------------------------------------
    bas = ttk.Frame(racine, padding=(16, 0, 16, 12))
    bas.pack(fill="x")
    progres = ttk.Progressbar(bas, mode="indeterminate", length=160)
    progres.pack(side="left")
    ttk.Label(bas, textvariable=var_statut).pack(side="left", padx=10)
    bouton_dossier = ttk.Button(bas, text="Ouvrir le dossier", state="disabled",
                                command=lambda: os.startfile(os.path.dirname(etat["sortie"])))
    bouton_dossier.pack(side="right")

    # --- Logique -----------------------------------------------------------
    def ecrire(zone_txt, contenu, ajouter=False):
        zone_txt.configure(state="normal")
        if not ajouter:
            zone_txt.delete("1.0", "end")
        zone_txt.insert("end", contenu)
        zone_txt.configure(state="disabled")
        if ajouter:
            zone_txt.see("end")

    def colorer_commentaires():
        zone_res.tag_remove("commentaire", "1.0", "end")
        contenu = zone_res.get("1.0", "end")
        for m in re.finditer(r"//[^\n]*|/\*.*?\*/", contenu, re.DOTALL):
            zone_res.tag_add("commentaire", f"1.0+{m.start()}c", f"1.0+{m.end()}c")

    def charger_apercu(*_):
        chemin = var_fichier.get().strip().strip('"')
        if os.path.isfile(chemin):
            try:
                ecrire(zone_orig, lire_fichier(chemin))
            except OSError:
                pass

    def parcourir():
        chemin = filedialog.askopenfilename(
            title="Choisir un fichier C",
            filetypes=[("Fichiers C", "*.c *.h"), ("Tous les fichiers", "*.*")])
        if chemin:
            var_fichier.set(os.path.normpath(chemin))

    def demarrer():
        chemin = var_fichier.get().strip().strip('"')
        if not os.path.isfile(chemin):
            messagebox.showerror("Fichier introuvable", f"Le fichier n'existe pas :\n{chemin}")
            return
        modele = var_modele.get().strip() or MODELE_DEFAUT
        code = lire_fichier(chemin)
        ecrire(zone_orig, code)
        ecrire(zone_res, "")
        etat.update(annule=False, en_cours=True, sortie=None)
        bouton_go.configure(state="disabled")
        bouton_stop.configure(state="normal")
        bouton_dossier.configure(state="disabled")
        progres.start(12)
        var_statut.set(f"{modele} reflechit... (le premier appel peut prendre un moment)")

        def travail():
            try:
                resultat = commenter(code, modele,
                                     sur_morceau=lambda t: file_msgs.put(("morceau", t)),
                                     annule=lambda: etat["annule"])
                sortie = chemin_sortie(chemin)
                with open(sortie, "w", encoding="ascii", newline="\n") as f:
                    f.write(resultat)
                file_msgs.put(("fini", (resultat, sortie, code_modifie(code, resultat))))
            except ErreurOllama as e:
                file_msgs.put(("erreur", str(e)))
            except Exception as e:  # garde l'interface vivante quoi qu'il arrive
                file_msgs.put(("erreur", f"{type(e).__name__} : {e}"))

        threading.Thread(target=travail, daemon=True).start()

    def terminer():
        etat["en_cours"] = False
        progres.stop()
        bouton_go.configure(state="normal")
        bouton_stop.configure(state="disabled")

    def lire_file():
        try:
            while True:
                genre, val = file_msgs.get_nowait()
                if genre == "morceau":
                    ecrire(zone_res, nettoyer_texte(val), ajouter=True)
                elif genre == "fini":
                    resultat, sortie, modifie = val
                    terminer()
                    ecrire(zone_res, resultat)
                    colorer_commentaires()
                    etat["sortie"] = sortie
                    bouton_dossier.configure(state="normal")
                    msg = f"Enregistre : {sortie}"
                    if modifie:
                        msg += "   /!\\ le modele semble avoir modifie le code, verifiez."
                    var_statut.set(msg)
                elif genre == "erreur":
                    terminer()
                    var_statut.set("Erreur.")
                    messagebox.showerror("Erreur", val)
        except queue.Empty:
            pass
        racine.after(50, lire_file)

    def rafraichir_modeles():
        modeles = lister_modeles()
        if modeles is None:
            var_statut.set("Ollama ne repond pas sur " + OLLAMA_URL + " - lancez 'ollama serve'.")
        else:
            combo.configure(values=modeles)
            if modeles and var_modele.get() not in modeles:
                var_statut.set(f"Modele {var_modele.get()} absent : 'ollama pull {var_modele.get()}'.")

    var_fichier.trace_add("write", charger_apercu)
    champ.bind("<Return>", lambda _: demarrer())
    racine.after(50, lire_file)
    racine.after(100, rafraichir_modeles)
    champ.focus_set()
    racine.mainloop()


# ---------------------------------------------------------------------------
# Point d'entree
# ---------------------------------------------------------------------------

def main_cli(fichier, modele=MODELE_DEFAUT):
    code = lire_fichier(fichier)
    print(f"Commentaire de {fichier} avec {modele}...", file=sys.stderr)
    try:
        resultat = commenter(code, modele,
                             sur_morceau=lambda t: print(".", end="", flush=True, file=sys.stderr))
    except ErreurOllama as e:
        print(f"\nErreur : {e}", file=sys.stderr)
        sys.exit(1)
    sortie = chemin_sortie(fichier)
    with open(sortie, "w", encoding="ascii", newline="\n") as f:
        f.write(resultat)
    print(f"\nEnregistre : {sortie}", file=sys.stderr)
    if code_modifie(code, resultat):
        print("Attention : le modele semble avoir modifie le code, verifiez.", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main_cli(sys.argv[1], *sys.argv[2:3])
    else:
        lancer_interface()
