script_path <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[[1]])
repo_root <- normalizePath(file.path(dirname(script_path), ".."), winslash = "/", mustWork = TRUE)
source(file.path(repo_root, "iramuteqlite", "distance-labbe.R"), local = TRUE)

assert_close <- function(actual, expected, tolerance = 1e-12) {
  stopifnot(isTRUE(all.equal(actual, expected, tolerance = tolerance)))
}

identical_tab <- cbind(A = c(5, 3, 2), B = c(5, 3, 2))
assert_close(compute.labbe(1, 2, identical_tab), 0)

proportional_tab <- cbind(A = c(10, 6, 4), B = c(5, 3, 2))
assert_close(compute.labbe(1, 2, proportional_tab), 0)
assert_close(compute.labbe(2, 1, proportional_tab), 0)

disjoint_tab <- cbind(A = c(10, 0), B = c(0, 10))
assert_close(compute.labbe(1, 2, disjoint_tab), 1)

# Cas limite qui révélait l'asymétrie > 1 / >= 1 du script historique.
boundary_tab <- cbind(A = c(2, 0, 2), B = c(1, 1, 2))
assert_close(compute.labbe(1, 2, boundary_tab), compute.labbe(2, 1, boundary_tab))

matrix_result <- dist.labbe(cbind(A = c(5, 3, 2), B = c(5, 3, 2), C = c(0, 8, 2)))
stopifnot(isTRUE(all.equal(matrix_result, t(matrix_result))))
stopifnot(all(diag(matrix_result) == 0))
stopifnot(all(matrix_result >= 0 & matrix_result <= 1))

invalid <- try(compute.labbe(1, 2, cbind(A = c(0, 0), B = c(1, 2))), silent = TRUE)
stopifnot(inherits(invalid, "try-error"))

cat("Tests distance de Labbe: OK\n")
