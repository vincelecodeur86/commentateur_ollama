# Commentateur C

Petit utilitaire Windows qui commente automatiquement un fichier `.c` avec un
modèle local Ollama (par défaut `mistral:7b`). Le résultat est enregistré à
côté du fichier source sous le nom `<nom>_commente.c`, en ASCII pur.

## Utilisation directe

```bat
python commenter_code.py            :: interface graphique
python commenter_code.py fichier.c  :: ligne de commande
```

Prérequis : Python 3.8+ avec Tkinter, Ollama lancé, `ollama pull mistral:7b`.

## Installeur Windows (10 / 11)

`dist\Commentateur-C-Setup-<version>.exe` est le seul fichier à distribuer.
L'assistant :

- vérifie qu'un Python 3.8+ avec Tkinter est présent (registre PEP 514, puis
  le lanceur `py`) et propose sinon de l'installer via winget ou python.org ;
- installe l'utilitaire sans droits administrateur (dans
  `%LOCALAPPDATA%\Programs\Commentateur C`, ou pour tous les utilisateurs si
  on le choisit) ;
- crée l'entrée du menu Démarrer, le raccourci Bureau et la désinstallation
  dans Paramètres > Applications.

Ollama et le modèle ne sont pas installés par l'assistant.

### Reconstruire l'installeur

Sur la machine de construction uniquement :

```bat
winget install -e --id JRSoftware.InnoSetup
installer\build.bat
```

| Fichier | Rôle |
| --- | --- |
| `installer\commentateur.iss` | Script Inno Setup (version dans `AppVersion`) |
| `installer\make_icon.py` | Génère `commentateur.ico` en pur Python |
| `installer\build.bat` | Génère l'icône si besoin puis compile |

`commentateur.iss` doit rester encodé en UTF-8 **avec BOM**, sinon les accents
de l'assistant s'affichent mal.
