#from proxy package
#############################################################
#a, b, c, and d are the counts of all (TRUE, TRUE), (TRUE, FALSE), (FALSE, TRUE), and (FALSE, FALSE)
# n <- a + b + c + d = nrow(x)

make.a <- function(x) {
    a  <- t(x) %*% (x)
    a
}

make.b <- function(x) {
    b <- t(x) %*% (1 - x)
    b
}

make.c <- function(x) {
    c <- (1-t(x)) %*% x
    c
}

make.d <- function(x, a, b, c) {
#??????????? ncol ?
    d <- ncol(x) - a - b - c
    d
}

###########################################
#x, a
###########################################
my.jaccard <- function(x) {
    a <- make.a(x)
    b <- make.b(x)
    c <- make.c(x)
    #d <- make.d(x, a, b, c)
    jac <- a / (a + b + c)
    jac
}

#Col-wise Jaccard similarity
#http://stats.stackexchange.com/a/89947/2817
sparse.jaccard <- function(x) {
  A = crossprod(x)
  ix = which(A > 0, arr.ind=TRUE)
  b = colSums(x)
  Aix = A[ix]
  J = sparseMatrix(
    i = ix[,1],
    j = ix[,2],
    x = Aix / (b[ix[,1]] + b[ix[,2]] - Aix),
    dims = dim(A)
  )
  colnames(J) <- colnames(x)
  rownames(J) <- row.names(x)
  return(J)
}



prcooc <- function(x, a) {
    prc <- (a / nrow(x))
    prc
}

make.bin <- function(cs, a, i, j, nb) {
    if (a[i, j] >= 1) {
        ab <- a[i, j] - 1
        res <- binom.test(ab, nb, (cs[i]/nb) * (cs[j]/nb), "less")
    } else {
        res <- NULL
        res$p.value <- 0
    }
    #res <- binom.test(ab, nb, (cs[i]/nb) * (cs[j]/nb), "less")
    res$p.value
    }

binom.sim <- function(x) {
    a <- make.a(x)
    n <- nrow(x)
    cs <- colSums(x)
    mat <- matrix(0,ncol(x),ncol(x))
    colnames(mat)<-colnames(a)
    rownames(mat)<-rownames(a)
    for (i in 1:(ncol(x)-1)) {
        for (j in (i+1):ncol(x)) {
            mat[j,i] <- make.bin(cs, a, i, j , n)
        }
    }
#    print(mat)
    mat
}


############################################
# a, b, c
############################################
# jaccard a, b, c   a / (a + b + c)
# Kulczynski1 a, b, c   a / (b + c)
# Kulczynski2 a, b, c   [a / (a + b) + a / (a + c)] / 2
# Mountford a, b, c    2a / (ab + ac + 2bc)
# Fager, McGowan a, b, c   a / sqrt((a + b)(a + c)) - 1 / 2 sqrt(a + c)
# Russel, Rao a (a/n)
# Dice, Czekanowski, Sorensen a, b, c   2a / (2a + b + c)
# Mozley, Margalef a, b, c  an / (a + b)(a + c)
# Ochiai a, b, c  a / sqrt[(a + b)(a + c)]
# Simpson a, b, c   a / min{(a + b), (a + c)}
# Braun-Blanquet a, b, c  a / max{(a + b), (a + c)}

#simple matching, Sokal/Michener a, b, c, d, ((a + d) /n)
# Hamman, a, b, c, d, ([a + d] - [b + c]) / n
# Faith , a, b, c, d, (a + d/2) / n
# Tanimoto, Rogers a, b, c, d, (a + d) / (a + 2b + 2c + d)
# Phi  a, b, c, d   (ad - bc) / sqrt[(a + b)(c + d)(a + c)(b + d)]
# Stiles a, b, c, d  log(n(|ad-bc| - 0.5n)^2 / [(a + b)(c + d)(a + c)(b + d)])
# Michael   a, b, c, d   4(ad - bc) / [(a + d)^2 + (b + c)^2]
# Yule a, b, c, d  (ad - bc) / (ad + bc)
# Yule2  a, b, c, d  (sqrt(ad) - sqrt(bc)) / (sqrt(ad) + sqrt(bc))

BuildProf01<-function(x,classes) {
	#x : donnees en 0/1
	#classes : classes de chaque lignes de x
	dm<-cbind(x,cl=classes)
	clnb=length(summary(as.data.frame(as.character(classes)),max=100))
	print(clnb)
	print(summary(as.data.frame(as.character(classes)),max=100))
	mat<-matrix(0,ncol(x),clnb)
	rownames(mat)<-colnames(x)
	for (i in 1:clnb) {
		dtmp<-dm[which(dm$cl==i),]
		for (j in 1:(ncol(dtmp)-1)) {
			mat[j,i]<-sum(dtmp[,j])
		}
	}
	mat
}

do.simi <- function(x, method = 'cooc',seuil = NULL, p.type = 'tkplot',layout.type = 'frutch', max.tree = TRUE, coeff.vertex=NULL, coeff.edge = NULL, minmaxeff=c(NULL,NULL), vcexminmax= c(NULL,NULL), cex = 1, coords = NULL, communities = NULL, halo = FALSE, fromcoords=NULL, forvertex=NULL, index.word=NULL) {
	mat.simi <- x$mat
    mat.eff <- x$eff
    v.label <- colnames(mat.simi)
	g1<-graph.adjacency(mat.simi,mode="lower",weighted=TRUE)
	g.toplot<-g1
	weori<-get.edge.attribute(g1,'weight')
	if (max.tree) {
        if (method == 'cooc') {
		    invw <- 1 / weori
        } else {
            invw <- 1 - weori
        }
		E(g1)$weight<-invw
		g.max<-minimum.spanning.tree(g1)
        if (method == 'cooc') {
		    E(g.max)$weight<-1 / E(g.max)$weight
        } else {
            E(g.max)$weight<-1 - E(g.max)$weight
        }
		g.toplot<-g.max
	}

    if (!is.null(seuil)) {
        if (seuil >= max(mat.simi)) seuil <- -Inf
        vec<-vector()
        w<-E(g.toplot)$weight
        tovire <- which(w<=seuil)
        g.toplot <- delete.edges(g.toplot,(tovire))
        for (i in 1:(length(V(g.toplot)))) {
            if (length(neighbors(g.toplot,i))==0) {
                vec<-append(vec,i)
            }
        }
        g.toplot <- delete.vertices(g.toplot,vec)
        v.label <- V(g.toplot)$name
        if (!is.logical(vec)) mat.eff <- mat.eff[-(vec)]
    } else {
		vec <- NULL
	}

	if (!is.null(minmaxeff[1])) {
        eff<-norm.vec(mat.eff,minmaxeff[1],minmaxeff[2])
    } else {
        eff<-coeff.vertex
    }
    if (!is.null(vcexminmax[1])) {
        label.cex = norm.vec(mat.eff, vcexminmax[1], vcexminmax[2])
    } else {
        label.cex = cex
    }
    if (!is.null(coeff.edge)) {
        #FIXME
        we.width <- norm.vec(abs(E(g.toplot)$weight), coeff.edge[1], coeff.edge[2])
	    #we.width <- abs((E(g.toplot)$weight/max(abs(E(g.toplot)$weight)))*coeff.edge)
    } else {
        we.width <- NULL
    }
    if (method != 'binom') {
        we.label <- round(E(g.toplot)$weight,3)
    } else {
        we.label <- round(E(g.toplot)$weight,4)
    }
	if (p.type=='rgl' || p.type=='rglweb') {
        nd<-3
    } else {
        nd<-2
    }
    if (! is.null(fromcoords)) {
        newfrom <- matrix(runif(nd*length(V(g.toplot)$name),min(fromcoords)),max(fromcoords),ncol=nd, nrow=length(V(g.toplot)$name))
        for (i in 1:length(V(g.toplot)$name)) {
            if(V(g.toplot)$name[i] %in% forvertex) {
                newfrom[i,] <- fromcoords[which(forvertex==V(g.toplot)$name[i]),]
            }
        }
       fromcoords <- newfrom
    }
    #print(layout.type)
    if (is.null(coords)) {
    	if (layout.type == 'frutch') {
            #lo <- layout_with_drl(g.toplot,dim=nd)
            #lo <- layout_with_fr(g.toplot,dim=nd, grid="grid", niter=10000, weights=1/E(g.toplot)$weight)#, start.temp = 1)#, )
			if (nd==2) {
				library(sna)
				library(intergraph)
				lo <- gplot.layout.fruchtermanreingold(asNetwork(g.toplot), list())
				detach("package:intergraph", unload=TRUE)
				detach("package:sna", unload=TRUE)
				detach("package:network", unload=TRUE)
				library(igraph)
			} else {
				lo <- layout_with_fr(g.toplot,dim=nd)
			}
        }
    	if (layout.type == 'kawa') {
    		lo <- layout_with_kk(g.toplot,dim=nd, weights=1/E(g.toplot)$weight, start=fromcoords, epsilon=0, maxiter = 10000)
            #print(lo)
        }
    	if (layout.type == 'random')
    		lo <- layout_on_grid(g.toplot,dim=nd)
    	if (layout.type == 'circle' & p.type != 'rgl')
    		lo <- layout_in_circle(g.toplot)
    	if (layout.type == 'circle' & p.type == 'rgl')
    		lo <- layout_on_sphere(g.toplot)
        if (layout.type == 'graphopt')
            lo <- layout_as_tree(g.toplot, circular = TRUE)
		if (layout.type == 'spirale')
			lo <- spirale(g.toplot, E(g.toplot)$weight, index.word)
		if (layout.type == 'spirale3D')
			lo <- spirale3D(g.toplot, E(g.toplot)$weight, index.word)
    } else {
        lo <- coords
    }
    if (!is.null(communities)) {
        if (communities == 0 ){
            com <- edge.betweenness.community(g.toplot)
        } else if (communities == 1) {
            com <- fastgreedy.community(g.toplot)
        } else if (communities == 2) {
            com <- label.propagation.community(g.toplot)
        } else if (communities == 3) {
            com <- leading.eigenvector.community(g.toplot)
        } else if (communities == 4) {
            com <- multilevel.community(g.toplot)
        } else if (communities == 5) {
            com <- optimal.community(g.toplot)
        } else if (communities == 6) {
            com <- spinglass.community(g.toplot)
        } else if (communities == 7) {
            com <- walktrap.community(g.toplot)
        }
    } else {
        com <- NULL
    }

	out <- list(graph = g.toplot, mat.eff = mat.eff, eff = eff, mat = mat.simi, v.label = v.label, we.width = we.width, we.label=we.label, label.cex = label.cex, layout = lo, communities = com, halo = halo, elim=vec)
}

plot.simi <- function(graph.simi, p.type = 'tkplot',filename=NULL, communities = NULL, vertex.col = 'red', edge.col = 'black', edge.label = TRUE, vertex.label=TRUE, vertex.label.color = 'black', vertex.label.cex= NULL, vertex.size=NULL, leg=NULL, width = 800, height = 800, alpha = 0.1, cexalpha = FALSE, movie = NULL, edge.curved = TRUE, svg = FALSE, bg='white') {
	mat.simi <- graph.simi$mat
	g.toplot <- graph.simi$graph
    if (is.null(vertex.size)) {
        vertex.size <- graph.simi$eff
    } else {
        vertex.size <- vertex.size
    }
	we.width <- graph.simi$we.width
    if (vertex.label) {
        #v.label <- vire.nonascii(graph.simi$v.label)
        v.label <- graph.simi$v.label
    } else {
        v.label <- NA
    }
    if (edge.label) {
        we.label <- graph.simi$we.label
    } else {
        we.label <- NA
    }
	lo <- graph.simi$layout
    #rownames(lo) <- v.label
    if (!is.null(vertex.label.cex)) {
        label.cex<-vertex.label.cex
    } else {
        label.cex = graph.simi$label.cex
    }
 
    if (cexalpha) {
        alphas <- norm.vec(label.cex, 0.5,1)
        nvlc <- NULL
        if (length(vertex.label.color) == 1) {
            for (i in 1:length(alphas)) {
             nvlc <- append(nvlc, adjustcolor(vertex.label.color, alpha=alphas[i]))
            }
        } else {
            for (i in 1:length(alphas)) {
                nvlc <- append(nvlc, adjustcolor(vertex.label.color[i], alpha=alphas[i]))
            }
        }
        vertex.label.color <- nvlc  
    }
    if (p.type=='nplot') {
        #print('ATTENTION - PAS OPEN FILE')
        open_file_graph(filename, width = width, height = height, svg = svg)
        par(mar=c(2,2,2,2))
        par(bg=bg)
        if (!is.null(leg)) {
            layout(matrix(c(1,2),1,2, byrow=TRUE),widths=c(3,lcm(7)))
            par(mar=c(2,2,1,0))
        }
        par(pch=' ')
        if (is.null(graph.simi$com)) {
            plot(g.toplot,vertex.label='', edge.width=we.width, vertex.size=vertex.size, vertex.color=vertex.col, vertex.label.color='white', edge.label=we.label, edge.label.cex=cex, edge.color=edge.col, vertex.label.cex = 0, layout=lo, edge.curved=edge.curved)#, rescale = FALSE)
        } else {
            if (graph.simi$halo) {
                mark.groups <- communities(graph.simi$com)
            } else {
                mark.groups <- NULL
            }
            plot(com, g.toplot,vertex.label='', edge.width=we.width, vertex.size=vertex.size, vertex.color=vertex.col, vertex.label.color='white', edge.label=we.label, edge.label.cex=cex, edge.color=edge.col, vertex.label.cex = 0, layout=lo, mark.groups = mark.groups, edge.curved=edge.curved)
        }
        #txt.layout <- lo
        txt.layout <- layout.norm(lo, -1, 1, -1, 1, -1, 1)
        #txt.layout <- txt.layout[order(label.cex),]
        #vertex.label.color <- vertex.label.color[order(label.cex)]
        #v.label <- v.label[order(label.cex)]
        #label.cex <- label.cex[order(label.cex)]
        text(txt.layout[,1], txt.layout[,2], v.label, cex=label.cex, col=vertex.label.color)
        if (!is.null(leg)) {
            par(mar=c(0,0,0,0))
            plot(0, axes = FALSE, pch = '')
            legend(x = 'center' , leg$unetoile, fill = leg$gcol)
        }
        dev.off()
        return(lo)
    }
	if (p.type=='tkplot') {
		id <- tkplot(g.toplot,vertex.label=v.label, edge.width=we.width, vertex.size=vertex.size, vertex.color=vertex.col, vertex.label.color=vertex.label.color, edge.label=we.label, edge.color=edge.col, layout=lo)
        coords = tkplot.getcoords(id)
        ok <- try(coords <- tkplot.getcoords(id), TRUE)
		while (is.matrix(ok)) {
            ok <- try(coords <- tkplot.getcoords(id), TRUE)
			Sys.sleep(0.5)
        }
	tkplot.off()
    return(coords)
	}
	
	if (p.type == 'rgl' || p.type == 'rglweb') {
		library('rgl')
        #rgl.open()
        #par3d(cex=0.8)
        lo <- layout.norm(lo, -10, 10, -10, 10, -10, 10)
		bg3d('white')
		rglplot(g.toplot,vertex.label='', edge.width=we.width/10, vertex.size=0.01, vertex.color=vertex.col, vertex.label.color="black", edge.color = edge.col, layout=lo, rescale = FALSE)
        #los <- layout.norm(lo, -1, 1, -1, 1, -1, 1)
		text3d(lo[,1], lo[,2], lo[,3], vire.nonascii(v.label), col = vertex.label.color, alpha = 1, cex = vertex.label.cex)
        rgl.spheres(lo, col = vertex.col, radius = vertex.size/100, alpha = alpha)
        #rgl.bg(color = c('white','black'))
        #bg3d('white')
        if (!is.null(movie)) {
            require(tcltk)
            ReturnVal <- tkmessageBox(title="RGL 3 D",message="Cliquez pour commencer le film",icon="info",type="ok")

            movie3d(spin3d(axis=c(0,0,1),rpm=6), movie = 'film_graph', frames = "tmpfilm", duration=10, clean=TRUE, top = TRUE, dir = movie)
            ReturnVal <- tkmessageBox(title="RGL 3 D",message="Film fini !",icon="info",type="ok")
        }
        #play3d(spin3d(axis=c(0,1,0),rpm=6))
        if (p.type == 'rglweb') {
            writeWebGL(dir = filename, width = width, height= height)
			#rglwidget()
        }# else {
            require(tcltk)
            ReturnVal <- tkmessageBox(title="RGL 3 D",message="Cliquez pour fermer",icon="info",type="ok")
        #}
        rgl.close()
	#	while (rgl.cur() != 0)
	#		Sys.sleep(0.5)
	} else if (p.type == 'web') {
		library(rgexf)
        graph.simi$label.cex <- label.cex
		if (length(vertex.col)==1) {
			vertex.col <- rep(vertex.col, length(v.label))
		}
        graph.simi$color <- vertex.col
        label <- v.label
        nodes.attr <- data.frame(label)
		simi.to.gexf(filename, graph.simi, nodes.attr = nodes.attr)
	}
}


graph.word <- function(mat.simi, index) {
    nm <- matrix(0, ncol = ncol(mat.simi), nrow=nrow(mat.simi), dimnames=list(row.names(mat.simi), colnames(mat.simi)))
    nm[,index] <- mat.simi[,index]
    nm[index,] <- mat.simi[index,]
    nm
}

#from : 
#http://gopalakrishna.palem.in/iGraphExport.html#GexfExport
# Converts the given igraph object to GEXF format and saves it at the given filepath location
#     g: input igraph object to be converted to gexf format
#     filepath: file location where the output gexf file should be saved
#
saveAsGEXF = function(g, filepath="converted_graph.gexf")
{
  require(igraph)
  require(rgexf)
  
  # gexf nodes require two column data frame (id, label)
  # check if the input vertices has label already present
  # if not, just have the ids themselves as the label
  if(is.null(V(g)$label))
    V(g)$label <- as.character(V(g))
  
  # similarily if edges does not have weight, add default 1 weight
  if(is.null(E(g)$weight))
    E(g)$weight <- rep.int(1, ecount(g))
  
  nodes <- data.frame(cbind(1:vcount(g), V(g)$label))
  nodes[,1] <- as.character(nodes[,1])
  nodes[,2] <- as.character(nodes[,2])
  edges <- t(Vectorize(get.edge, vectorize.args='id')(g, 1:ecount(g)))
  
  # combine all node attributes into a matrix (and take care of & for xml)
  vAttrNames <- setdiff(list.vertex.attributes(g), "label")
  for (val in c("x","y","color")) {
        vAttrNames <- setdiff(vAttrNames, val)
  }
  nodesAtt <- data.frame(sapply(vAttrNames, function(attr) sub("&", "&",get.vertex.attribute(g, attr))))
  for (i in 1:ncol(nodesAtt)) {
      nodesAtt[,i] <- as.character(nodesAtt[,i])
  }
  
  # combine all edge attributes into a matrix (and take care of & for xml)
  eAttrNames <- setdiff(list.edge.attributes(g), "weight") 
  edgesAtt <- data.frame(sapply(eAttrNames, function(attr) sub("&", "&",get.edge.attribute(g, attr))))
  
  # combine all graph attributes into a meta-data
  graphAtt <- sapply(list.graph.attributes(g), function(attr) sub("&", "&",get.graph.attribute(g, attr)))
  ll <- length(V(g)$x)
  cc <- t(sapply(V(g)$color, col2rgb, alpha=TRUE))
  cc[,4] <- cc[,4]/255
  # generate the gexf object
  output <- write.gexf(nodes, edges, 
                       edgesWeight=E(g)$weight,
                       edgesAtt = edgesAtt,
                       #edgesVizAtt = list(size=as.matrix(E(g)$weight)),
                       nodesAtt = nodesAtt,
                       nodesVizAtt=list(color=cc, position=cbind(V(g)$x,V(g)$y, rep(0,ll)), size=V(g)$weight),
                       meta=c(list(creator="iramuteq", description="igraph -> gexf converted file", keywords="igraph, gexf, R, rgexf"), graphAtt))
  
  print(output, filepath, replace=T)
}


merge.graph <- function(graphs) {
    library(colorspace)
    ng <- graph.union(graphs, byname=T)
    V.weight <- V(ng)$weight_1 
    E.weight <- E(ng)$weight_1
    cols <- rainbow(length(graphs))
    V.color <- rep(cols[1], length(V.weight))
    for (i in 2:length(graphs)) {
        tw <- paste('weight_', i, sep='')
        tocomp <- get.vertex.attribute(ng,tw)
        totest <- intersect(which(!is.na(V.weight)), which(!is.na(tocomp)))
        maxmat <- cbind(V.weight[totest], tocomp[totest])
        resmax <- apply(maxmat, 1, which.max)
        ncolor <- c(cols[(i-1)], cols[i])
        #rbgcol1 <- col2rgb(cols[(i-1)])
        #rbgcol1 <- rbgcol1/255
        #rgbcol1 <- RGB(rbgcol1[1],rbgcol1[2],rbgcol1[3])
        rbgcol2 <- col2rgb(cols[i])
        rbgcol2 <- rbgcol2/255
        #rgbcol2 <- RGB(rbgcol2[1],rbgcol2[2],rbgcol2[3])       
        for (j in totest) {
            alpha <- tocomp[j] /(V.weight[j] + tocomp[j])
            rbgcol1 <- col2rgb(V.color[j])
            rbgcol1 <- rbgcol1/255
            #mix.col <- mixcolor(alpha,rbgcol1, rbgcol2)
            mix.col <- mixcolor(alpha, RGB(rbgcol1[1],rbgcol1[2],rbgcol1[3]), RGB(rbgcol2[1],rbgcol2[2],rbgcol2[3]))
            V.color[j] <- hex(mix.col)
			#V.color[j] <- adjustcolor(hex(mix.col), 0.6)
        }
        #to.change <- totest[which(resmax == 2)]
        #V.color[to.change] <- cols[i]
        V.weight[totest] <- apply(maxmat, 1, max)
        nas <- which(is.na(V.weight))
        nas2 <- which(is.na(tocomp))
        fr2 <- setdiff(nas,nas2)
        V.weight[fr2] <- tocomp[fr2]
        V.color[fr2] <- cols[i]
        tocomp <- get.edge.attribute(ng, tw)
        totest <- intersect(which(!is.na(E.weight)), which(!is.na(tocomp)))
        maxmat <- cbind(E.weight[totest], tocomp[totest])
        resmax <- apply(maxmat, 1, which.max)
        E.weight[totest] <- apply(maxmat, 1, max)
        nas <- which(is.na(E.weight))
        nas2 <- which(is.na(tocomp))
        fr2 <- setdiff(nas,nas2)
        E.weight[fr2] <- tocomp[fr2]        
    }
    V(ng)$weight <- V.weight
    V(ng)$color <- V.color
    E(ng)$weight <- E.weight
	colors <- col2rgb(V(ng)$color)
	V(ng)$r <- colors["red", ]
	V(ng)$g <- colors["green", ]
	V(ng)$b <- colors["blue", ]
    ng
}

merge.graph.proto <- function(graphs) {
    library(colorspace)
    ng <- graph.union(graphs, byname=T)
    V.weight <- V(ng)$weight_1 
    E.weight <- E(ng)$weight_1
	V.proto.color <- V(ng)$proto.color_1
	cols <- rainbow(length(graphs))
	V.color <- rep(cols[1], length(V.weight))
    for (i in 2:length(graphs)) {
        tw <- paste('weight_', i, sep='')
        tocomp <- get.vertex.attribute(ng,tw)
        totest <- intersect(which(!is.na(V.weight)), which(!is.na(tocomp)))
        maxmat <- cbind(V.weight[totest], tocomp[totest])
        resmax <- apply(maxmat, 1, which.max)
        V.weight[totest] <- apply(maxmat, 1, max)
        nas <- which(is.na(V.weight))
        nas2 <- which(is.na(tocomp))
        fr2 <- setdiff(nas,nas2)
        V.weight[fr2] <- tocomp[fr2]

		cw <- paste('proto.color_', i, sep='')
		tocomp.col <- get.vertex.attribute(ng,cw)
		which.sup <- which(resmax==2)
		V.proto.color[totest[which.sup]] <- tocomp.col[totest[which.sup]]
		V.proto.color[fr2] <- tocomp.col[fr2]

		V.color[totest[which.sup]] <- cols[i]
		V.color[fr2] <- cols[i]

        tocomp <- get.edge.attribute(ng, tw)
        totest <- intersect(which(!is.na(E.weight)), which(!is.na(tocomp)))
        maxmat <- cbind(E.weight[totest], tocomp[totest])
        resmax <- apply(maxmat, 1, which.max)
        E.weight[totest] <- apply(maxmat, 1, max)
        nas <- which(is.na(E.weight))
        nas2 <- which(is.na(tocomp))
        fr2 <- setdiff(nas,nas2)
        E.weight[fr2] <- tocomp[fr2]        	
	}
    V(ng)$weight <- V.weight
    V(ng)$proto.color <- V.proto.color
	V(ng)$color <- V.proto.color
    E(ng)$weight <- E.weight
	V(ng)$ocolor <- V.color
	colors <- col2rgb(V(ng)$color)
	V(ng)$r <- colors["red", ]
	V(ng)$g <- colors["green", ]
	V(ng)$b <- colors["blue", ]
    ng
}


spirale <- function(g, weigth, center, miny=0.1) {
	ncoord <- matrix(0, nrow=length(weigth)+1, ncol=2)
	v.names <- V(g)$name 
	center.name <- v.names[center]
	first <- which.max(weigth)[1]
	if (head_of(g, first)$name == center.name) {
		n.name <- tail_of(g, first)
	} else {
		n.name <- head_of(g, first)
	}
	n.name <- n.name$name
	nb <- length(weigth)
	ncoord[which(v.names==n.name),] <- c(0,1)
	weigth[first] <- 0
	rs <- norm.vec(weigth,1, miny)
	nbt <- nb %/% 50
	if (nbt == 0) nbt <- 1
	angler <- ((360 * nbt) / (nb- 1)) * (pi/180)
	ang <- 90 * (pi/180)
	rr <- (1-miny) / (nb-1)
	r <- 1
	while (max(weigth != 0)) {
		first <- which.max(weigth)[1]
		if (head_of(g, first)$name == center.name) {
			n.name <- tail_of(g, first)
		} else {
			n.name <- head_of(g, first)
		}
		n.name <- n.name$name
		#r <- rs[first]
		r <- r - rr
		ang <- ang + angler 
		x <- r * cos(ang)
		y <- r * sin(ang)
		weigth[first] <- 0
		ncoord[which(v.names==n.name),] <- c(x,y)
	}
	ncoord
}

spirale3D <- function(g, weigth, center, miny=0.1) {
	ncoord <- matrix(0, nrow=length(weigth)+1, ncol=3)
	v.names <- V(g)$name 
	center.name <- v.names[center]
	first <- which.max(weigth)[1]
	if (head_of(g, first)$name == center.name) {
		n.name <- tail_of(g, first)
	} else {
		n.name <- head_of(g, first)
	}
	n.name <- n.name$name
	nb <- length(weigth)
	ncoord[which(v.names==n.name),] <- c(0,0,1)
	weigth[first] <- 0
	rs <- norm.vec(weigth,1, miny)
	nbt <- nb %/% 50
	if (nbt == 0) nbt <- 1
	angler <- ((360 * nbt) / (nb- 1)) * (pi/180)
	theta <- 0
	phi <- 90 * (pi/180)
	rr <- (1-miny) / (nb-1)
	r <- 1
	while (max(weigth != 0)) {
		first <- which.max(weigth)[1]
		if (head_of(g, first)$name == center.name) {
			n.name <- tail_of(g, first)
		} else {
			n.name <- head_of(g, first)
		}
		n.name <- n.name$name
		#r <- rs[first]
		r <- r - rr
		theta <- theta + angler
		phi <- phi + angler/2
		x <- r * sin(theta) * cos(phi)
		y <- r * sin(theta) * sin(phi)
		z <- r * cos(theta)
		weigth[first] <- 0
		ncoord[which(v.names==n.name),] <- c(x,y,z)
	}
	ncoord
}
