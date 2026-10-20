"""Graphiques non interactifs exportables, sans serveur graphique ni interface principale."""
from .indice import INDICATEURS
from .engagement import TAUX


def tracer_engagements(tableau,correlations,dossier):
    """Nuages de points bruts, effectifs et corrélations ; aucun lien causal suggéré."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    from .presentation import formater_nombre
    for indicateur in INDICATEURS:
        figure,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
        for axe,taux in zip(axes,TAUX):
            valeurs=tableau[[indicateur,taux]].dropna()
            axe.scatter(valeurs[indicateur],valeurs[taux],s=18,alpha=.65)
            mesure=next(r for r in correlations if r['indicateur']==indicateur and r['engagement']==taux)
            texte=f"n = {mesure['n']}"
            if mesure['rho'] is not None: texte+=f" ; ρ = {mesure['rho']:.3f} ; p = {mesure['p']:.3g}"
            else: texte+=' ; corrélation non calculable'
            axe.set(title=texte,xlabel=indicateur.replace('_',' '),ylabel=taux.replace('_',' '))
            axe.xaxis.set_major_formatter(FuncFormatter(lambda valeur,position:formater_nombre(valeur)))
            axe.yaxis.set_major_formatter(FuncFormatter(lambda valeur,position:formater_nombre(valeur)))
            axe.grid(alpha=.2)
        figure.suptitle('Désordre visuel et engagement — analyse exploratoire')
        figure.savefig(dossier/(indicateur+'.png'),dpi=140);plt.close(figure)
