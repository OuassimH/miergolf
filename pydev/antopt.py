
import sys
import scipy.sparse as sp
import scipy.sparse.linalg as lin
import numpy as np
from bisect import bisect
import random
import itertools as it

# Hypercube MinMax Ant Optimization #
def optimize (pool, s, nodes, sparseMat):

    # for each new convergence #
    for run in xrange(s["runs"]):
        print "RUN: " + str(run) 

        # prepare for this reset-run #
        nodes = resetNodes(nodes)
        s     = resetState(s)
        iters = 0; maxIters = 100000;
        
        while iters < maxIters and s["c"] > s["ct"]:

            # generate the probability distribution # 
            ps = genProbs(s,nodes)

            # for each new ant, generate a solution, local search, and score
            (bestSoln,bestScore) = antWork(pool, s, np.copy(ps), sparseMat)

            # update the best/resetbest/iterbests #
            s = updateSolutionSet(s, bestSoln, bestScore, iters)

            # update the pheromones #
            nodes = updatePheromones(s, nodes)

            # check for convergence #
            s = checkConvergence(s, nodes)
            iters += 1
            s["iters"] = iters

    return(s)


def resetNodes(nodes):
    for k in nodes.keys():
        (a,b,c,d,e) = nodes[k]
        nodes[k] = (a,b,c,0.5,e)
    return(nodes)


def resetState(s):
    s["bestRest"] = (0.0,0.0,[])
    s["bestIter"] = (0.0,0.0,[])
    s["c"] = 1.0
    return(s)


def genProbs(s,nodes):
    # generate the probablities for selecting each node
    ps = np.zeros(len(nodes))
    for k in nodes.keys():
        ps[k] = (pow(nodes[k][2], s["alph"]) * pow(nodes[k][3], s["beta"]))
    return(ps)


def antWork(pool, s, ps, sparseMat):
    # for the solns
    nants = s["ants"]
    # generate the list of data for each ant
    antdat = it.izip(xrange(nants), it.repeat(s, nants), it.repeat(ps, nants), it.repeat(sparseMat, nants))
    # send it to a pooled fun party
    solns = pool.map(poolParty, antdat)
    # return teh bestest
    return(scoreMax(solns, s))


def poolParty( (i, s, ps, sparseMat) ):
    # start with a possible solution
    soln = genSoln(i,s,np.copy(ps))
    # then do a local search
    (soln2, score) = localSearch(s, np.copy(ps), soln, sparseMat)
    # return the best
    return(soln2, score)

    
def genSoln(i, s, ps):
    # generate a solution, probabilistically for each ant.    
    soln = []
    r = random.Random()
    r.jumpahead(int(1000*r.random())) # make sure each parallel thread has diff #s
    for ki in xrange(int(s["k"])):
        ps = ps/(sum(ps)) # after removing one ... renorm the probs
        cs = ps.cumsum()
        solni = bisect(cs,r.random()) # should skip over the 0'ed ones...
        soln.append(solni)
        ps[solni] = 0
    return(soln)


def localSearch(s, ps, bestSoln, sparseMat):
    (bestScore,bestTouch) = scoreSoln(bestSoln, s, sparseMat)
    if s["local"] == -1:   # none
        # go back! go back!
        return (bestSoln,(bestScore,bestTouch))
    else:
        # hill climbing for a certain number of steps
        r = random.Random()
        r.jumpahead(int(1000*r.random())) # make sure each parallel thread has diff #
        newSoln = list(bestSoln)
        newScore = bestScore
        newTouch = bestTouch
        ps = ps/(sum(ps))
        cs = ps.cumsum()
        n = s["local"] # the number of tries to make
        testsoln = list(newSoln)
        for i in xrange(n):
            remr  = random.sample(testsoln,1)[0]           # the one to remove
            solnr = [xi for xi in testsoln if xi != remr]  # fragment list
            solni = testsoln[0];                                    # pick a new one, not in the list already
            while solni in testsoln:
                solni = bisect(cs,r.random())         # the one to add, based on ps
            testsoln = list( (solnr + [solni]) )           # the new soln list
            score    = scoreSoln(testsoln, s, sparseMat)   # score it
            if s["opton"] == "touch":
                if score[1] > newTouch:
                    newScore = score[0]          # if better: keep it
                    newTouch = score[1]
                    newSoln = list(testsoln)
                else:
                    testsoln = list(newSoln)  # else: return to previous soln                    
            else:
                print "Not implemented yet!"
                sys.exit(1)
        return (newSoln, (newScore, newTouch))


def scoreSoln(soln, s, smat):
    # soln -- the solutions set S
    # smat  -- nxn sparse matrix
    # s     -- the program state
    n = (smat.shape[0])
    ts = [i for i in xrange(n) if i not in soln] # set T
    idn = sp.eye(len(ts),len(ts))
    pst = subMatrix(soln, ts, smat) # prob of S to T
    pts = subMatrix(ts, soln, smat) # prob of T to S
    ptt = subMatrix(ts, ts, smat)    # prob of T to T
    lap = sp.csc_matrix(idn-ptt)
    pst_t = sp.csc_matrix(pst.transpose())
    lap_t = sp.csc_matrix(lap.transpose())    
    if s["mode"] == "both":
        return(scoreBoth(s,lap,pts,lap_t,pst_t))
    elif s["mode"] == "tx":
        return(scoreTX(s,lap,pts))
    elif s["mode"] == "rx":
        return(scoreRX(s,lap_t,pst_t))
    else:
        print "ScoreSoln Error! mode must be rx, tx, or both."
        sys.exit(1)


def scoreBoth(s,lap,pts,lap_t,pst_t):
    f = lin.spsolve(lap, pts) 
    h = lin.spsolve(lap_t, pst_t)
    if type(f) == type(np.array([])): # came back as an array
        print "single array f, h"
        score = f.sum() + h.sum()
        touch = sum(h > s["tx"]) + sum(f > s["rx"])
    else: # came back as a sparse matrix
        fSsum = np.array(f.sum(0)).flatten()
        hSsum = np.array(h.sum(0)).flatten()
        scover = fSsum + hSsum

        fTsum = np.array(f.sum(1)).flatten()
        hTsum = np.array(h.sum(1)).flatten()
        tcover = fTsum + hTsum

        #score = fSsum.sum()+fTsum.sum()+hSsum.sum()+hTsum.sum()
        score = scover.sum() + tcover.sum()
        
        #touch = (sum(fSsum > s["rx"]) + 
        #         sum(fTsum > s["rx"]) +
        #         sum(hSsum > s["tx"]) +
        #         sum(hTsum > s["tx"]))
        touch = sum(scover > s["rx"]) + sum(tcover > s["rx"])

        #  best score; best touch #
    return((score, touch))


def XscoreBoth(s,lap,pts,lap_t,pst_t):
    f = lin.spsolve(lap, pts) 
    h = lin.spsolve(lap_t, pst_t)
    if type(f) == type(np.array([])): # came back as an array
        fh = f+h
        score = fh.sum()
        touch = (fh > s["tx"]).sum()
    else: # came back as a sparse matrix
        fsum = np.array(f.sum(1)).flatten()
        hsum = np.array(h.sum(1)).flatten()
        fh = fsum + hsum
        touch = sum(fh > s["tx"])
        #  best score; best touch #
    return((fh.sum(), touch))



def scoreRX(s,lap,pts):
    f = lin.spsolve(lap, pts) 
    if type(f) == type(np.array([])): # came back as an array
        ftouch = sum(f > s["rx"])
    else: # came back as a sparse matrix
        fsum = np.array(f.sum(1)).flatten()
        ftouch = sum(fsum > s["rx"])
    return((fsum.sum(), ftouch))


def scoreTX(s, lap_t, pst_t):
    h = lin.spsolve(lap_t, pst_t)
    if type(h) == type(np.array([])): # came back as an array
        htouch = sum(h > s["tx"])
    else: # came back as a sparse matrix
        hsum = np.array(h.sum(1)).flatten()
        htouch = sum(hsum > s["tx"])
    return((hsum.sum(), htouch))


def scoreMats(solns, s, smat):
    # ss    -- the solutions set S
    # smat  -- nxn sparse matrix
    # ts    -- the set T
    n = (smat.shape[0]-1)
    ts = [i for i in xrange(n) if i not in solns]
    idn = sp.eye(len(ts))
    pst = subMatrix(solns, ts, smat)
    pts = subMatrix(ts, solns, smat)
    ptt = subMatrix(ts, ts, smat)
    lap = sp.csc_matrix(idn-ptt)
    pst_t = sp.csc_matrix(pst.transpose())
    lap_t = sp.csc_matrix(lap.transpose())    
    f = lin.spsolve(lap, pts) 
    h = lin.spsolve(lap_t, pst_t)
    return((f,h))


def subMatrix(rows, cols, A):
    return(A.tocsr()[rows,:].tocsc()[:,cols])


def scoreMax(solns, s):
    best = 0  # index to the best
    idx = 0   # current index
    for (a,(b,c)) in solns:
        if s["opton"] == "touch":
            if best < c:
                best = idx
        elif s["opton"] == "score":
            if best < b:
                best = idx
        elif s["opton"] == "combo":
            if best < combo(b,c):
                best = idx
        else:
            print "ScoreMax Error: opton must be score, touch, or combo"
            sys.exit(1)
        idx += 1 # NEXT!
    return(solns[best])


def combo(a,b):
    return(a*b)


def updateSolutionSet(s, bestSoln, (bestScore,bestTouch), iters):
    if s["opton"] == "score":
        if bestScore > s["bestEver"][0]:
            s["bestEver"] = (bestScore, bestTouch, bestSoln)
        if bestScore > s["bestRest"][0]:
            s["bestRest"] = (bestScore, bestTouch, bestSoln)
        if bestScore > s["bestIter"][0]:
            s["bestIter"] = (bestScore, bestTouch, bestSoln)
    elif s["opton"] == "touch": 
        if bestTouch > s["bestEver"][1]:
            s["bestEver"] = (bestScore, bestTouch, bestSoln)
        if bestTouch > s["bestRest"][1]:
            s["bestRest"] = (bestScore, bestTouch, bestSoln)
        if bestTouch > s["bestIter"][1]:
            s["bestIter"] = (bestScore, bestTouch, bestSoln)
    elif s["opton"] == "combo":
        if combo(bestTouch,bestScore) > combo(s["bestEver"][1],s["bestEver"][0]):
            s["bestEver"] = (bestScore, bestTouch, bestSoln)
        if combo(bestTouch,bestScore) > combo(s["bestRest"][1],s["bestRest"][0]):
            s["bestRest"] = (bestScore, bestTouch, bestSoln)
        if combo(bestTouch*bestScore) > combo(s["bestIter"][1],s["bestIter"][0]):
            s["bestIter"] = (bestScore, bestTouch, bestSoln)
    else:
        print "Update Solution Error! config option 'opton' must be score, touch, or combo"
        sys.exit(1)
    return(s)


def updatePheromones(s, nodes):
    (iterp, restp, bestp) = pheroProportions(s)
    restartSoln = s["bestRest"][2]
    iterateSoln = s["bestIter"][2]
    bestSoln    = s["bestEver"][2]
    for k in nodes.keys():
        (a,b,w,p,ch) = nodes[k]
        inRest = int(k in restartSoln)
        inIter = int(k in iterateSoln)
        inBest = int(k in bestSoln)
        deposit = inIter * iterp + inRest * restp + inBest * bestp
        p2 = bounded(p + s["evap"]*(deposit - p))
        nodes[k] = (a,b,w,p2,(ch+(inIter+inRest+inBest)/3.0))
    return(nodes)


def pheroProportions(s):
    # return proportions of solutions to use
    # (iteration, restart, best)
    sc = s["c"]
    if sc > 0.8:
        x= (1.0, 0.0, 0.0) #- just started out, use iteration best
    elif sc >= 0.6 and sc < 0.8:
        x= (0.6669, 0.3331, 0.0)
    elif sc >= 0.4 and sc < 0.6:
        x= (0.3331, 0.6669, 0.0) # nearing the end - move to restart 
    elif sc >= 0.2 and sc > 0.4:
        x= (0.0, 0.6669, 0.3331)
    elif sc >= 0.1 and sc < 0.2:
        x= (0.0, 0.3331, 0.6669) # nearing the end - move to best ever
    else:
        x = (0.0,0.0,1.0)
    return(x)


def bounded(x):
    if x < 0.001:
        return(0.001)
    elif x > 0.999:
        return(0.999)
    else:
        return(x)


def checkConvergence(s, nodes):
    normfactor = (0.999-0.001) * len(nodes)
    ps = [p for (i,(a,b,c,p,e)) in nodes.items()]
    convergence = 1.0 - 2.0 * (( sum(map(convNum, ps)) / normfactor ) - 0.5 )
    pToKRatio = (sum (ps)) / ((0.999-0.001) * s["k"])
    s["c"] = convergence
    s["pTokRatio"] = pToKRatio
    return(s)

def divn(x, n):
    round(x/n)

def convNum(x):
    return(max(0.999-x, x-0.001))


