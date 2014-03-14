


def initProgramState (args):
    configText  = open(args[0], 'r').read().split("\n")
    programArgs = filter (lambda zed: zed is not None , map(lambda x: parser(x), configText)) 
    programState = {"runs" : int(programArgs[0]),
                    "ants" : int(programArgs[1]),
                    "ct"   : float(programArgs[2]),
                    "local": float(programArgs[3]),
                    "evap" : float(programArgs[4]),
                    "damp" : float(programArgs[5]),
                    "alph" : float(programArgs[6]),
                    "beta" : float(programArgs[7]),
                    "tx"   : float(programArgs[8]),
                    "rx"   : float(programArgs[9]),
                    "bestEver" : (0.0, []),
                    "bestRest" : (0.0, []),
                    "bestIter" : (0.0, []),
                    "config" : args[0],
                    "graphfile" : args[1],
                    "c" : 1.0,
                    "k"    : float(programArgs[10]),
                    "ptoKratio" : 0.0,
                    "runsDone" : 0}
    return(programState)


def parser(x):
    a = x.strip()
    b = a.split(':')
    if len(b) > 1:
        return (b[1].strip())
