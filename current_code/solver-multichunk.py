from msread import *
from time import time
import math
import cykernels

def compute_jhr(obser_arr, model_arr, gains, t_int=1, f_int=1):
    """
    This function computes the (J^H)R term of the GN/LM method for the
    full-polarisation, phase-only case.

    Args:
        obser_arr (np.array): Array containing the observed visibilities.
        model_arr (np.array): Array containing the model visibilities.
        gains (np.array): Array containing the current gain estimates.

    Returns:
        jhr (np.array): Array containing the result of computing (J^H)R.
    """

    out_shape = list(obser_arr.shape)
    out_shape[-3:] = [2,2]

    tmp_array1 = np.empty([2,2], dtype=np.complex128)
    tmp_array2 = np.zeros(out_shape, dtype=np.complex128)

    cykernels.compute_rgmh(obser_arr, gains, model_arr.transpose([0,1,3,2,4,5]),
                          tmp_array1, tmp_array2, t_int, f_int)

    if (f_int>1) or (t_int>1):

        reduced_shape = list(tmp_array2.shape)
        reduced_shape[0] = int(math.ceil(reduced_shape[0]/t_int))
        reduced_shape[1] = int(math.ceil(reduced_shape[1]/f_int))

        interval_array = np.zeros(reduced_shape, dtype=np.complex128)
        cykernels.interval_reduce(tmp_array2, interval_array, t_int, f_int)
        tmp_array2 = interval_array

        out_shape = reduced_shape

    out_shape[-1] = 1
    tmp_array1 = np.empty(out_shape, dtype=np.complex128)
    cykernels.compute_ghirmgh(gains.conj(), tmp_array2, tmp_array1)

    jhr = -2 * tmp_array1.imag

    return jhr


def compute_jhjinv(model_arr, t_int=1, f_int=1):
    """
    This function computes the ((J^H)J)^-1 term of the GN/LM method for the
    full-polarisation, phase-only case. Note that this depends only on the
    model visibilities.

    Args:
        model_arr (np.array): Array containing the model visibilities.

    Returns:
        jhjinv (np.array): Array containing the result of computing ((J^H)J)^-1.
    """

    jhjinv_shape = list(model_arr.shape)
    jhjinv_shape[-3:] = [2,2]

    jhjinv_shape[0] = int(math.ceil(jhjinv_shape[0]/t_int))
    jhjinv_shape[1] = int(math.ceil(jhjinv_shape[1]/f_int))

    jhjinv = np.zeros(jhjinv_shape, dtype=np.float64)
    cykernels.compute_jhj(model_arr, jhjinv, t_int, f_int)
    cykernels.invert_jhj(jhjinv)

    return jhjinv


def compute_update(model_arr, obser_arr, gains, jhjinv, t_int=1, f_int=1):
    """
    This function computes the update step of the GN/LM method. This is
    equivalent to the complete (((J^H)J)^-1)(J^H)R.

    Args:
        obser_arr (np.array): Array containing the observed visibilities.
        model_arr (np.array): Array containing the model visibilities.
        gains (np.array): Array containing the current gain estimates.
        jhjinv (np.array): Array containing (J^H)J)^-1. (Invariant)

    Returns:
        update (np.array): Array containing the result of computing
            (((J^H)J)^-1)(J^H)R
    """

    jhr = compute_jhr(obser_arr, model_arr, gains, t_int, f_int)

    update = np.empty_like(jhr)

    cykernels.compute_update(jhjinv, jhr, update)

    return update


def compute_residual(obser_arr, model_arr, gains, t_int=1, f_int=1):
    """
    This function computes the residual. This is the difference between the
    observed data, and the model data with the gains applied to it.

    Args:
        obser_arr (np.array): Array containing the observed visibilities.
        model_arr (np.array): Array containing the model visibilities.
        gains (np.array): Array containing the current gain estimates.

    Returns:
        residual (np.array): Array containing the result of computing D-GMG^H.
    """

    gmgh = np.empty_like(obser_arr)
    cykernels.apply_gains(gains, gains.conj(), model_arr, gmgh, t_int, f_int)

    residual = obser_arr - gmgh

    return residual


def full_pol_phase_only(model_arr, obser_arr, min_delta_g=1e-3, maxiter=30,
                        chi_tol=1e-6, chi_interval=5, t_int=1, f_int=1):
    """
    This function is the main body of the GN/LM method. It handles iterations
    and convergence tests.

    Args:
        obser_arr (np.array): Array containing the observed visibilities.
        model_arr (np.array): Array containing the model visibilities.
        min_delta_g (float): Gain improvement threshold.
        maxiter (int): Maximum number of iterations allowed.
        chi_tol (float): Chi-squared improvement threshold.
        chi_interval (int): Interval at which the chi-squared test is performed.

    Returns:
        gains (np.array): Array containing the final gain estimates.
    """

    phase_shape = list(model_arr.shape)
    phase_shape[-3:] = [2, 1]
    phase_shape[0] = int(math.ceil(phase_shape[0]/t_int))
    phase_shape[1] = int(math.ceil(phase_shape[1]/f_int))

    phases = np.zeros(phase_shape, dtype=np.float64)

    gain_shape = list(model_arr.shape)
    gain_shape[-3:] = [2, 2]
    gain_shape[0] = int(math.ceil(gain_shape[0]/t_int))
    gain_shape[1] = int(math.ceil(gain_shape[1]/f_int))

    gains = np.zeros(gain_shape, dtype=np.complex128)
    gains[...,(0,1),(0,1)] = np.exp(-1j*phases)[...,(0,1),(0,0)]

    delta_g = 1
    iters = 0
    chi = np.inf

    jhjinv = compute_jhjinv(model_arr, t_int, f_int)

    while delta_g > min_delta_g:

        if iters % 2 == 0:
            fact = 0.5
        else:
            fact = 1

        phases += fact*compute_update(model_arr, obser_arr, gains, jhjinv,
                                      t_int, f_int)

        delta_g = gains.copy()

        gains[...,(0,1),(0,1)] = np.exp(-1j*phases)[...,(0,1),(0,0)]

        iters += 1

        if iters > maxiter:
            return gains

        if (iters % chi_interval) == 0:
            old_chi = chi
            chi = np.linalg.norm(compute_residual(obser_arr, model_arr, gains,
                                                  t_int, f_int))
            if (old_chi - chi) < chi_tol:
                return gains
            if old_chi < chi:
                print "Bad solutions."
                return gains

        delta_g = np.linalg.norm(delta_g - gains)

    return gains


def apply_gains(obser_arr, gains, t_int=1, f_int=1):
    """
    Applies the inverse of the gain estimates to the observed data matrix.

    Args:
        obser_arr (np.array): Array of the observed visibilities.
        gains (np.array): Array of the gain estimates.

    Returns:
        inv_gdgh (np.array): Array containing (G^-1)D(G^-H).
    """

    inv_gains = np.transpose(gains[..., ::-1, ::-1], axes=[0, 1, 2, 4, 3])

    inv_gains = np.array([[1, -1], [-1, 1]]) * inv_gains

    inv_gains *= 1./(gains[..., 0, 0] * gains[..., 1, 1]
                   - gains[..., 0, 1] * gains[..., 1, 0])[..., None, None]

    inv_gdgh = np.empty_like(obser_arr)
    cykernels.apply_gains(inv_gains, inv_gains.conj(), obser_arr, inv_gdgh,
                          t_int, f_int)

    return inv_gdgh


ms = DataHandler("WESTERBORK_POINT.MS")
ms.fetch_all()
ms.define_chunk(100, 64)

t_int, f_int = 4., 4.

t0 = time()
for b, a in ms:
    gains = full_pol_phase_only(a, b, t_int=t_int, f_int=f_int)
    corr_vis = apply_gains(b, gains, t_int=t_int, f_int=f_int)
    ms.array_to_vis(corr_vis, ms._first_t, ms._last_t, ms._first_f, ms._last_f)
print time() - t0

ms.save(ms.covis, "CORRECTED_DATA")
