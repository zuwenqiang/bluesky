''' This module provides the Conflict Detection base class. '''
import numpy as np

import bluesky as bs
from bluesky.tools.aero import ft, nm
from bluesky.tools.replaceable import ReplaceableSingleton
from bluesky.tools.trafficarrays import TrafficArrays, RegisterElementParameters


bs.settings.set_variable_defaults(asas_pzr=5.0, asas_pzh=1000.0,
                                  asas_dtlookahead=300.0)


class ConflictDetection(ReplaceableSingleton, TrafficArrays):
    ''' Base class for Conflict Detection implementations. '''
    def __init__(self):
        TrafficArrays.__init__(self)
        # [s] lookahead time
        self.dtnolook_def = 0.0
        self.dtlook_def = bs.settings.asas_dtlookahead
        self.rpz_def = bs.settings.asas_pzr * nm
        self.hpz_def = bs.settings.asas_pzh * ft

        # Conflicts and LoS detected in the current timestep (used for resolving)
        self.confpairs = list()
        self.lospairs = list()
        self.qdr = np.array([])
        self.dist = np.array([])
        self.dcpa = np.array([])
        self.tcpa = np.array([])
        self.tLOS = np.array([])
        # Unique conflicts and LoS in the current timestep (a, b) = (b, a)
        self.confpairs_unique = set()
        self.lospairs_unique = set()

        # All conflicts and LoS since simt=0
        self.confpairs_all = list()
        self.lospairs_all = list()

        # Per-aircraft conflict data
        with RegisterElementParameters(self):
            self.inconf = np.array([], dtype=bool)  # In-conflict flag
            self.tcpamax = np.array([]) # Maximum time to CPA for aircraft in conflict
            # [m] Horizontal separation minimum for detection
            self.rpz = np.array([])
            # [m] Vertical separation minimum for detection
            self.hpz = np.array([])
            self.dtlookahead = np.array([])
            self.dtnolook = np.array([])

    def clearconfdb(self):
        ''' Clear conflict database. '''
        self.confpairs_unique.clear()
        self.lospairs_unique.clear()
        self.confpairs.clear()
        self.lospairs.clear()
        self.qdr = np.array([])
        self.dist = np.array([])
        self.dcpa = np.array([])
        self.tcpa = np.array([])
        self.tLOS = np.array([])
        self.inconf = np.zeros(bs.traf.ntraf)
        self.tcpamax = np.zeros(bs.traf.ntraf)

    def reset(self):
        super().reset()
        self.clearconfdb()
        self.confpairs_all.clear()
        self.lospairs_all.clear()
        self.dtlook_def = bs.settings.asas_dtlookahead
        self.dtnolook_def = 0.0
        self.rpz_def = bs.settings.asas_pzr * nm
        self.hpz_def = bs.settings.asas_pzh * ft

    def create(self, n=1):
        super().create(n)
        self.rpz[-n:] = self.rpz_def
        self.hpz[-n:] = self.hpz_def
        self.dtlookahead[-n:] = self.dtlook_def
        self.dtnolook[-n:] = self.dtnolook_def


    @classmethod
    def setmethod(cls, name=''):
        ''' Select a CD method. '''
        # Get a dict of all registered CD methods
        methods = cls.derived()
        names = ['OFF' if n == 'CONFLICTDETECTION' else n for n in methods]
        if not name:
            curname = 'OFF' if cls.selected() is ConflictDetection else cls.selected().__name__
            return True, f'Current CD method: {curname}' + \
                         f'\nAvailable CD methods: {", ".join(names)}'
        # Check if the requested method exists
        if name == 'OFF':
            # Select the base method and clear the conflict database
            ConflictDetection.select()
            ConflictDetection.instance().clearconfdb()
            return True, 'Conflict Detection turned off.'
        if name == 'ON':
            # Just select the first CD method in the list
            name = next(n for n in names if n != 'OFF')
        method = methods.get(name, None)
        if method is None:
            return False, f'{name} doesn\'t exist.\n' + \
                          f'Available CD methods: {", ".join(names)}'

        # Select the requested method
        method.select()
        ConflictDetection.instance().clearconfdb()
        return True, f'Selected {method.__name__} as CD method.'

    def setrpz(self, value=None, idx=None):
        ''' Set the horizontal separation distance. '''
        if value is None:
            if idx is None:
                return True, f"Default PZ radius is set to {self.rpz_def / nm} NM"
            return True, ("Current PZ radius for selected aircraft: %.2f NM" % (self.rpz[idx] / nm))
        if idx is None:
            # When no aircraft given, change default value
            self.rpz_def = value * nm
            return True, f"Setting default PZ radius to {value} NM"
        self.rpz[idx] = value * nm
        return True, f"Setting PZ radius to {value} NM for selected aircraft"

    def sethpz(self, value=None, idx=None):
        ''' Set the vertical separation distance. '''
        if value is None:
            if idx is None:
                return True, f"Default PZ height is set to {self.hpz_def / nm} ft"
            return True, ("Current PZ height for selected aircraft: %.2f ft" % (self.hpz[idx] / ft))
        if idx is None:
            # When no aircraft given, change default value
            self.hpz_def = value * nm
            return True, f"Setting default PZ height to {value} ft"
        self.hpz[idx] = value * ft
        return True, f"Setting PZ height to {value} ft for selected aircraft"

    def setdtlook(self, value=None, idx=None):
        ''' Set the lookahead time for conflict detection. '''
        if value is None:
            if idx is None:
                return True, f"Default lookahead time: {self.dtlook_def} sec"
            return True, f"Lookahead time for selected aircraft: {self.dtlookahead[idx]}"
        if idx is None:
            self.dtlook_def = value
            return True, f"Setting default lookahead time to {value} sec"
        self.dtlookahead[idx] = value
        return True, f"Setting lookahead time to {value} sec for selected aircraft"

    def setdtnolook(self, value=None, idx=None):
        ''' Set the interval in which conflict detection is skipped after a
            conflict resolution. '''
        if value is None:
            if idx is None:
                return True, f"Default nolook time: {self.dtnolook_def} sec"
            return True, f"Nolook time for selected aircraft: {self.dtnolook[idx]}"
        if idx is None:
            self.dtnolook_def = value
            return True, f"Setting default nolook time to {value} sec"
        self.dtnolook[idx] = value
        return True, f"Setting nolook time to {value} sec for selected aircraft"

    def update(self, ownship, intruder):
        ''' Perform an update step of the Conflict Detection implementation. '''
        print('Detection step, simt =', bs.sim.simt)
        self.confpairs, self.lospairs, self.inconf, self.tcpamax, self.qdr, \
            self.dist, self.dcpa, self.tcpa, self.tLOS = \
                self.detect(ownship, intruder, self.rpz, self.hpz, self.dtlookahead)

        # confpairs has conflicts observed from both sides (a, b) and (b, a)
        # confpairs_unique keeps only one of these
        confpairs_unique = {frozenset(pair) for pair in self.confpairs}
        lospairs_unique = {frozenset(pair) for pair in self.lospairs}

        self.confpairs_all.extend(confpairs_unique - self.confpairs_unique)
        self.lospairs_all.extend(lospairs_unique - self.lospairs_unique)

        # Update confpairs_unique and lospairs_unique
        self.confpairs_unique = confpairs_unique
        self.lospairs_unique = lospairs_unique

    def detect(self, ownship, intruder, rpz, hpz, dtlookahead):
        ''' 
            Detect any conflicts between ownship and intruder.
            This function should be reimplemented in a subclass for actual
            detection of conflicts. See for instance
            bluesky.traffic.asas.statebased.
        '''
        confpairs = []
        lospairs = []
        inconf = np.zeros(ownship.ntraf)
        tcpamax = np.zeros(ownship.ntraf)
        qdr = np.array([])
        dist = np.array([])
        dcpa = np.array([])
        tcpa = np.array([])
        tLOS = np.array([])
        return confpairs, lospairs, inconf, tcpamax, qdr, dist, dcpa, tcpa, tLOS
