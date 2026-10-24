import requests, sys, re

def extraire_code(texte):
    # Cherche un bloc entre ``` (avec ou sans langage) ou entre '''
    m = re.search(r"(?:```|''')[a-zA-Z]*\n(.*?)(?:```|''')", texte, re.DOTALL)
    if m:
        return m.group(1).strip()
    return texte.strip()  # pas de bloc trouve : on renvoie tout

def commenter(fichier, modele="mistral:7b"):
    code = open(fichier, encoding="utf-8").read()
    prompt = (
        "Tu es un assistant de relecture. Ajoute des commentaires "
        "concis en français au code C suivant, sans modifier le code. "
        "n'utilise pas de caractères spéciaux et n'utilise pas de caracteres avec accents"
        "remplace systematiquement les caracteres qui contiennent des accents par la lettre équivalente sans accent. Par exemple caractère devient caractere"
        "ne formule pas de phrase autre que le commentaire du code. "
        "Renvoie uniquement le code commenté.\n\n" + code
    )
    r = requests.post("http://localhost:11434/api/generate",
                      json={"model": modele, "prompt": prompt,
                            "stream": False, "options": {"temperature": 0.2}})
    data=r.json()
    if "response" not in data:
        print("Erreur Ollama :", data, file=sys.stderr)
        sys.exit(1)
    return extraire_code(data["response"])
    

if __name__ == "__main__":
    print(commenter(sys.argv[1]))