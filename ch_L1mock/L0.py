"""
Implementation of L0 processing on for pathfinder pulsar beams.

L0 includes all correlator side processing, including beam forming,
up-channelization, square accumulation, and initial dedispersion. In the
pathfinder mock up, data is recieved as beam formed baseband data. This module
is based off of the packet assembly package: 'ch_vdif_assembler'.

"""

import logging
import time

import numpy as np
import ch_vdif_assembler

import _L0


logger = logging.getLogger(__name__)


# Vdif processors
# ===============

class BaseIntegrator(ch_vdif_assembler.processor):
    """Abstract base class for basic integrators with call backs."""

    call_back = lambda self, t0, intensity, weight: None

    def __init__(self, nsamp_integrate=512, **kwargs):
        super(BaseIntegrator, self).__init__(**kwargs)
        self._nsamp_integrate = nsamp_integrate

    def process_chunk(self, t0, nt, efield, mask):
        ninteg = self._nsamp_integrate
        if nt % ninteg:
            msg = ("Number of samples to accumulate (%d) must evenly divide"
                   " number of samples (%d).")
            msg = msg % (ninteg, nt)
            raise ValueError(msg)

        #t0 = time.time()
        intensity, weight = self.square_accumulate(efield, mask)
        #print "Chunk integration time:", time.time() - t0
        self.call_back(t0, intensity, weight)

    def square_accumulate(self, efield, maska):
        raise NotImplementedError("This is just an abstract base class.")


class ReferenceIntegrator(BaseIntegrator):

    def square_accumulate(self, efield, mask):
        ninteg = self._nsamp_integrate

        e_squared = abs(efield)**2
        shape = efield.shape
        new_shape = shape[:-1] + (shape[-1] // ninteg, ninteg)
        e_squared.shape  = new_shape
        mask.shape = new_shape

        # Integrate.
        intensity = np.sum(e_squared, -1, dtype=np.float32)
        weight = np.sum(mask, -1, dtype=np.float32)
        # Normalize for missing data.
        bad_inds = weight == 0
        weight[bad_inds] = 1
        intensity *= ninteg / weight
        # Convert weight to integer between 0 and 255.
        weight *= 255 / ninteg
        weight = np.round(weight).astype(np.uint8)
        weight[bad_inds] = 0

        return intensity, weight


class FastIntegrator(BaseIntegrator):

    byte_data = True

    def square_accumulate(self, efield, mask):
        return _L0.square_accumulate(efield, self._nsamp_integrate)




# Testing Classes
# ===============

class IntegratorComparison(object):

    integrated_chunk1 = None
    integrated_chunk2 = None

    def __init__(self, integrator1, integrator2):
        integrator1.call_back = self.add_integrated_chunk1
        integrator2.call_back = self.add_integrated_chunk2

    def add_integrated_chunk1(self, t0, intensity, weight):
        self.integrated_chunk1 = (t0, intensity, weight)
        if self.integrated_chunk2:
            self.compare()

    def add_integrated_chunk2(self, t0, intensity, weight):
        self.integrated_chunk2 = (t0, intensity, weight)
        if self.integrated_chunk1:
            self.compare()

    def compare(self):
        c1 = self.integrated_chunk1
        c2 = self.integrated_chunk2
        if not np.allclose(c1[0], c2[0]):
            raise RuntimeError("Time stamps don't match")
        if not np.allclose(c1[1], c2[1]):
            raise RuntimeError("Intensity does not match")
        if not np.allclose(c1[2], c2[2]):
            raise RuntimeError("Weight does not match")
        self.integrated_chunk1 = None
        self.integrated_chunk2 = None
        print "Passed!"



