"""
Nettoyage IA optionnel.
Nécessite OPENAI_API_KEY dans l'environnement.
L'IA ne doit pas inventer le prix, le poids ou les dimensions.
"""
import json, os
from openai import OpenAI

def enrich(product):
    key=os.getenv("OPENAI_API_KEY")
    if not key:
        return product
    client=OpenAI(api_key=key)
    payload={k:product.get(k) for k in ["name","title","description","category","sizes","seller","tags"]}
    response=client.responses.create(
        model=os.getenv("OPENAI_MODEL","gpt-5"),
        instructions="""Tu nettoies des fiches de vêtements. Retourne uniquement un JSON valide avec:
name, title, description, category, tags.
Ne modifie jamais prix, currency, sizes, weight, dimensions, seller, sku, images ou URLs.
N'invente aucune caractéristique absente. category doit être l'une de: tshirt,veste,pantalon,chaussure,accessoire,sac.""",
        input=json.dumps(payload,ensure_ascii=False)
    )
    try:
        data=json.loads(response.output_text)
        for k in ["name","title","description","category","tags"]:
            if k in data: product[k]=data[k]
    except Exception as e:
        print("IA: réponse non JSON, données originales conservées:",e)
    return product
