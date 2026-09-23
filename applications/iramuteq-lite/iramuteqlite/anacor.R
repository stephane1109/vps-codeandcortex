#################################################################################


write.sparse <- function (m, to) {
  ## Writes in a format that SVDLIBC can read
  stopifnot(inherits(m, "dgCMatrix"))
  fh <- file(to, open="w")
  
  wl <- function(...) cat(..., "\n", file=fh)
  
  ## header
  wl(dim(m), length(m@x))
  
  globalCount <- 1
  nper <- diff(m@p)
  for(i in 1:ncol(m)) {
    wl(nper[i])  ## Number of entries in this column
    if (nper[i]==0) next
    for(j in 1:nper[i]) {
      wl(m@i[globalCount], m@x[m@p[i]+j])
      globalCount <- globalCount+1
    }
  }
}

my.svd <- function(x, nu, nv, libsvdc.path=NULL, sparse.path=NULL) {
  print('my.svd')
  stopifnot(nu==nv)
  outfile <- file.path(tempdir(),'sout')
  cmd <- paste(libsvdc.path, '-o', outfile, '-d')
  #rc <- system(paste("/usr/bin/svd -o /tmp/sout -d", nu, "/tmp/sparse.m"))
  rc <- system(paste(cmd, nu, sparse.path))
  if (rc != 0)
    stop("Couldn't run external svd code")
  res1 <- paste(outfile,'-S', sep='')
  d <- scan(res1, skip=1)
#FIXME : sometimes, libsvdc doesn't find solution with 2 dimensions, but does with 3 
  if (length(d)==1) {
      nu <- nu + 1
      #rc <- system(paste("/usr/bin/svd -o /tmp/sout -d", nu, "/tmp/sparse.m"))
      rc <- system(paste(cmd, nu, sparse.path))
      d <- scan(res1, skip=1)
  }
  utfile <- paste(outfile, '-Ut', sep='')
  ut <- matrix(scan(utfile,skip=1),nrow=nu,byrow=TRUE)
  if (nrow(ut)==3) {
      ut <- ut[-3,]
  }
  vt <- NULL
  list(d=d, u=-t(ut), v=vt)
}
###################################################################################

#from anacor package
boostana<-function (tab, ndim = 2, svd.method = 'svdR', libsvdc.path=NULL) 
{
    #tab <- as.matrix(tab)
    if (ndim > min(dim(tab)) - 1) 
        stop("Too many dimensions!")
    name <- deparse(substitute(tab))
    if (any(is.na(tab))) 
	print('YA NA')        
	#tab <- reconstitute(tab, eps = eps)
    n <- dim(tab)[1]
    m <- dim(tab)[2]
    N <- sum(tab)
    #tab <- as.matrix(tab)
    #prop <- as.vector(t(tab))/N
    r <- rowSums(tab)
    c <- colSums(tab)
    qdim <- ndim + 1
    r <- ifelse(r == 0, 1, r)
    c <- ifelse(c == 0, 1, c)
    print('make z')
    z1 <- t(tab)/sqrt(c)
    z2 <- tab/sqrt(r)
    z <- t(z1) * z2
    if (svd.method == 'svdlibc') {
        #START NEW SVD
        z <- as(z, "dgCMatrix")
        tmpmat <- tempfile(pattern='sparse')
        print('write sparse matrix')
        write.sparse(z, tmpmat)
        print('do svd')
        sv <- my.svd(z, qdim, qdim, libsvdc.path=libsvdc.path, sparse.path=tmpmat)
        #END NEW SVD
    } else if (svd.method == 'svdR') {
        print('start R svd')
        sv <- svd(z, nu = qdim, nv = qdim) 
        print('end svd')
    } else if (svd.method == 'irlba') {
        if (!requireNamespace("irlba", quietly = TRUE)) {
            warning("Package 'irlba' introuvable, bascule automatique vers 'svdR'.")
            print('start R svd (fallback)')
            sv <- svd(z, nu = qdim, nv = qdim)
            print('end svd (fallback)')
        } else {
            min_dim <- min(nrow(z), ncol(z))
            if (qdim >= min_dim) {
                warning(
                    paste0(
                        "Méthode 'irlba' non applicable (nu/nv=", qdim,
                        " doit être strictement < min(nrow, ncol)=", min_dim,
                        "). Bascule automatique vers 'svdR'."
                    )
                )
                print('start R svd (fallback: qdim >= min_dim)')
                sv <- svd(z, nu = qdim, nv = qdim)
                print('end svd (fallback: qdim >= min_dim)')
            } else {
                print('irlba')
                sv <- irlba::irlba(z, nv = qdim, nu = qdim)
                print('end irlba')
            }
        }
    }
    sigmavec <- (sv$d)[2:qdim]
	x <- ((sv$u)/sqrt(r))[, -1]
    x <- x * sqrt(N)
    x <- x * outer(rep(1, n), sigmavec)
    dimlab <- paste("D", 1:ndim, sep = "")
    colnames(x) <- dimlab# <- colnames(y) <- dimlab
    rownames(x) <- rownames(tab)
    result <- list(ndim = ndim, row.scores = x, 
			singular.values = sigmavec, eigen.values = sigmavec^2)
    class(result) <- "boostanacor"
    result
}
