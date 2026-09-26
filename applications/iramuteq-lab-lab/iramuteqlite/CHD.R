#Author: Pierre Ratinaud
#Copyright (c) 2008-2020 Pierre Ratinaud
#License: GNU/GPL

pp<-function(txt,val) {
	d<-paste(txt,' : ')
	print(paste(d,val))
}
MyChiSq<-function(x,sc,n){
	sr<-rowSums(x)
	E <- outer(sr, sc, "*")/n
	STAT<-sum(((x - E)^2)/E)
	STAT
}

MySpeedChi <- function(x,sc) {
    sr <-rowSums(x)
    E <- outer(sr, sc, "*")
	STAT<-sum((x - E)^2/E)
	STAT
}

find.max <- function(dtable, chitable, compte, rmax, maxinter, sc, TT) {
    ln <- which(dtable==1, arr.ind=TRUE)
    lo <- list()
    lo[1:nrow(dtable)] <- 0
    for (k in 1:nrow(ln)) {lo[[ln[k,1]]]<-append(lo[[ln[k,1]]],ln[k,2])}
    for (k in 1:nrow(dtable)) {lo[[k]] <- lo[[k]][-1]}
	## lo<-lo[-c(1,length(lo))]
	## for (l in lo) {
	##     compte <- compte + 1 
	##     chitable[1,l]<-chitable[1,l]+1
	##     chitable[2,l]<-chitable[2,l]-1
	##     chi<-MyChiSq(chitable,sc,TT)
		## if (chi>maxinter) {
		##     maxinter<-chi
		##     rmax<-compte
		## }   
    #}
	lo<-lo[-c(1)]
	for (l in lo) {
		chi<-MyChiSq(chitable,sc,TT)
		if (chi>maxinter) {
			maxinter<-chi
			rmax<-compte
		}
		compte <- compte + 1
		chitable[1,l]<-chitable[1,l]+1
		chitable[2,l]<-chitable[2,l]-1
	}	
    res <- list(maxinter=maxinter, rmax=rmax)
    res
}  





CHD<-function(data.in, x=9, mode.patate = FALSE, svd.method, libsvdc.path=NULL){
#	sink('/home/pierre/workspace/iramuteq/dev/findchi2.txt')
	dataori <- data.in
    row.names(dataori) <- rownames(data.in)
	dtable <- data.in
	colnames(dtable) <- 1:ncol(dtable)
    dout <- NULL
	rowelim<-NULL
	pp('ncol entree : ',ncol(dtable))
	pp('nrow entree',nrow(dtable))
	listcol <- list()
	listmere <- list()
	list_fille <- list()
	print('vire colonnes vides en entree')#FIXME : il ne doit pas y avoir de colonnes vides en entree !!
	sdt<-colSums(dtable)
	if (min(sdt)==0)
		dtable<-dtable[,-which(sdt==0)]
    print('vire lignes vides en entree')
    sdt<-rowSums(dtable)
	if (min(sdt)==0) {
        rowelim<-as.integer(rownames(dtable)[which(sdt==0)])
        print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
        print(rowelim)
        print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
		dtable<-dtable[-which(sdt==0),]
	}
	mere<-1
	for (i in 1:x) {
		clnb<-(i*2)
		listmere[[clnb]]<-mere
		listmere[[clnb+1]]<-mere
		list_fille[[mere]] <- c(clnb,clnb+1)
		listcol[[clnb]]<-vector()
		listcol[[clnb+1]]<-vector()
		#extraction du premier facteur de l'afc
		print('afc')
		pp('taille dtable dans boucle (col/row)',c(ncol(dtable),nrow(dtable)))
		afc<-boostana(dtable, nd=1, svd.method = svd.method, libsvdc.path=libsvdc.path)
		pp('SV',afc$singular.values)
		pp('V.P.', afc$eigen.values)
		coordrow <- as.matrix(afc$row.scores[,1])
		coordrowori<-coordrow
		row.names(coordrow)<-rownames(dtable)
        coordrow <- cbind(coordrow,1:nrow(dtable))
		print('deb recherche meilleur partition')
        ordert <- as.matrix(coordrow[order(coordrow[,1]),])
        ordert <- cbind(ordert, 1:nrow(ordert))
        ordert <- ordert[order(ordert[,2]),]

		listinter<-vector()
		listlim<-vector()
        dtable <- dtable[order(ordert[,3]),]
        sc <- colSums(dtable)
        TT <- sum(sc)
        sc1 <- dtable[1,]
        sc2 <- colSums(dtable) - sc1 
        chitable <- rbind(sc1, sc2)
        compte <- 1
        maxinter <- 0
        rmax <- NULL

        inert <- find.max(dtable, chitable, compte, rmax, maxinter, sc, TT)
        print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@')
		pp('max inter phase 1', inert$maxinter/TT)#max(listinter))
		print('@@@@@@@@@@@@@@@@@@@@@@@@@@@@')
        ordert <- ordert[order(ordert[,3]),]
		listclasse<-ifelse(coordrowori<=ordert[(inert$rmax),1],clnb,clnb+1)
	    dtable <- dtable[order(ordert[,2]),]
		cl<-listclasse
		pp('TT',TT)
		#dtable<-cbind(dtable,'cl'= as.vector(cl))

		N1<-length(listclasse[listclasse==clnb])
		N2<-length(listclasse[listclasse==clnb+1])
		pp('N1',N1)
		pp('N2',N2)
###################################################################
#                  reclassement des individus                     #
###################################################################
        if (!mode.patate) {
    		malcl<-1000000000000
    		it<-0
    		listsub<-list()
    		#in boucle
            ln <- which(dtable==1, arr.ind=TRUE)
            lnz <- list()
            lnz[1:nrow(dtable)] <- 0
    
            for (k in 1:nrow(ln)) {lnz[[ln[k,1]]]<-append(lnz[[ln[k,1]]],ln[k,2])}
            for (k in 1:nrow(dtable)) {lnz[[k]] <- lnz[[k]][-1]}
    		TT<-sum(dtable)
    
    		while (malcl!=0 & N1>=5 & N2>=5) {
    			it<-it+1
    			listsub[[it]]<-vector()
                txt <- paste('nombre iteration', it)
    			#pp('nombre iteration',it)
    			vdelta<-vector()
    			#dtable[,'cl']<-cl
    			t1<-dtable[which(cl[,1]==clnb),]#[,-ncol(dtable)]
    			t2<-dtable[which(cl[,1]==clnb+1),]#[,-ncol(dtable)]
    			ncolt<-ncol(t1)
    			#pp('ncolt',ncolt)
    
                if (N1 != 1) {
                    sc1<-colSums(t1)
                } else {
                    sc1 <- t1
                }
                if (N2 != 1) {
    			    sc2<-colSums(t2)
                } else {
                    sc2 <- t2
                }
    			
                sc<-sc1+sc2
    			chtableori<-rbind(sc1,sc2)
    			chtable<-chtableori
    			interori<-MyChiSq(chtableori,sc,TT)/TT#chisq.test(chtableori)$statistic#/TT
    			txt <- paste(txt, ' - interori : ',interori)
                #pp('interori',interori)
    
    			N1<-nrow(t1)
    			N2<-nrow(t2)
    
    			#pp('N1',N1)
    			#pp('N2',N2)
    			txt <- paste(txt, 'N1:', N1,'-N2:',N2)
                print(txt)
                compte <- 0
    			for (l in lnz){
                        chi.in<-chtable
                        compte <- compte + 1
    					if(cl[compte]==clnb){
    						chtable[1,l]<-chtable[1,l]-1
    						chtable[2,l]<-chtable[2,l]+1
    					}else{
    						chtable[1,l]<-chtable[1,l]+1
    						chtable[2,l]<-chtable[2,l]-1
    					}
    					interswitch<-MyChiSq(chtable,sc,TT)/TT#chisq.test(chtable)$statistic/TT
    					ws<-interori-interswitch
    
    					if (ws<0){
    						interori<-interswitch
    						if(cl[compte]==clnb){
    							#sc1<-chtable[1,]
    							#sc2<-chtable[2,]
    							cl[compte]<-clnb+1
    							listsub[[it]]<-append(listsub[[it]],compte)
    						} else {
    							#sc1<-chtable[1,]
    							#sc2<-chtable[2,]
    							cl[compte]<-clnb
    							listsub[[it]]<-append(listsub[[it]],compte)
    						}
    						vdelta<-append(vdelta,compte)
                        } else {
                            chtable<-chi.in
    					}
                   }
    #			for (val in vdelta) {
    #				if (cl[val]==clnb) {
    #					cl[val]<-clnb+1
    #					listsub[[it]]<-append(listsub[[it]],val)
    #					}else {
    #					cl[val]<-clnb
    #					listsub[[it]]<-append(listsub[[it]],val)
    #				}
    #			}
    			print('###################################')
    			print('longueur < 0')
    			malcl<-length(vdelta)

    			if ((it>1)&&(!is.logical(listsub[[it]]))&&(!is.logical(listsub[[it-1]]))){
    				if (all(listsub[[it]]==listsub[[(it-1)]])){
    					malcl<-0
    				}
    			}
    			print(malcl)
    			print('###################################')
    		}
        }
		#dtable<-cbind(dtable,'cl'=as.vector(cl))
        #dtable[,'cl'] <-as.vector(cl)
#######################################################################
#                 Fin reclassement des individus                      #
#######################################################################
#		if (!(length(cl[cl==clnb])==1 || length(cl[cl==clnb+1])==1)) {
			#t1<-dtable[dtable[,'cl']==clnb,][,-ncol(dtable)]
			#t2<-dtable[dtable[,'cl']==clnb+1,][,-ncol(dtable)]
		    t1<-dtable[which(cl[,1]==clnb),]#[,-ncol(dtable)]
			t2<-dtable[which(cl[,1]==clnb+1),]#[,-ncol(dtable)]
            if (inherits(t1, "numeric")) {
                sc1 <- as.vector(t1)
                nrowt1 <- 1
            } else {
                sc1 <- colSums(t1)
                nrowt1 <- nrow(t1)
            }
            if  (inherits(t2, "numeric")) {
                sc2 <- as.vector(t2)
                nrowt2 <- 1
            } else {
                sc2 <- colSums(t2)
                nrowt2 <- nrow(t2)
            }
            chtable<-rbind(sc1,sc2)
			inter<-chisq.test(chtable)$statistic/TT
			pp('last inter',inter)
			print('=====================')
			#calcul de la specificite des colonnes
			mint<-min(nrowt1,nrowt2)
			maxt<-max(nrowt1,nrowt2)
			seuil<-round((1.9*(maxt/mint))+1.9,digit=6)
			#sink('/home/pierre/workspace/iramuteq/dev/findchi2.txt')
#			print('ATTENTION SEUIL 3,84')
#			seuil<-3.84
			pp('seuil',seuil)
			sominf<-0
			nv<-0
			nz<-0
			ncclnb<-0
			ncclnbp<-0
            NN1<-0
            NN2<-0
            maxchip<-0
            nbzeroun<-0
            res1<-0
            res2<-0
            nbseuil<-0
            nbexe<-0
            nbcontrib<-0
			cn<-colnames(dtable)
            #another try#########################################
            one <- cbind(sc1,sc2)
            cols <- c(length(which(cl==clnb)), length(which(cl==clnb+1))) 
            print(cols)
            colss <- matrix(rep(cols,ncol(dtable)), ncol=2, byrow=TRUE)
            zero <- colss - one
            rows <- cbind(rowSums(zero), rowSums(one))
            n <- sum(cols)
            for (m in 1:nrow(rows)) {
                obs <- t(matrix(c(zero[m,],one[m,]),2,2))
                E <- outer(rows[m,],cols,'*')/n
                if ((min(obs[2,])==0) & (min(obs[1,])!=0)) {
                    chi <- seuil + 1
                } else if ((min(obs[1,])==0) & (min(obs[2,])!=0)) {
                    chi <- seuil - 1
                } else if (any(obs < 10)) {
                    chi <- sum((abs(obs - E) - 0.5)^2 / E)
                } else {
                    chi <- sum(((obs - E)^2)/E)
                }
                if (is.na(chi)) {
                    chi <- 0
                }
                if (chi > seuil) {
                    if (obs[2,1] < E[2,1]) {
                        listcol[[clnb]]<-append(listcol[[clnb]],cn[m])
                        ncclnb<-ncclnb+1
                    } else if (obs[2,2] < E[2,2]) {
						listcol[[clnb+1]]<-append(listcol[[clnb+1]],cn[m])
						ncclnbp<-ncclnbp+1
                    }
                }
            }
            ######################################################
			print('resultats elim item')
			pp(clnb+1,length(listcol[[clnb+1]]))
			pp(clnb,length(listcol[[clnb]]))
			pp('ncclnb',ncclnb)
			pp('ncclnbp',ncclnbp)
			listrownamedtable<-rownames(dtable)
			listrownamedtable<-as.integer(listrownamedtable)
			newcol<-vector(length=nrow(dataori))
			#remplissage de la nouvelle colonne avec les nouvelles classes
			print('remplissage')
#			num<-0
            newcol[listrownamedtable] <- cl[,1]
			#recuperation de la classe precedante pour les cases vides
			print('recuperation classes precedentes')
            if (i!=1) {
                newcol[which(newcol==0)] <- dout[,ncol(dout)][which(newcol==0)]
            }
            if(!is.null(rowelim)) {
                newcol[rowelim] <- 0
            }
			tailleclasse<-as.matrix(summary(as.factor(as.character(newcol))))
			print('tailleclasse')
			print(tailleclasse)
			tailleclasse<-as.matrix(tailleclasse[!(rownames(tailleclasse)==0),])
			plusgrand<-which.max(tailleclasse)
			#???????????????????????????????????
			#Si 2 classes ont des effectifs egaux, on prend la premiere de la liste...
			if (length(plusgrand)>1) {
				plusgrand<-plusgrand[1]
			}
			#????????????????????????????????????
			
			#constuction du prochain tableau a analyser
			print('construction tableau suivant')
            dout<-cbind(dout,newcol)
			classe<-as.integer(rownames(tailleclasse)[plusgrand])
			dtable<-dataori[which(newcol==classe),]
			row.names(dtable)<-rownames(dataori)[which(newcol==classe)]
            colnames(dtable) <- 1:ncol(dtable)
			mere<-classe
			listcolelim<-listcol[[as.integer(classe)]]
			mother<-listmere[[as.integer(classe)]]
			while (mother!=1) {
				listcolelim<-append(listcolelim,listcol[[mother]])
				mother<-listmere[[mother]]
			}
			
			listcolelim<-sort(unique(listcolelim))
			pp('avant',ncol(dtable))
			if (!is.logical(listcolelim)){
				print('elimination colonne')
				#dtable<-dtable[,-listcolelim]
                dtable<-dtable[,!(colnames(dtable) %in% listcolelim)]
			}
			pp('apres',ncol(dtable))
			#elimination des colonnes ne contenant que des 0
			print('vire colonne inf 3 dans boucle')
			sdt<-colSums(dtable)
			if (min(sdt)<=3)
				dtable<-dtable[,-which(sdt<=3)]
	
			#elimination des lignes ne contenant que des 0
			print('vire ligne vide dans boucle')
			if (ncol(dtable)==1) {
				sdt<-dtable[,1]
			} else {
				sdt<-rowSums(dtable)
			}
			if (min(sdt)==0) {
				rowelim<-as.integer(rownames(dtable)[which(sdt==0)])
				print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
				print(rowelim)
				print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
				dtable<-dtable[-which(sdt==0),]
			}
#		}
	}
#	sink()
	res <- list(n1 = dout, list_mere = listmere, list_fille = list_fille)
	res
}
