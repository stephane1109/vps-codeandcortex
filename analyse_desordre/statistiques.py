"""Spearman au niveau publication, permutations et correction des comparaisons multiples."""
import itertools
import math
import numpy as np
from scipy.stats import rankdata
from .indice import INDICATEURS
from .engagement import VARIABLES_ENGAGEMENT


def correlation_spearman(x,y,permutations=1999,graine=42):
    """Test bilatéral exact jusqu'à sept observations, Monte-Carlo au-delà, ex aequo conservés."""
    x=np.asarray(x,float);y=np.asarray(y,float)
    presents=np.isfinite(x)&np.isfinite(y);x=x[presents];y=y[presents];n=len(x)
    base={'n':n,'rho':None,'p':None,'methode':'indisponible','permutations':0}
    if n<3: return {**base,'raison':'moins_de_trois_publications'}
    a=rankdata(x);b=rankdata(y);a-=a.mean();b-=b.mean()
    denominateur=np.linalg.norm(a)*np.linalg.norm(b)
    if denominateur==0: return {**base,'raison':'indicateur_constant'}
    rho=float(np.clip(a@b/denominateur,-1,1));extremes=0
    if n<=7:
        tirages=itertools.permutations(range(n));total=math.factorial(n);methode='permutation_exacte'
    else:
        hasard=np.random.default_rng(graine)
        tirages=(hasard.permutation(n) for _ in range(permutations));total=permutations;methode='permutation_monte_carlo'
    for ordre in tirages:
        valeur=float(a@b[list(ordre)]/denominateur)
        extremes+=abs(valeur)>=abs(rho)-1e-12
    probabilite=extremes/total if n<=7 else (extremes+1)/(total+1)
    return {'n':n,'rho':rho,'p':probabilite,'methode':methode,'permutations':total,'raison':''}


def calculer_correlations(tableau,parametres):
    """Une ligne par publication ; exclusion paire par paire des données manquantes."""
    resultat=[]
    for indicateur in INDICATEURS:
        for taux in VARIABLES_ENGAGEMENT:
            resultat.append({'indicateur':indicateur,'engagement':taux,
                **correlation_spearman(tableau[indicateur],tableau[taux],parametres.permutations,parametres.graine)})
    valides=sorted((i for i,r in enumerate(resultat) if r['p'] is not None),key=lambda i:resultat[i]['p'])
    minimum=1.
    for rang in range(len(valides),0,-1):
        i=valides[rang-1];minimum=min(minimum,resultat[i]['p']*len(valides)/rang)
        resultat[i]['p_ajustee_bh']=minimum
    return resultat
