# Aide DetectIA vidéo

DetectIA analyse les incohérences temporelles d'une vidéo à partir du flux optique.

## Principe

Une vidéo réelle présente généralement une continuité physique du mouvement : trajectoires, inertie, flou de mouvement, occlusions et arrière-plan restent cohérents. Une vidéo générée ou fortement manipulée peut produire des détails instables, des textures flottantes, des objets qui se déforment ou des ruptures de mouvement.

## Ce que mesure l'application

- Optical flow : mouvement apparent entre deux frames.
- Résidu temporel : différence restante après compensation du mouvement.
- Flicker : variation brutale d'intensité entre frames.
- Jerk : rupture ou accélération anormale du mouvement.
- Frames suspectes : instants où plusieurs signaux sont élevés.

## Interprétation

Le score n'est pas une preuve. Il sert à prioriser une vérification humaine.

Un score élevé peut venir de :

- vidéo générée par IA ;
- forte compression ;
- montage rapide ;
- stabilisation logicielle ;
- ralenti ou interpolation ;
- faible luminosité ;
- mauvaise qualité de source.
