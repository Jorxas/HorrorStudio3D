// Langue des textes à l'image (enseignes, panneaux). Les noms internes restent en anglais
// (le code des films s'en sert pour retrouver les bâtiments) ; seul l'affichage change.
// Choix : ?lang=fr dans l'URL de la page, ou window.LANG avant le chargement.
const params = new URLSearchParams(location.search);
export const LANG = (params.get('lang') || window.LANG || 'en').toLowerCase();

const DICT = {
  fr: {
    'BAKERY': 'BOULANGERIE', 'DELI': 'TRAITEUR', 'SPORTS': 'SPORTS', 'CANDY': 'CONFISERIE',
    'MUSIC': 'MUSIQUE', 'COMICS': 'BD', 'GAMES': 'JEUX', 'NEWS': 'PRESSE', 'FRUIT': 'PRIMEUR',
    'PHARMACY': 'PHARMACIE', 'SOAP': 'SAVONS', 'BOOKS': 'LIBRAIRIE', 'TOYS': 'JOUETS', 'CAFE': 'CAFÉ',
    'FLOWERS': 'FLEURISTE', 'SHOES': 'CHAUSSURES', 'HATS': 'CHAPEAUX', 'TEA': 'SALON DE THÉ',
    'GIFTS': 'CADEAUX', 'BANK': 'BANQUE', 'POST': 'POSTE', 'DINER': 'BRASSERIE',
    'CORNER MARKET': 'ÉPICERIE DU COIN', 'TOWN LIMIT': 'LIMITE DE LA VILLE', 'SUBSCRIBE': 'ABONNE-TOI',
  },
};

// Remplacements ponctuels : window.SIGN_OVERRIDES = { 'TOWN LIMIT': '…' } (ex. pour coller au script).
export function label(name) {
  const o = window.SIGN_OVERRIDES && window.SIGN_OVERRIDES[name];
  if (o) return o;
  return (DICT[LANG] && DICT[LANG][name]) || name;
}
