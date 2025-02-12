suppressPackageStartupMessages(library(scPNMF))
suppressPackageStartupMessages(library(anndata))
library(reticulate)
np <- import("numpy")

# example
ddir <- "/bigstore/GeneralStorage/fangming/projects/dredfish/res_dpnmf/"
name0 <- "smrt" 
k <- 24 
mu_range <- c(1e4, 1e2, 1, 1e-2, 1e-4)
namex_range <- c("subL3n100")
namey_range <- c("L3")

for (i in 1:length(namex_range)){ 
    namex <- namex_range[i]
    namey <- namey_range[i]
    print(namex)
    print(namey)

    for (j in 1:length(mu_range)){
        mu <- mu_range[j]
        print(mu)

        in_X <- paste(ddir, name0, "_X_", namex, ".npy", sep = "") 
        in_y <- paste(ddir, name0, "_X_", namex, "_y_", namey, ".npy", sep = "") 
        ot_w <- paste(ddir, name0, "_X_", namex, "_y_", namey, 
                        "_dpnmfW_", "k", toString(k), "_mu", toString(mu), ".csv", sep = "")
        ot_s <- paste(ddir, name0, "_X_", namex, "_y_", namey, 
                        "_dpnmfS_", "k", toString(k), "_mu", toString(mu), ".csv", sep = "")

        ot_wsel <- paste(ddir, name0, "_X_", namex, "_y_", namey, 
                        "_dpnmfWsel_", "k", toString(k), "_mu", toString(mu), ".csv", sep = "")
        ot_ssel <- paste(ddir, name0, "_X_", namex, "_y_", namey, 
                        "_dpnmfSsel_", "k", toString(k), "_mu", toString(mu), ".csv", sep = "")
        print(ot_w)
        print(ot_s)

        X <- np$load(in_X, allow_pickle = TRUE)
        labels <- np$load(in_y, allow_pickle = TRUE)

        m <- dim(X)[1]
        n <- dim(X)[2]
        rownames(X) <- 1:m
        colnames(X) <- 1:n

        print(length(labels))
        print(dim(X))
        print("Running DPNMF...")
        res <- PNMFfun(X = X, 
                    K = k, 
                    method = "DPNMF", # "EucDist", # "DPNMF"
                    label = labels,
                    mu = mu,
                    lambda = 0.01,
                    verboseN = TRUE,
                    maxIter=2000,
                    tol=1e-4,
                    seed = 0,
                    )
        W <- res$Weight
        S <- res$Score

        # select good basis (test of corr vs library size; multimodal test)
        W_sel <- scPNMF::basisSelect(W = W, S = S,
                                X = X, toTest = TRUE, toAnnotate = FALSE, mc.cores = 4)
        S_sel <- S[,colnames(W_sel)]

        write.csv(W, file=ot_w)
        write.csv(S, file=ot_s)
        write.csv(W_sel, file=ot_wsel)
        write.csv(S_sel, file=ot_ssel)
        break
    }
    break
}
