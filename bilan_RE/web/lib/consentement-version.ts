/**
 * Version du texte de consentement en vigueur — EXEMPLAIRE UNIQUE.
 *
 * Fichier minuscule et sans dependance exprès : le bandeau (navigateur) et la
 * base (serveur) doivent lire la MEME valeur. Recopiee des deux cotes, elle
 * aurait derive, et un consentement aurait porte sur un texte que personne ne
 * sait retrouver.
 *
 * A INCREMENTER quand le texte change : un consentement porte sur un texte
 * precis. Le bandeau se reaffiche alors a tout le monde, et c'est voulu.
 */
export const VERSION_CONSENTEMENT = "2026-10-19";
