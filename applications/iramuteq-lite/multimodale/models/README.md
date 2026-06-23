Dépose ici un modèle ArcFace ONNX pour la sélection manuelle de visage.

Chemins reconnus automatiquement :

- `multimodale/models/arcface.onnx`
- `multimodale/models/face_recognition_sface_2021dec.onnx`
- `multimodale/models/face_recognition_sface_2021dec_int8.onnx`

Alternative :

- définir la variable d'environnement `IRAMUTEQ_ARCFACE_MODEL` vers le fichier ONNX

Quand un de ces modèles est présent, le mode `sélection à la souris` utilise ArcFace pour la ré-identification de la personne ciblée.
