"""Identité binaire SHA-256 et signature perceptuelle DCT de 63 bits."""
import hashlib

def calculer_sha256(chemin):
    empreinte = hashlib.sha256()
    with open(chemin,"rb") as flux:
        for bloc in iter(lambda: flux.read(1024*1024),b""): empreinte.update(bloc)
    return empreinte.hexdigest()

def calculer_phash(image):
    import cv2
    import numpy as np
    gris = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    coefficients = cv2.dct(cv2.resize(gris,(32,32)).astype(np.float32))[:8,:8].flatten()[1:]
    mediane = float(np.median(coefficients)); nombre = 0
    for bit in coefficients > mediane: nombre = (nombre << 1) | int(bit)
    return f"{nombre:016x}"

def distance_phash(a,b):
    return (int(a,16)^int(b,16)).bit_count()


def calculer_regions(image):
    """Comparer le cadre entier, le centre et des fenêtres qui se chevauchent."""
    hauteur, largeur = image.shape[:2]
    regions = [calculer_phash(image)]
    for fraction in (0.8, 0.6):
        h, l = round(hauteur*fraction), round(largeur*fraction)
        for y, x in ((0, 0), (0, largeur-l), (hauteur-h, 0),
                     (hauteur-h, largeur-l), ((hauteur-h)//2, (largeur-l)//2)):
            regions.append(calculer_phash(image[y:y+h, x:x+l]))
    return list(dict.fromkeys(regions))


def repartir_candidats(candidats, maximum):
    """Répartir le budget sur toute la vidéo, puis compléter par les meilleurs voisins."""
    from collections import defaultdict
    groupes=defaultdict(list)
    for i,j,distance in set(tuple(c) for c in candidats):
        groupes[i].append([i,j,distance])
    for groupe in groupes.values(): groupe.sort(key=lambda c:(c[2],c[1]))
    cles=sorted(groupes)
    if len(cles)>maximum:
        cles=[cles[round(i*(len(cles)-1)/max(1,maximum-1))] for i in range(maximum)]
    resultat=[]; rang=0
    while len(resultat)<maximum:
        ajouts=[groupes[cle][rang] for cle in cles if len(groupes[cle])>rang]
        if not ajouts: break
        resultat.extend(ajouts[:maximum-len(resultat)]); rang+=1
    return resultat


class IndexVisuel:
    """Index SQLite cloisonné par corpus ; vignettes et ORB survivent aux MP4.

    Quatre bandes de 16 bits sondées à un bit près donnent un rappel exact
    jusqu'à 7 bits de distance. Au-delà, la recherche est approximative.
    Les plafonds protègent le VPS et sont signalés au lieu de conclure à tort.
    """
    def __init__(self, chemin):
        import sqlite3
        from pathlib import Path
        Path(chemin).parent.mkdir(parents=True, exist_ok=True)
        self.base = sqlite3.connect(chemin, timeout=30)
        self.base.execute("PRAGMA journal_mode=WAL")
        self.base.executescript("""
            CREATE TABLE IF NOT EXISTS version_recherche(version INTEGER);
            CREATE TABLE IF NOT EXISTS recherches(video TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS videos(id TEXT PRIMARY KEY, sha TEXT, donnees TEXT);
            CREATE INDEX IF NOT EXISTS videos_sha ON videos(sha);
            CREATE TABLE IF NOT EXISTS images(numero INTEGER PRIMARY KEY, video TEXT,
                temps REAL, phash TEXT, regions TEXT, vignette BLOB, orb BLOB);
            CREATE INDEX IF NOT EXISTS images_video ON images(video);
            CREATE TABLE IF NOT EXISTS bandes(bande INTEGER, valeur INTEGER, image INTEGER);
            CREATE INDEX IF NOT EXISTS bandes_recherche ON bandes(bande,valeur);
            CREATE INDEX IF NOT EXISTS bandes_image ON bandes(image);
            CREATE TABLE IF NOT EXISTS semantique(video TEXT, bande INTEGER, valeur INTEGER);
            CREATE INDEX IF NOT EXISTS semantique_recherche ON semantique(bande,valeur);
            CREATE TABLE IF NOT EXISTS paires(a TEXT, b TEXT, candidats TEXT, resultat TEXT,
                PRIMARY KEY(a,b));
        """)
        # Recalculer les candidats sans perdre vignettes/ORB ni exiger les MP4 nettoyés.
        version=self.base.execute('SELECT version FROM version_recherche').fetchone()
        with self.base:
            if version != (3,):
                self.base.execute('DELETE FROM paires')
                self.base.execute('INSERT OR IGNORE INTO recherches SELECT id FROM videos')
                self.base.execute('DELETE FROM version_recherche')
                self.base.execute('INSERT INTO version_recherche VALUES(3)')
        self.tronque = False

    def fermer(self):
        self.base.close()

    def lire_video(self, identifiant):
        import json
        ligne = self.base.execute("SELECT donnees FROM videos WHERE id=?", (identifiant,)).fetchone()
        return json.loads(ligne[0]) if ligne else None

    def enregistrer_video(self, video, images):
        """Remplacer atomiquement les empreintes ; ne jamais conserver un ancien lien."""
        import cv2
        import json
        identifiant = video['id']
        with self.base:
            self.base.execute("DELETE FROM bandes WHERE image IN (SELECT numero FROM images WHERE video=?)", (identifiant,))
            self.base.execute("DELETE FROM images WHERE video=?", (identifiant,))
            self.base.execute("DELETE FROM semantique WHERE video=?", (identifiant,))
            embedding=video.get('embedding',{})
            if embedding.get('statut')=='mesure' and embedding.get('vecteur'):
                # Projections déterministes : recherche sémantique facultative sans toutes les paires.
                import numpy as np
                vecteur=np.asarray(embedding['vecteur'],dtype=np.float32)
                projections=np.random.default_rng(2026).standard_normal((4,16,len(vecteur)))
                bandes=[sum(int(bit)<<i for i,bit in enumerate(ligne)) for ligne in (projections@vecteur)>0]
                self.base.executemany("INSERT INTO semantique VALUES(?,?,?)",[(identifiant,i,b) for i,b in enumerate(bandes)])
            self.base.execute("DELETE FROM paires WHERE a=? OR b=?", (identifiant,identifiant))
            self.base.execute("INSERT OR REPLACE INTO videos VALUES(?,?,?)",
                              (identifiant,video['sha256'],json.dumps(video)))
            self.base.execute('INSERT OR IGNORE INTO recherches VALUES(?)',(identifiant,))
            for image in images:
                regions = calculer_regions(image['image'])
                succes, octets = cv2.imencode('.jpg',image['image'],[cv2.IMWRITE_JPEG_QUALITY,92])
                if not succes: raise OSError("Vignette illisible")
                numero = self.base.execute("INSERT INTO images(video,temps,phash,regions,vignette) VALUES(?,?,?,?,?)",
                    (identifiant,image['temps_s'],regions[0],json.dumps(regions),octets.tobytes())).lastrowid
                bandes = {(bande,(int(h,16) >> (16*bande)) & 65535,numero)
                          for h in regions for bande in range(4)}
                self.base.executemany("INSERT INTO bandes VALUES(?,?,?)",sorted(bandes))

    def preparer_candidats(self, identifiant, seuils, verifier=lambda: None, options=None):
        """Accumuler uniquement des paires proposées par l'index, sur disque."""
        import json
        options=options or {}
        video = self.lire_video(identifiant)
        par_paire={}
        for bande,valeur in self.base.execute("SELECT bande,valeur FROM semantique WHERE video=?",(identifiant,)).fetchall():
            valeurs=[valeur]+[valeur^(1<<i) for i in range(16)]
            lignes=self.base.execute("SELECT DISTINCT video FROM semantique WHERE bande=? AND valeur IN ("+
                ','.join('?'*len(valeurs))+") AND video<>? LIMIT 65",(bande,*valeurs,identifiant)).fetchall()
            if len(lignes)>64: self.tronque=True
            for (autre,) in lignes[:64]:
                self.base.execute("INSERT OR IGNORE INTO paires(a,b,candidats) VALUES(?,?,?)",(*sorted((identifiant,autre)),'[]'))
        # L'identité binaire ne dépend pas de la richesse visuelle du fichier.
        for (autre,) in self.base.execute("SELECT id FROM videos WHERE sha=? AND id<>? ORDER BY id LIMIT 1", (video['sha256'],identifiant)).fetchall():
            self.base.execute("INSERT OR IGNORE INTO paires(a,b,candidats) VALUES(?,?,?)", (*sorted((identifiant,autre)), '[]'))
        for numero, temps, regions in self.base.execute("SELECT numero,temps,regions FROM images WHERE video=?", (identifiant,)).fetchall():
            verifier()
            regions = json.loads(regions)
            voisins = set()
            for h in regions:
                for bande in range(4):
                    valeur = (int(h,16) >> (16*bande)) & 65535
                    valeurs = [valeur] + [valeur ^ (1 << bit) for bit in range(16)]
                    lignes = self.base.execute("SELECT DISTINCT bandes.image FROM bandes JOIN images ON images.numero=bandes.image WHERE bande=? AND valeur IN ("+
                        ','.join('?'*len(valeurs))+") AND images.video<>? ORDER BY bandes.image LIMIT 257", (bande,*valeurs,identifiant)).fetchall()
                    if len(lignes)>256: self.tronque = True
                    voisins.update(v[0] for v in lignes[:256])
            meilleurs = []
            for voisin in sorted(voisins):
                autre, t, empreintes = self.base.execute("SELECT video,temps,regions FROM images WHERE numero=?",(voisin,)).fetchone()
                if autre == identifiant: continue
                if options.get('comparer_sha256',True) and self.lire_video(autre)['sha256']==video['sha256']: continue
                distance = min(distance_phash(a,b) for a in regions for b in json.loads(empreintes))
                if distance <= seuils['distance_phash']: meilleurs.append((distance,autre,t,voisin))
            # Alterner les publications avant de compléter : une longue vidéo ne
            # doit pas consommer les 64 places réservées aux voisins d'une image.
            meilleurs.sort()
            par_video={}
            for candidat in meilleurs: par_video.setdefault(candidat[1],[]).append(candidat)
            equilibres=[]; rang=0
            while len(equilibres)<64:
                ajouts=[g[rang] for g in par_video.values() if len(g)>rang]
                if not ajouts: break
                equilibres.extend(ajouts[:64-len(equilibres)]); rang+=1
            if len(meilleurs)>64: self.tronque = True
            for distance, autre, t, voisin in equilibres:
                a,b = sorted((identifiant,autre))
                couple = [numero,voisin,distance] if a==identifiant else [voisin,numero,distance]
                par_paire.setdefault((a,b),[]).append(couple)
        for (a,b),candidats in par_paire.items():
            ligne=self.base.execute('SELECT candidats FROM paires WHERE a=? AND b=?',(a,b)).fetchone()
            precedents=json.loads(ligne[0]) if ligne else []
            ensemble={tuple(c) for c in precedents+candidats}
            if len(ensemble)>seuils['paires_orb_max']: self.tronque=True
            retenus=repartir_candidats(ensemble,seuils['paires_orb_max'])
            # Les candidats sont choisis APRÈS toute la vidéo, pas sur son début seul.
            if {tuple(c) for c in retenus}!={tuple(c) for c in precedents}:
                self.base.execute('INSERT OR REPLACE INTO paires VALUES(?,?,?,NULL)',(a,b,json.dumps(retenus)))
        self.base.execute('DELETE FROM recherches WHERE video=?',(identifiant,))
        self.base.commit()

    def lire_image(self, numero):
        """Calculer ORB une seule fois, puis relire son cache compressé."""
        import cv2
        import numpy as np
        import json
        import zlib
        from .comparaison_orb import extraire_orb
        temps, phash, vignette, orb = self.base.execute("SELECT temps,phash,vignette,orb FROM images WHERE numero=?",(numero,)).fetchone()
        if orb is None:
            descripteurs = extraire_orb(cv2.imdecode(np.frombuffer(vignette,dtype=np.uint8),cv2.IMREAD_COLOR))
            orb = zlib.compress(json.dumps(descripteurs).encode())
            with self.base: self.base.execute("UPDATE images SET orb=? WHERE numero=?",(orb,numero))
        else: descripteurs = json.loads(zlib.decompress(orb))
        return {'temps_s':temps,'phash':phash,'orb':descripteurs}

    def liens(self):
        """Ne charger que les preuves positives, jamais tous les descripteurs."""
        import json
        from .groupes_visuels import TYPES_REEMPLOI
        for (resultat,) in self.base.execute("SELECT resultat FROM paires WHERE resultat IS NOT NULL ORDER BY a,b"):
            valeur = json.loads(resultat)
            if valeur['type'] in TYPES_REEMPLOI or valeur.get('semantiquement_similaires'): yield valeur


class IndexDino:
    """Index privé inter-lots : SQLite durable et FAISS HNSW dérivé, sans MP4 requis."""
    def __init__(self, dossier, threads=1):
        import sqlite3
        import fcntl
        from pathlib import Path
        self.dossier=Path(dossier); self.dossier.mkdir(parents=True,exist_ok=True)
        # Deux analyses d'un même propriétaire ne doivent pas réécrire l'index ensemble.
        self.verrou=(self.dossier/'index.lock').open('w')
        try: fcntl.flock(self.verrou,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.verrou.close(); raise RuntimeError('Une autre analyse DINOv2 utilise cet index ; réessayez après sa fin.')
        self.base=sqlite3.connect(self.dossier/'images.sqlite',timeout=30)
        self.base.executescript('''
            CREATE TABLE IF NOT EXISTS images(id INTEGER PRIMARY KEY AUTOINCREMENT, video TEXT,
              temps REAL, vecteur BLOB, vignette BLOB, phash TEXT);
            CREATE INDEX IF NOT EXISTS images_video ON images(video);
            CREATE TABLE IF NOT EXISTS videos(id TEXT PRIMARY KEY, donnees TEXT);
            CREATE TABLE IF NOT EXISTS revision(valeur INTEGER);
            INSERT INTO revision SELECT 0 WHERE NOT EXISTS(SELECT 1 FROM revision);
        ''')
        self.threads=threads; self.index=None

    def fermer(self):
        self.base.close(); self.verrou.close()

    def enregistrer(self, video, images, embeddings):
        """Remplacer les images d'une publication atomiquement, sans conserver de doublons."""
        import json
        import cv2
        import numpy as np
        if len(images)!=len(embeddings): raise ValueError('Nombre incohérent d’images DINOv2.')
        with self.base:
            self.base.execute('DELETE FROM images WHERE video=?',(video['id'],))
            self.base.execute('INSERT OR REPLACE INTO videos VALUES(?,?)',(video['id'],json.dumps(video)))
            for image,embedding in zip(images,embeddings):
                vecteur=np.asarray(embedding['vecteur'],dtype='float32')
                if vecteur.shape!=(384,) or not np.isfinite(vecteur).all() or np.linalg.norm(vecteur)==0:
                    raise ValueError('Embedding DINOv2 invalide.')
                vecteur/=np.linalg.norm(vecteur)
                miniature=image['image']; h,w=miniature.shape[:2]
                miniature=cv2.resize(miniature,(max(1,round(w*min(1,224/max(h,w)))),max(1,round(h*min(1,224/max(h,w))))))
                succes,jpeg=cv2.imencode('.jpg',miniature,[cv2.IMWRITE_JPEG_QUALITY,80])
                if not succes: raise ValueError('Miniature DINOv2 illisible.')
                self.base.execute('INSERT INTO images(video,temps,vecteur,vignette,phash) VALUES(?,?,?,?,?)',
                    (video['id'],embedding['temps_s'],vecteur.tobytes(),jpeg.tobytes(),calculer_phash(image['image'])))
            self.base.execute('UPDATE revision SET valeur=valeur+1')
        self.index=None

    def contient(self, identifiant, sha):
        import json
        ligne=self.base.execute('SELECT donnees FROM videos WHERE id=?',(identifiant,)).fetchone()
        return bool(ligne and json.loads(ligne[0]).get('sha256')==sha)

    def preparer(self, verifier=lambda:None):
        """Reconstruire par blocs si nécessaire ; ne jamais charger toutes les vignettes."""
        import faiss
        import numpy as np
        import os
        faiss.omp_set_num_threads(self.threads)
        revision=str(self.base.execute('SELECT valeur FROM revision').fetchone()[0])
        chemin=self.dossier/'index.faiss'; marqueur=self.dossier/'revision.txt'
        if chemin.exists() and marqueur.exists() and marqueur.read_text()==revision:
            try:
                self.index=faiss.read_index(str(chemin)); return
            except RuntimeError: pass
        graphe=faiss.IndexHNSWFlat(384,32,faiss.METRIC_INNER_PRODUCT)
        graphe.hnsw.efConstruction=80; graphe.hnsw.efSearch=128
        self.index=faiss.IndexIDMap2(graphe)
        curseur=self.base.execute('SELECT id,vecteur FROM images ORDER BY id')
        while True:
            lignes=curseur.fetchmany(256)
            if not lignes: break
            verifier()
            self.index.add_with_ids(np.stack([np.frombuffer(v,dtype='float32') for _,v in lignes]),np.array([i for i,_ in lignes],dtype='int64'))
        temporaire=self.dossier/'index.tmp'
        faiss.write_index(self.index,str(temporaire)); os.replace(temporaire,chemin)
        temporaire=self.dossier/'revision.tmp'; temporaire.write_text(revision); os.replace(temporaire,marqueur)

    def rechercher(self, identifiant, verifier=lambda:None):
        """Dix autres publications, sans seuil ; davantage de voisins si une vidéo domine."""
        import numpy as np
        import json
        if self.index is None: self.preparer(verifier)
        videos={i:json.loads(d) for i,d in self.base.execute('SELECT id,donnees FROM videos')}
        if identifiant not in videos: return []
        objectif=min(10,len(videos)-1); correspondances={}
        if objectif<=0: return []
        for numero,temps,vecteur,phash in self.base.execute('SELECT id,temps,vecteur,phash FROM images WHERE video=? ORDER BY temps',(identifiant,)):
            verifier(); k=min(self.index.ntotal,128)
            while k:
                scores,ids=self.index.search(np.frombuffer(vecteur,dtype='float32').reshape(1,-1),k)
                voisins={}
                for score,autre in zip(scores[0],ids[0]):
                    if autre<0: continue
                    ligne=self.base.execute('SELECT video,temps,phash FROM images WHERE id=?',(int(autre),)).fetchone()
                    if not ligne or ligne[0]==identifiant: continue
                    video,t,h=ligne
                    if video not in voisins:
                        voisins[video]={'image_a':numero,'image_b':int(autre),'temps_a':temps,'temps_b':t,
                            'score':max(-1.,min(1.,float(score))),'phash_a':phash,'phash_b':h}
                if len(voisins)>=objectif or k==self.index.ntotal: break
                k=min(self.index.ntotal,k*2)
            for video,mesure in voisins.items(): correspondances.setdefault(video,[]).append(mesure)
        resultats=[]
        for autre,mesures in correspondances.items():
            meilleure=max(mesures,key=lambda m:m['score'])
            resultats.append({'a':identifiant,'b':autre,'url_a':videos[identifiant].get('url'),'url_b':videos[autre].get('url'),
                'score':meilleure['score'],'meilleure':meilleure,'correspondances':mesures,'preuve_reemploi':False})
        return sorted(resultats,key=lambda r:(-r['score'],r['b']))[:10]

    def miniature(self, numero):
        ligne=self.base.execute('SELECT vignette FROM images WHERE id=?',(numero,)).fetchone()
        return ligne[0] if ligne else None

    def comparer_lot(self, identifiant, publications, verifier=lambda:None):
        """Comparer toutes les paires d'un petit lot, une vidéo cible à la fois."""
        import json
        import numpy as np
        if len(publications)>50: raise ValueError('Comparaison exhaustive limitée à 50 publications.')
        def images(video):
            return self.base.execute('SELECT id,temps,vecteur,phash FROM images WHERE video=? ORDER BY temps',(video,)).fetchall()
        source=images(identifiant)
        if not source:return []
        matrice=np.stack([np.frombuffer(r[2],dtype='float32') for r in source])
        meta=self.base.execute('SELECT donnees FROM videos WHERE id=?',(identifiant,)).fetchone()
        resultat=[]
        for autre in sorted(set(publications)-{identifiant}):
            verifier(); cible=images(autre)
            if not cible:continue
            # Seule la petite matrice d'une paire vidéo est conservée en mémoire.
            scores=matrice@np.stack([np.frombuffer(r[2],dtype='float32') for r in cible]).T
            correspondances=[]
            for i,j in enumerate(scores.argmax(axis=1)):
                a,b=source[i],cible[j]
                correspondances.append({'image_a':a[0],'image_b':b[0],'temps_a':a[1],'temps_b':b[1],
                    'phash_a':a[3],'phash_b':b[3],'score':max(-1.,min(1.,float(scores[i,j])))})
            meilleure=max(correspondances,key=lambda c:c['score'])
            voisin=json.loads(self.base.execute('SELECT donnees FROM videos WHERE id=?',(autre,)).fetchone()[0])
            resultat.append({'a':identifiant,'b':autre,'url_a':json.loads(meta[0]).get('url'),'url_b':voisin.get('url'),
                'score':meilleure['score'],'meilleure':meilleure,'correspondances':correspondances,'preuve_reemploi':False})
        return resultat
