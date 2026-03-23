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


def extract_bairro(text: str) -> Optional[str]:
    """Extract Sergipe municipality from text. Returns canonical name or None."""
    if not text:
        return None
    for mun, pattern in _MUNICIPIO_PATTERNS:
        if pattern.search(text):
            # Normalize abbreviations
            if mun == "Socorro":
                return "Nossa Senhora do Socorro"
            return mun
    return None
