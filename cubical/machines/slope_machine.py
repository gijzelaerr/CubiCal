# CubiCal: a radio interferometric calibration suite
# (c) 2017 Rhodes University & Jonathan S. Kenyon
# http://github.com/ratt-ru/CubiCal
# This code is distributed under the terms of GPLv2, see LICENSE.md for details
from cubical.machines.parameterised_machine import ParameterisedGains
import numpy as np
from cubical.flagging import FL
from numpy.ma import masked_array

import cubical.kernels.cytf_plane
import cubical.kernels.cyf_slope   
import cubical.kernels.cyt_slope

def _normalize(x, dtype):
    """
    Helper function: normalizes array to [0,1] interval.
    """
    if len(x) > 1:
        return ((x - x[0]) / (x[-1] - x[0])).astype(dtype)
    elif len(x) == 1:
        return np.zeros(1, dtype)
    else:
        return x


class PhaseSlopeGains(ParameterisedGains):
    """
    This class implements the diagonal phase-only parameterised slope gain machine.
    """

    def __init__(self, label, data_arr, ndir, nmod, chunk_ts, chunk_fs, chunk_label, options):
        """
        Initialises a diagonal phase-slope gain machine.
        
        Args:
            label (str):
                Label identifying the Jones term.
            data_arr (np.ndarray): 
                Shape (n_mod, n_tim, n_fre, n_ant, n_ant, n_cor, n_cor) array containing observed 
                visibilities. 
            ndir (int):
                Number of directions.
            nmod (nmod):
                Number of models.
            chunk_ts (np.ndarray):
                Times for the data being processed.
            chunk_fs (np.ndarray):
                Frequencies for the data being processsed.
            options (dict): 
                Dictionary of options. 
        """
        
        ParameterisedGains.__init__(self, label, data_arr, ndir, nmod,
                                    chunk_ts, chunk_fs, chunk_label, options)

        self.slope_type = options["type"]
        self.n_param = 3 if self.slope_type == "tf-plane" else 2

        self.param_shape = [self.n_dir, self.n_timint, self.n_freint, 
                            self.n_ant, self.n_param, self.n_cor, self.n_cor]
        self.slope_params = np.zeros(self.param_shape, dtype=self.ftype)

        self.chunk_ts = _normalize(chunk_ts, self.ftype)
        self.chunk_fs = _normalize(chunk_fs, self.ftype)

        if self.slope_type == "tf-plane":
            self.cyslope = cubical.kernels.cytf_plane
        elif self.slope_type == "f-slope":
            self.cyslope = cubical.kernels.cyf_slope
        elif self.slope_type == "t-slope":
            self.cyslope = cubical.kernels.cyt_slope    
            
    @staticmethod
    def exportable_solutions():
        """ Returns a dictionary of exportable solutions for this machine type. """

        exportables = ParameterisedGains.exportable_solutions()

        exportables.update({
            "offset": (0., ("dir", "time", "freq", "ant", "corr")),
            "delay":  (0., ("dir", "time", "freq", "ant", "corr")),
            "rate":   (0., ("dir", "time", "freq", "ant", "corr")),
        })
        
        return exportables

    def importable_solutions(self):
        """ Returns a dictionary of importable solutions for this machine type. """

        # defines solutions we can import from
        # Note that complex gain (as a derived parameter) is exported, but not imported

        return { "offset": self.interval_grid,
                 "delay":  self.interval_grid,
                 "rate":   self.interval_grid  }
        
    def export_solutions(self):
        """ Saves the solutions to a dict of {label: solutions,grids} items. """

        solutions = ParameterisedGains.export_solutions(self)

        if self.slope_type=="tf-plane":
            solutions.update({
                 "offset": (masked_array(self.slope_params[...,2,(0,1),(0,1)]), self.interval_grid),
                 "delay":  (masked_array(self.slope_params[...,0,(0,1),(0,1)]), self.interval_grid),
                 "rate":   (masked_array(self.slope_params[...,1,(0,1),(0,1)]), self.interval_grid),
            })
        elif self.slope_type=="f-slope":
            solutions.update({
             "offset": (masked_array(self.slope_params[...,1,(0,1),(0,1)]), self.interval_grid),
             "delay":  (masked_array(self.slope_params[...,0,(0,1),(0,1)]), self.interval_grid),
            })
        elif self.slope_type=="t-slope":
            solutions.update({
             "offset": (masked_array(self.slope_params[...,1,(0,1),(0,1)]), self.interval_grid),
             "rate":   (masked_array(self.slope_params[...,0,(0,1),(0,1)]), self.interval_grid),
            })
        return solutions

    def import_solutions(self, soldict):
        """ 
        Loads solutions from a dict. 
        
        Args:
            soldict (dict):
                Contains gains solutions which must be loaded.
        """
        
        # Note that this is inherently very flexible. For example, we can init from a solutions
        # table which only has a "phase" entry, e.g. one generated by a phase_only solver (and the
        # delay will then be left at zero).
        
        if self.slope_type=="tf-plane":
            phase = soldict.get("offset")
            delay = soldict.get("delay")
            rate = soldict.get("rate")
            if phase is not None:
                self.slope_params[...,2,(0,1),(0,1)] = phase
            if delay is not None:
                self.slope_params[...,0,(0,1),(0,1)] = delay
            if rate is not None:
                self.slope_params[...,1,(0,1),(0,1)] = rate
            # if any were loaded, convert into complex gains
            if phase is not None or delay is not None or rate is not None:
                self.cyslope.cyconstruct_gains(self.slope_params, self.gains, self.chunk_ts, 
                                               self.chunk_fs, self.t_int, self.f_int)
        
        elif self.slope_type=="f-slope":
            phase = soldict.get("offset")
            delay = soldict.get("delay")
            if phase is not None:
                self.slope_params[...,1,(0,1),(0,1)] = phase
            if delay is not None:
                self.slope_params[...,0,(0,1),(0,1)] = delay
            # if either was loaded, convert into complex gains
            if phase is not None or delay is not None:
                self.cyslope.cyconstruct_gains(self.slope_params, self.gains, self.chunk_fs,
                                               self.t_int, self.f_int)

        elif self.slope_type=="t-slope":
            phase = soldict.get("offset")
            rate = soldict.get("rate")
            if phase is not None:
                self.slope_params[...,1,(0,1),(0,1)] = phase
            if delay is not None:
                self.slope_params[...,0,(0,1),(0,1)] = rate
            # if either was loaded, convert into complex gains
            if phase is not None or rate is not None:
                self.cyslope.cyconstruct_gains(self.slope_params, self.gains, self.chunk_ts,
                                               self.t_int, self.f_int)


    def compute_js(self, obser_arr, model_arr):
        """
        This function computes the J\ :sup:`H`\R term of the GN/LM method. 

        Args:
            obser_arr (np.ndarray): 
                Shape (n_mod, n_tim, n_fre, n_ant, n_ant, n_cor, n_cor) array containing the 
                observed visibilities.
            model_arr (np.ndrray): 
                Shape (n_dir, n_mod, n_tim, n_fre, n_ant, n_ant, n_cor, n_cor) array containing the 
                model visibilities.

        Returns:
            np.ndarray:
                J\ :sup:`H`\R
        """

        n_dir, n_tim, n_fre, n_ant, n_cor, n_cor = self.gains.shape

        gh = self.gains.transpose(0,1,2,3,5,4).conj()

        jh = np.zeros_like(model_arr)

        self.cyslope.cycompute_jh(model_arr, self.gains, jh, 1, 1)

        tmp_jhr_shape = [n_dir, n_tim, n_fre, n_ant, n_cor, n_cor]

        tmp_jhr = np.zeros(tmp_jhr_shape, dtype=obser_arr.dtype)

        if n_dir > 1:
            resid_arr = np.empty_like(obser_arr)
            r = self.compute_residual(obser_arr, model_arr, resid_arr)
        else:
            r = obser_arr

        self.cyslope.cycompute_tmp_jhr(gh, jh, r, tmp_jhr, 1, 1)

        tmp_jhr = tmp_jhr.imag

        jhr_shape = [n_dir, self.n_timint, self.n_freint, n_ant, self.n_param, n_cor, n_cor]

        jhr = np.zeros(jhr_shape, dtype=tmp_jhr.dtype)

        if self.slope_type=="tf-plane":
            self.cyslope.cycompute_jhr(tmp_jhr, jhr, self.chunk_ts, self.chunk_fs, self.t_int, self.f_int)
        elif self.slope_type=="f-slope":
            self.cyslope.cycompute_jhr(tmp_jhr, jhr, self.chunk_fs, self.t_int, self.f_int)
        elif self.slope_type=="t-slope":
            self.cyslope.cycompute_jhr(tmp_jhr, jhr, self.chunk_ts, self.t_int, self.f_int)

        return jhr, self.jhjinv, 0

    def implement_update(self, jhr, jhjinv):
        update = np.zeros_like(jhr)

        self.cyslope.cycompute_update(jhr, jhjinv, update)

        if self.iters%2 == 0:
            self.slope_params += 0.5*update
        else:
            self.slope_params += update

        self.restrict_solution()

        # Need to turn updated parameters into gains.

        if self.slope_type=="tf-plane":
            self.cyslope.cyconstruct_gains(self.slope_params, self.gains, self.chunk_ts, self.chunk_fs, self.t_int, self.f_int)
        elif self.slope_type=="f-slope":
            self.cyslope.cyconstruct_gains(self.slope_params, self.gains, self.chunk_fs, self.t_int, self.f_int)
        elif self.slope_type=="t-slope":
            self.cyslope.cyconstruct_gains(self.slope_params, self.gains, self.chunk_ts, self.t_int, self.f_int)

    def compute_residual(self, obser_arr, model_arr, resid_arr):
        """
        This function computes the residual. This is the difference between the
        observed data, and the model data with the gains applied to it.

        Args:
            obser_arr (np.ndarray): 
                Shape (n_mod, n_tim, n_fre, n_ant, n_ant, n_cor, n_cor) array containing the 
                observed visibilities.
            model_arr (np.ndrray): 
                Shape (n_dir, n_mod, n_tim, n_fre, n_ant, n_ant, n_cor, n_cor) array containing the 
                model visibilities.
            resid_arr (np.ndarray): 
                Shape (n_mod, n_tim, n_fre, n_ant, n_ant, n_cor, n_cor) array into which the 
                computed residuals should be placed.

        Returns:
            np.ndarray: 
                Array containing the result of computing D - GMG\ :sup:`H`.
        """
        
        gains_h = self.gains.transpose(0,1,2,3,5,4).conj()

        resid_arr[:] = obser_arr

        self.cyslope.cycompute_residual(model_arr, self.gains, gains_h, resid_arr, 1, 1)

        return resid_arr

    def apply_inv_gains(self, resid_arr, corr_vis=None):
        """
        Applies the inverse of the gain estimates to the observed data matrix.

        Args:
            obser_arr (np.ndarray): 
                Shape (n_mod, n_tim, n_fre, n_ant, n_ant, n_cor, n_cor) array containing the 
                observed visibilities.
            corr_vis (np.ndarray or None, optional): 
                if specified, shape (n_mod, n_tim, n_fre, n_ant, n_ant, n_cor, n_cor) array 
                into which the corrected visibilities should be placed.

        Returns:
            np.ndarray: 
                Array containing the result of G\ :sup:`-1`\DG\ :sup:`-H`.
        """

        g_inv = self.gains.conj()

        gh_inv = g_inv.conj()

        if corr_vis is None:                
            corr_vis = np.empty_like(resid_arr)

        self.cyslope.cycompute_corrected(resid_arr, g_inv, gh_inv, corr_vis, 1, 1)

        return corr_vis, 0   # no flags raised here, since phase-only always invertible

    def restrict_solution(self):
        """
        Restricts the solution by invoking the inherited restrict_soultion method and applying
        any machine specific restrictions.
        """

        ParameterisedGains.restrict_solution(self)
        
        if self.ref_ant is not None:
            self.slope_params -= self.slope_params[:,:,:,self.ref_ant,:,:,:][:,:,:,np.newaxis,:,:,:]
        for idir in self.fix_directions:
            self.slope_params[idir, ...] = 0

    def precompute_attributes(self, model_arr, flags_arr, inv_var_chan):
        """
        Precompute (J\ :sup:`H`\J)\ :sup:`-1`, which does not vary with iteration.

        Args:
            model_arr (np.ndarray):
                Shape (n_dir, n_mod, n_tim, n_fre, n_ant, n_ant, n_cor, n_cor) array containing 
                model visibilities.
        """
        ParameterisedGains.precompute_attributes(self, model_arr, flags_arr, noise)

        tmp_jhj_shape = [self.n_dir, self.n_mod, self.n_tim, self.n_fre, self.n_ant, 2, 2] 

        tmp_jhj = np.zeros(tmp_jhj_shape, dtype=self.dtype)

        self.cyslope.cycompute_tmp_jhj(model_arr, tmp_jhj)

        blocks_per_inverse = 6 if self.slope_type=="tf-plane" else 3

        jhj_shape = [self.n_dir, self.n_timint, self.n_freint, self.n_ant, blocks_per_inverse, 2, 2]

        jhj = np.zeros(jhj_shape, dtype=self.ftype)

        if self.slope_type=="tf-plane":
            self.cyslope.cycompute_jhj(tmp_jhj.real, jhj, self.chunk_ts, self.chunk_fs, self.t_int, self.f_int)
        elif self.slope_type=="f-slope":
            self.cyslope.cycompute_jhj(tmp_jhj.real, jhj, self.chunk_fs, self.t_int, self.f_int)
        elif self.slope_type=="t-slope":
            self.cyslope.cycompute_jhj(tmp_jhj.real, jhj, self.chunk_ts, self.t_int, self.f_int)

        self.jhjinv = np.zeros(jhj_shape, dtype=self.ftype)

        self.cyslope.cycompute_jhjinv(jhj, self.jhjinv, self.eps)
