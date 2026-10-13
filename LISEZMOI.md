# iPad -> tablette graphique (USB)

L'iPad affiche l'ecran du PC et le stylet pilote Windows comme une vraie tablette graphique
(stylet Windows Ink : pression et inclinaison si l'Apple Pencil les fournit). Tout passe par le cable USB.

## Comment ca marche
- `pc/serveur.py` : capture l'ecran, l'envoie a l'iPad en JPEG, rejoue les traits avec un stylet Windows simule.
- `ios/` : app iPad "Tablette" (Swift). Elle ecoute sur le port 2345 ; le PC s'y connecte par le service USB d'Apple (iTunes).
- `.github/workflows/app-ipad.yml` : compile l'app sur un Mac de GitHub (pas besoin de Mac) -> `Tablette.ipa`.

## Installation (une fois)
1. PC : `python -m pip install -r pc/requirements.txt` (iTunes doit etre installe : c'est deja le cas).
2. Pousser ce dossier sur un depot GitHub -> onglet **Actions** -> "App iPad" -> telecharger `Tablette-ipa`.
3. Installer **Sideloadly**, brancher l'iPad, glisser `Tablette.ipa`, entrer son identifiant Apple.
4. Sur l'iPad : Reglages > General > VPN et gestion de l'appareil > faire confiance au profil.
   (iPadOS 16+ : activer aussi Reglages > Confidentialite > Mode developpeur.)

Compte Apple gratuit : l'app expire au bout de **7 jours** -> la reinstaller avec Sideloadly.

## Utilisation
1. Brancher l'iPad, ouvrir l'app Tablette.
2. Double-cliquer `lancer.bat` (ou `python pc/serveur.py`).

Options : `--ecran 1` (2e ecran), `--lister`, `--qualite 75`, `--largeur 1920`, `--fps 60`,
`--pression 0.6` (pression fixe quand le stylet n'en donne pas), `--stats`.
