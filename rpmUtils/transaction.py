#!/usr/bin/python

#
# Client code for Update Agent
# Copyright (c) 1999-2002 Red Hat, Inc.  Distributed under GPL.
#
#         Adrian Likins <alikins@redhat.com>
# Some Edits by Seth Vidal <skvidal@phy.duke.edu>
#
# a couple of classes wrapping up transactions so that we  
#    can share transactions instead of creating new ones all over
#

import rpm
import miscutils
from sets import Set

read_ts = None
ts = None

# wrapper/proxy class for rpm.Transaction so we can
# instrument it, etc easily
class TransactionWrapper:
    def __init__(self, root='/'):
        self.ts = rpm.TransactionSet(root)
        self._methods = ['dbMatch',
                         'check',
                         'order',
                         'addErase',
                         'addInstall',
                         'run',
                         'IDTXload',
                         'IDTXglob',
                         'rollback',
                         'pgpImportPubkey',
                         'pgpPrtPkts',
                         'Debug',
                         'setFlags',
                         'setVSFlags',
                         'setProbFilter',
                         'hdrFromFdno',
                         'next',
                         'clean']
        self.tsflags = []
        self.open = True

    def __del__(self):
        # Automatically close the rpm transaction when the reference is lost
        self.close()

    def close(self):
        if self.open:
            self.ts.closeDB()
            self.ts = None
            self.open = False

    def __getattr__(self, attr):
        if attr in self._methods:
            return self.getMethod(attr)
        else:
            raise AttributeError, attr

    def __iter__(self):
        return self.ts
        
    def getMethod(self, method):
        # in theory, we can override this with
        # profile/etc info
        return getattr(self.ts, method)

    # push/pop methods so we dont lose the previous
    # set value, and we can potentiall debug a bit
    # easier
    def pushVSFlags(self, flags):
        self.tsflags.append(flags)
        self.ts.setVSFlags(self.tsflags[-1])

    def popVSFlags(self):
        del self.tsflags[-1]
        self.ts.setVSFlags(self.tsflags[-1])

    def addTsFlag(self, flag):
        curflags = self.ts.setFlags(0)
        self.ts.setFlags(curflags | flag)

#    def addProblemFilter(self, filt):
#        curfilter = self.ts.setProbFilter(0)
#        self.ts.setProbFilter(cutfilter | filt)    
        
    def test(self, cb, conf={}):
        """tests the ts we've setup, takes a callback function and a conf dict 
           for flags and what not"""
    
        self.addTsFlag(rpm.RPMTRANS_FLAG_TEST)
        # FIXME GARBAGE - remove once this is reimplemented elsehwere
        # KEEPING FOR API COMPLIANCE ONLY
        if conf.has_key('diskspacecheck'):
            if conf['diskspacecheck'] == 0:
                self.ts.setProbFilter(rpm.RPMPROB_FILTER_DISKSPACE)
        tserrors = self.ts.run(cb.callback, '')
    
        reserrors = []
        if tserrors:
            for (descr, (etype, mount, need)) in tserrors:
                reserrors.append(descr)
        
        return reserrors
            
        
    def returnLeafNodes(self):
        """returns a list of package tuples (n,a,e,v,r) that are not required by
           any other package on the system"""
        
        req = {}
        orphan = []
    
        mi = self.dbMatch()
        if mi is None: # this is REALLY unlikely but let's just say it for the moment
            return orphan    
            
        for h in mi:
            tup = miscutils.pkgTupleFromHeader(h)    
            if not h[rpm.RPMTAG_REQUIRENAME]:
                continue
            for r in h[rpm.RPMTAG_REQUIRENAME]:
                if not req.has_key(r):
                    req[r] = Set()
                req[r].add(tup)
     
     
        mi = self.dbMatch()
        if mi is None:
            return orphan
     
        for h in mi:
            preq = 0
            tup = miscutils.pkgTupleFromHeader(h)
            for p in h[rpm.RPMTAG_PROVIDES] + h[rpm.RPMTAG_FILENAMES]:
                if req.has_key(p):
                    # Don't count a package that provides its require
                    s = req[p]
                    if len(s) > 1 or tup not in s:
                        preq = preq + 1
        
            if preq == 0:
                orphan.append(tup)
        
        return orphan

        
def initReadOnlyTransaction(root='/'):
    read_ts =  TransactionWrapper(root=root)
    read_ts.pushVSFlags((rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
    return read_ts

