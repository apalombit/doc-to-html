"""Each card's particulars: a date, people, towns and words for names — spec 0020.

**Why.** Over the pilot's 100 pages, written with no particulars, 69
carried an October 2026 date and 21 were dated 24 October 2026, the date
the brief's locale table shows as an example. "Okafor" was on 8 pages,
"Whitcombe" on 7, and "Harbour" or "Harbor" on 13. Each writer reached for
the same names, and on a contact sheet the corpus read as one author.
Alessandro, 2026-10-25: give the pages random dates and names for variety;
the 100 already written stay as they are.

**What a card is given.** Drawn from the card's id and `SEED`, so a card
always gets the same particulars and nothing is stored on it:
- `date`: the document's own date (issued, printed, the visit, the
  statement), uniform from `FIRST` to `LAST`;
- `people`: three people, a given name and a surname from the locale's
  lists;
- `places`: two towns of the locale's country;
- `name_words`: two words to build an organisation's, brand's or
  product's name from.

The lists leave out the names the pilot overused (`OVERUSED`), and the
brief tells writers to avoid them too.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from doc_to_html.factory.cards import Card

SEED = 20261025
FIRST = date(2019, 1, 1)
LAST = date(2027, 6, 30)

OVERUSED = ("Okafor", "Whitcombe", "Harbour", "Harbor", "Fenwick", "Calloway",
            "Marchetti", "Marrowfield")

GIVEN: dict[str, tuple[str, ...]] = {
    "en-GB": ("Amelia", "Oliver", "Isla", "Harry", "Priya", "Tom", "Niamh", "Callum",
              "Freya", "Rhys", "Zara", "Ewan", "Hannah", "Kwame", "Sophie", "Arjun",
              "Megan", "Declan", "Imogen", "Yusuf", "Ellie", "Gareth", "Leah", "Owen",
              "Bethan", "Rohan", "Ruth", "Finlay", "Aisha", "Stuart"),
    "en-US": ("Jordan", "Maria", "Tyler", "Keisha", "Brandon", "Mei", "Carlos", "Ashley",
              "DeShawn", "Rachel", "Hiro", "Kayla", "Luis", "Emily", "Darnell", "Sofia",
              "Grant", "Nadia", "Travis", "Aaliyah", "Wesley", "Camila", "Trevor",
              "Jasmine", "Raj", "Lauren", "Malik", "Erin", "Diego", "Brooke"),
    "it-IT": ("Giulia", "Marco", "Chiara", "Lorenzo", "Francesca", "Davide", "Elena",
              "Matteo", "Sara", "Alessio", "Martina", "Stefano", "Valentina", "Paolo",
              "Ilaria", "Riccardo", "Federica", "Simone", "Beatrice", "Andrea", "Roberta",
              "Nicola", "Silvia", "Fabio", "Anna"),
    "fr-FR": ("Camille", "Julien", "Léa", "Mathieu", "Chloé", "Antoine", "Manon", "Nicolas",
              "Inès", "Thomas", "Sarah", "Hugo", "Élodie", "Karim", "Pauline", "Romain",
              "Amina", "Guillaume", "Claire", "Yann", "Laure", "Baptiste", "Nadia",
              "Olivier", "Margaux"),
    "es-ES": ("Lucía", "Javier", "Carmen", "Pablo", "Elena", "Sergio", "Marta", "Diego",
              "Paula", "Alberto", "Nerea", "Raúl", "Irene", "Álvaro", "Rocío", "Iván",
              "Cristina", "Adrián", "Ainhoa", "Jorge"),
    "pt-PT": ("Inês", "João", "Mariana", "Tiago", "Beatriz", "Rui", "Catarina", "Miguel",
              "Sofia", "Pedro", "Leonor", "Duarte", "Rita", "Nuno", "Marta", "Gonçalo",
              "Joana", "André", "Teresa", "Diogo"),
    "pt-BR": ("Ana Clara", "Rafael", "Juliana", "Thiago", "Fernanda", "Lucas", "Camila",
              "Gabriel", "Larissa", "Matheus", "Bruna", "Felipe", "Letícia", "Gustavo",
              "Renata", "Vinícius", "Patrícia", "Rodrigo", "Aline", "Leandro"),
}

SURNAMES: dict[str, tuple[str, ...]] = {
    "en-GB": ("Thornton", "Patel", "Hughes", "Gallagher", "Pritchard", "Begum", "Llewellyn",
              "MacLeod", "Ashworth", "Kaur", "Burrows", "Sinclair", "Doherty", "Mensah",
              "Fairclough", "Rahman", "Whitaker", "Bryce", "Chowdhury", "Treloar", "Mercer",
              "Odell", "Kowalski", "Haworth", "Nwosu", "Caldwell", "Rees", "Ahmed",
              "Stirling", "Lindsay"),
    "en-US": ("Nguyen", "Kowalczyk", "Ramirez", "Holloway", "Jackson", "Brennan", "Castillo",
              "Lindqvist", "Washington", "Park", "Delgado", "Schultz", "Adeyemi",
              "Fitzgerald", "Morales", "Hendricks", "Yamamoto", "Sullivan", "Duarte",
              "Abernathy", "Le", "Gutierrez", "Pruitt", "Shapiro", "Lockhart", "Vasquez",
              "Kim", "Brandt", "Tillman", "Mahoney"),
    "it-IT": ("Ferri", "Colombo", "Esposito", "Bianchi", "Galli", "Conti", "Mancini",
              "Rinaldi", "Fontana", "Barbieri", "Caruso", "Moretti", "De Luca", "Marino",
              "Greco", "Santoro", "Ricci", "Pellegrini", "Gatti", "Testa", "Serra",
              "Vitale", "Bellini", "Orlando", "Lombardo"),
    "fr-FR": ("Lefèvre", "Moreau", "Girard", "Fournier", "Mercier", "Bonnet", "Lambert",
              "Faure", "Chevalier", "Garnier", "Leroy", "Benali", "Perrin", "Morel",
              "Gauthier", "Roussel", "Dumont", "Masson", "Nguyen", "Brunet", "Blanchard",
              "Picard", "Renaud", "Collet", "Diallo"),
    "es-ES": ("García Ortega", "Martínez Ruiz", "López Navarro", "Sánchez Molina",
              "Romero Gil", "Torres Vidal", "Domínguez Prieto", "Castro Lozano",
              "Herrera Soto", "Iglesias Marín", "Vega Cabrera", "Moreno Pastor",
              "Rubio Santos", "Medina Calvo", "Garrido León", "Ramos Serrano",
              "Delgado Cano", "Fuentes Mora", "Gallego Peña", "Nieto Ibáñez"),
    "pt-PT": ("Ferreira da Costa", "Almeida Santos", "Rodrigues Lopes", "Carvalho Pinto",
              "Sousa Martins", "Gomes Ribeiro", "Pereira Nunes", "Fernandes Matos",
              "Oliveira Rocha", "Marques Teixeira", "Cardoso Mendes", "Correia Leite",
              "Antunes Faria", "Moreira Simões", "Coelho Vieira"),
    "pt-BR": ("da Silva Moura", "Oliveira Prado", "Souza Lima", "Santos Barbosa",
              "Pereira Duarte", "Costa Nogueira", "Rodrigues Macedo", "Almeida Freitas",
              "Carvalho Rezende", "Gomes Araújo", "Ribeiro Tavares", "Martins Cordeiro",
              "Lopes Bezerra", "Rocha Fonseca", "Teixeira Brandão"),
}

PLACES: dict[str, tuple[str, ...]] = {
    "en-GB": ("Norwich", "Stockport", "Truro", "Wrexham", "Dundee", "Lancaster", "Kendal",
              "Derby", "Swindon", "Inverness", "Hereford", "Colchester", "Durham", "Bangor",
              "Carlisle", "Taunton", "Ipswich", "Perth", "Barnsley", "Lincoln", "Salisbury",
              "Aberystwyth", "Ayr", "Shrewsbury", "Newry"),
    "en-US": ("Duluth, MN", "Tacoma, WA", "Lubbock, TX", "Boise, ID", "Fresno, CA",
              "Eugene, OR", "Macon, GA", "Peoria, IL", "Billings, MT", "Erie, PA",
              "Santa Fe, NM", "Lexington, KY", "Wichita, KS", "Greenville, SC",
              "Fort Collins, CO", "Bangor, ME", "Mobile, AL", "Provo, UT", "Ithaca, NY",
              "Sioux Falls, SD", "Chattanooga, TN", "Tulsa, OK", "Madison, WI",
              "Rochester, MN", "Flagstaff, AZ"),
    "it-IT": ("Bergamo", "Parma", "Lecce", "Trento", "Perugia", "Ancona", "Udine", "Cagliari",
              "Bari", "Modena", "Ferrara", "Siena", "Pescara", "Brescia", "Novara", "Rimini",
              "Matera", "Treviso", "Cosenza", "Livorno"),
    "fr-FR": ("Rennes", "Nantes", "Grenoble", "Dijon", "Tours", "Angers", "Reims",
              "Clermont-Ferrand", "Besançon", "Poitiers", "Limoges", "Metz", "Brest",
              "Annecy", "Pau", "Nîmes", "Amiens", "Caen", "Perpignan", "La Rochelle"),
    "es-ES": ("Zaragoza", "Valladolid", "Murcia", "Córdoba", "Gijón", "Vitoria-Gasteiz",
              "Pamplona", "Salamanca", "Cáceres", "Alicante", "Burgos", "León", "Santander",
              "Granada", "Logroño", "Huesca", "Almería", "Lugo", "Toledo", "Girona"),
    "pt-PT": ("Braga", "Coimbra", "Aveiro", "Viseu", "Faro", "Leiria", "Setúbal",
              "Guimarães", "Viana do Castelo", "Covilhã", "Tomar", "Castelo Branco",
              "Portimão", "Bragança", "Beja"),
    "pt-BR": ("Curitiba", "Recife", "Belo Horizonte", "Florianópolis", "Goiânia",
              "Fortaleza", "Manaus", "Porto Alegre", "Salvador", "Campinas", "Natal",
              "Londrina", "Vitória", "Belém", "Joinville"),
}

NAME_WORDS = (
    "Acorn", "Amber", "Aspen", "Atlas", "Beacon", "Birch", "Bluebell", "Bracken", "Brook",
    "Cairn", "Canopy", "Cinder", "Clover", "Compass", "Copper", "Cormorant", "Cypress",
    "Dovetail", "Driftwood", "Ember", "Fern", "Flint", "Foxglove", "Garnet", "Granite",
    "Hawthorn", "Heron", "Indigo", "Iris", "Kestrel", "Larch", "Lattice", "Linden",
    "Lodestar", "Lumen", "Maple", "Marigold", "Meridian", "Millstone", "Moss", "Nettle",
    "Northgate", "Oakridge", "Obsidian", "Orchard", "Osprey", "Paragon", "Pebble",
    "Pinewood", "Plover", "Quarry", "Quill", "Rowan", "Saffron", "Sandpiper", "Sedge",
    "Sorrel", "Sparrow", "Spruce", "Stonecrop", "Sycamore", "Tamarisk", "Tansy", "Teasel",
    "Thistle", "Timber", "Topaz", "Umber", "Vale", "Verdigris", "Wagtail", "Walnut",
    "Willow", "Yarrow", "Zephyr", "Lark", "Gannet", "Puffin", "Merlin", "Tern", "Avocet",
    "Curlew", "Dunlin", "Fieldfare", "Goldcrest", "Linnet", "Nuthatch", "Redstart",
    "Siskin", "Basalt", "Cobalt", "Slate", "Ochre", "Russet", "Juniper", "Halcyon",
    "Keystone", "Tidewater", "Summit", "Lantern",
)


def particulars(card: Card) -> dict[str, Any]:
    """The date, people, places and name words `card` is written with."""
    locale = card.locale or "en-GB"
    rng = random.Random(f"{SEED}:{card.id}")
    when = FIRST + timedelta(days=rng.randint(0, (LAST - FIRST).days))
    given = rng.sample(GIVEN[locale], 3)
    surnames = rng.sample(SURNAMES[locale], 3)
    return {
        "date": when.isoformat(),
        "people": [f"{first} {last}" for first, last in zip(given, surnames)],
        "places": rng.sample(PLACES[locale], 2),
        "name_words": rng.sample(NAME_WORDS, 2),
    }
