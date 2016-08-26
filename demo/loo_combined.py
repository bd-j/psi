import sys, time
import numpy as np
import matplotlib.pyplot as pl
from matplotlib.backends.backend_pdf import PdfPages

import h5py
from psi.model import SimplePSIModel
from psi.utils import dict_struct
from psi.plotting import *

lightspeed = 2.998e18
from combined_params import bounds, features

class CombinedInterpolator(SimplePSIModel):

    def load_training_data(self, training_data='', c3k_weight=1e-1,
                           snr_threshold=1e-10, **extras):
        # --- read the data ---
        with h5py.File(training_data, "r") as f:
            self.wavelengths = f['wavelengths'][:]
            self.library_spectra = f['spectra'][:]
            self.library_labels = f['parameters'][:]
            unc = f['uncertainties'][:]

        # Weighting stuff
        self.c3k_weight = c3k_weight
        self.library_snr = self.library_spectra / unc #* 0.0 + 1.0
        self.has_errors = True

        # --- set negative (or very low) S/N fluxes to zero weight ---
        bad = (self.library_snr < snr_threshold) | (~np.isfinite(self.library_snr))
        self.bad_flux_value = np.nanmedian(self.library_spectra)
        self.library_spectra[bad] = self.bad_flux_value
        self.library_snr[bad] = 0.0
        
        self.reset_mask()

    def get_weights(self, ind_wave, spec):
        """
        :param spec:
            Flux in linear units of the training spectra
        """

        if (not self.has_errors) or (self.unweighted):
            return None
        else:
            if self.logify_flux:
                # if training log(flux), use relative (S/N)**2 for weights
                relative_weights = self.training_snr[:, ind_wave]**2
            else:
                # else just use the inverse flux variance (S/N)**2 /S**2 
                relative_weights = (self.training_snr[:, ind_wave] / spec)**2

            # --- do relative weighting of c3k ---
            c3k = (self.training_labels['miles_id'] == 'c3k')
            # median of MILES weights.  If zero, just give c3k full weight 
            wmiles = np.nanmedian(relative_weights[~c3k, :], axis=0)
            wmiles[wmiles == 0.] = 1.0
            relative_weights[c3k, :] = (wmiles * self.c3k_weight)[None, :]
                      
            return relative_weights
        
    def build_training_info(self):
        self.reference_index = None
        self.reference_spectrum = self.training_spectra.std(axis=0)

        
if __name__ == "__main__":

    ts = time.time()
    
    c3k_weight = 1e-1 # the relative weight of the CKC models compared to the MILES models.
    regime = 'Warm Giants'
    fake_weights = True
    outroot = '{}_unc={}_cwght={:3.2f}.pdf'.format(regime.replace(' ','_'), not fake_weights, c3k_weight)

    # --- The PSI Model ---
    mlib = '/Users/bjohnson/Projects/psi/data/combined/culled_lib_w_mdwarfs_w_unc_w_c3k.h5'
    spi = CombinedInterpolator(training_data=mlib, c3k_weight=c3k_weight,
                               unweighted=False, logify_flux=True)
    # renormalize by bolometric luminosity
    spi.renormalize_library_spectra(bylabel='luminosity')
    # Use fake, constant SNR for all the MILES spectra
    if fake_weights:
        g = spi.library_snr > 0
        spi.library_snr[g] = 10
    # mask the Mann mdwarf stars for now
    mann = np.where(spi.library_labels['miles_id'] == 'mdwarf')[0]
    c3k = np.where(spi.library_labels['miles_id'] == 'c3k')[0]
    spi.leave_out(mann)
    # Choose parameter regime and features
    spi.select(bounds=bounds[regime], delete=False)
    spi.features = features[regime]

    # --- Leave-one-out ----
    # These are the indices in the full library of the training spectra
    loo_indices = spi.training_indices.copy()
    # Only leave out MILES
    miles = spi.training_labels['miles_id'] != 'c3k'
    loo_indices = loo_indices[miles]
    # build output and other useful arrays
    observed = spi.library_spectra[loo_indices, :]
    obs_unc = observed / spi.library_snr[loo_indices, :]
    predicted = np.zeros([len(loo_indices), spi.n_wave])
    inhull = np.zeros(len(loo_indices), dtype=bool)
    # Loop over spectra to leave out and predict
    for i, j in enumerate(loo_indices):
        if (i % 10) == 0: print('{} of {}'.format(i, len(loo_indices)))
        # Get full sample and the parameters of the star to leave out
        spec = spi.library_spectra[j, :]
        tlabels = spi.library_labels[j]
        labels = dict([(n, tlabels[n]) for n in spi.label_names])
        # Leave one out and re-train
        spi.library_mask[j] = False
        spi.train()
        predicted[i, :] = spi.get_star_spectrum(**labels)
        inhull[i] = spi.inside_hull(labels)
        # now put it back
        spi.library_mask[j] = True

    print('time to retrain {} models: {:.1f}s'.format(len(loo_indices), time.time()-ts))
        
    # --- Calculate statistics ---
    # get fractional residuals
    wmin, wmax = 3800, 7200
    imin = np.argmin(np.abs(spi.wavelengths - wmin))
    imax = np.argmin(np.abs(spi.wavelengths - wmax))
    imin, imax = 0, len(spi.wavelengths) -1
    delta = predicted / observed - 1.0

    var_spectrum = np.nanvar(delta, axis=0)
    bias_spectrum = np.nanmean(delta, axis=0)
    var_total = np.nanvar(delta[:, imin:imax], axis=1)
    # Get chi^2
    snr = 100
    chisq =np.nansum( ((snr * delta)**2)[:,imin:imax], axis=1)

    # --- Make Plots ---

    # Plot the bias and variance spectrum
    sfig, sax = pl.subplots()
    sax.plot(spi.wavelengths, np.sqrt(var_spectrum)*100, label='Dispersion')
    sax.plot(spi.wavelengths, np.abs(bias_spectrum)*100, label='Mean absolute offset')
    sax.set_ylim(0.001, 100)
    sax.set_yscale('log')
    sax.set_ylabel('%')
    sax.legend(loc=0)
    sfig.show()

    # Plot a map of total variance as a function of label
    labels = spi.library_labels[loo_indices]
    quality, quality_label = np.log(chisq), r'$log \, \chi^2$ (S/N={})'.format(snr)
    mapfig, mapaxes = quality_map(lab, quality, quality_label=quality_label)
    #mapfig.savefig('figures/residual_map.pdf')

    # plot zoom ins around individual lines
    with PdfPages('{}_lines.pdf'.format(outroot)) as pdf:
        for i, j in enumerate(loo_indices):
            fig, ax = zoom_lines(spi.wavelengths, predicted[i,:], observed[i,:],
                                 uncertainties=obs_unc[i,:], showlines=showlines)
            values = dict_struct(spi.library_labels[j]),
            values['inhull'] = inhull[i]
            ti = "{name}: teff={teff:4.0f}, logg={logg:3.2f}, feh={feh:3.2f}, In hull={}".format(**values)
            fig.suptitle(ti)
            pdf.savefig(fig)
            pl.close(fig)
            
    print('finished training and plotting in {:.1f}'.format(time.time()-ts))
    