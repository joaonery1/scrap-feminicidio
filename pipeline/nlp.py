"""
pipeline/nlp.py

Municipality (cidade) extraction for Sergipe/SE via regex match.
The bairro column is reused to store the municipality name.
"""

import re
from typing import Optional

MUNICIPIOS_SE = [
    "Aracaju",
    "Nossa Senhora do Socorro",
    "Lagarto",
    "Itabaiana",
    "São Cristóvão",
    "Estância",
    "Tobias Barreto",
    "Laranjeiras",
    "Barra dos Coqueiros",
    "Carmópolis",
    "Maruim",
    "Nossa Senhora das Dores",
    "Propriá",
    "Simão Dias",
    "Itaporanga d'Ajuda",
    "Neópolis",
    "Canindé de São Francisco",
    "Poço Redondo",
    "Nossa Senhora da Glória",
    "Aquidabã",
    "Cristinápolis",
    "Umbaúba",
    "Indiaroba",
    "Brejo Grande",
    "Japaratuba",
    "Capela",
    "Riachuelo",
    "Rosário do Catete",
    "General Maynard",
    "Divina Pastora",
    "Malhador",
    "Itabi",
    "Gararu",
    "Porto da Folha",
    "Monte Alegre de Sergipe",
    "Poço Verde",
    "Riachão do Dantas",
    "Pedrinhas",
    "Arauá",
    "Boquim",
    "Salgado",
    "Tomar do Geru",
    "Frei Paulo",
    "Carira",
    "Pinhão",
    "Nossa Senhora Aparecida",
    "Feira Nova",
    "Moita Bonita",
    "Pedra Mole",
    "Cumbe",
    "Canhoba",
    "São Domingos",
    "Japoatã",
    "Pacatuba",
    "Santana do São Francisco",
    "Muribeca",
    "Cedro de São João",
    "Telha",
    "Amparo de São Francisco",
    "Ilha das Flores",
    "São Francisco",
    "Graccho Cardoso",
    "Itabaianinha",
    "Ribeirópolis",
    "Nossa Senhora de Lourdes",
    "Pirambu",
    "Santo Amaro das Brotas",
    "São Miguel do Aleixo",
    "Siriri",
    "Areia Branca",
    "Campo do Brito",
    "Macambira",
    "Pedras",
    "São Domingos",
    "Tobias Barreto",
    # Abreviações comuns nos títulos
    "Socorro",  # Nossa Senhora do Socorro
]

# Longest first to avoid partial matches
_MUNICIPIO_PATTERNS = [
    (mun, re.compile(r"\b" + re.escape(mun) + r"\b", re.IGNORECASE))
    for mun in sorted(set(MUNICIPIOS_SE), key=len, reverse=True)
]

# Padrões contextuais: "em Aracaju", "no município de Lagarto", etc.
_CONTEXT_PATTERN = re.compile(
    r"(?:em|no município de|na cidade de|interior de|cidade de)\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇÀÈÌÒÙ][a-záéíóúâêîôûãõçàèìòù]+(?:\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇÀÈÌÒÙa-záéíóúâêîôûãõçàèìòù]+)*)",
    re.IGNORECASE,
)


def _normalize(mun: str) -> str:
    if mun.lower() == "socorro":
        return "Nossa Senhora do Socorro"
    return mun


_CONSUMADO = [
    "morta", "assassinada", "foi morta", "foi assassinada",
    "matou", "mataram", "morre", "morreu", "óbito", "vítima fatal",
    "corpo", "cadáver", "homicídio", "homicida",
    "feminicídio consumado", "feminicidio consumado",
    "facadas", "tiros", "esfaqueada", "baleada",
]

_TENTATIVA = [
    "tentativa", "tentou matar", "tentou assassinar",
    "sobreviveu", "foi resgatada", "resgatada", "escapou",
    "preso antes", "evitou", "socorrida", "socorrido",
    "internada", "internado", "hospital", "huse",
    "fugiu", "conseguiu fugir",
]


def classify_tipo(text: str) -> str:
    """Classifica o caso como consumado, tentativa ou desconhecido."""
    if not text:
        return "desconhecido"
    lower = text.lower()
    is_tentativa = any(kw in lower for kw in _TENTATIVA)
    is_consumado = any(kw in lower for kw in _CONSUMADO)
    if is_tentativa and not is_consumado:
        return "tentativa"
    if is_consumado:
        return "consumado"
    return "desconhecido"


def extract_bairro(text: str) -> Optional[str]:
    """Extract Sergipe municipality from text. Returns canonical name or None."""
    if not text:
        return None

    # 1. Busca direta pelo nome do município
    for mun, pattern in _MUNICIPIO_PATTERNS:
        if pattern.search(text):
            return _normalize(mun)

    # 2. Busca contextual: "em X", "no município de X"
    for match in _CONTEXT_PATTERN.finditer(text):
        candidate = match.group(1).strip()
        for mun, pattern in _MUNICIPIO_PATTERNS:
            if pattern.search(candidate):
                return _normalize(mun)

    return None
