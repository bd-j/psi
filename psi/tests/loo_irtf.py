import sys, time
import numpy as np
import matplotlib.pyplot as pl
from psi.library_models import MILESInterpolator
from badstar import allbadstars

ts = time.time()

def reselect(spi, mlib, bad_ids, bounds, normwave=1.0):
    """Select a training set using bounds and removing bad stars listed by miles_id
    """
    spi.load_training_data(training_data=mlib)
    ind = [spi.training_labels['miles_id'].tolist().index(b) for b in bad_ids
           if b in spi.training_labels['miles_id']]
    spi.leave_out(ind)
    spi.restrict_sample(bounds=bounds)
    spi.renormalize_training_spectra(bylabel='luminosity')
    return spi

# The PSI Model
mlib = '/Users/bjohnson/Projects/psi/data/irtf/irtf_prugniel_extended.h5'
fgk_bounds = {'teff': (3000.0, 10000.0)}
spi = MILESInterpolator(training_data=mlib, normalize_labels=False)
badstar_ids = np.array(allbadstars.tolist())
spi.features = (['logt'], ['feh'], ['logg'],
                ['logt', 'logt'], ['feh', 'feh'], ['logg', 'logg'],
                ['logt', 'feh'], ['logg', 'logt'], ['logg', 'feh'],
                ['logt', 'logt', 'logt'], ['logt', 'logt', 'logt', 'logt'],
                ['logt', 'logt', 'logg']
                )
spi = reselect(spi, mlib, badstar_ids, fgk_bounds)

ntrain = spi.n_train
predicted = np.zeros([ntrain, spi.n_wave])

#sys.exit()
# Retrain and predict after leaving one out
for i in range(ntrain):
    if (i % 10) == 0: print(i)
    # get full sample and the parameters of the star to leave out
    spi = reselect(spi, mlib, badstar_ids, fgk_bounds)
    spec = spi.training_spectra[i,:]
    tlabels = spi.training_labels[i]
    labels = dict([(n, tlabels[n]) for n in spi.label_names])
    # leave one out and train
    spi.leave_out(i)
    spi.train()
    predicted[i, :] = spi.get_star_spectrum(**labels)

# reload the full training set
spi = reselect(spi, mlib, badstar_ids, fgk_bounds)

# get fractional residuals
delta = predicted/spi.training_spectra - 1.0
# get variance in good regions of the spectrum
wave = spi.wavelengths
wmin, wmax = 0.38, 2.4
telluric = [(1.35, 1.43), (1.81, 1.91)]
varinds = (wave > wmin) & (wave < wmax)
for bl, bh in telluric:
    varinds = varinds & ((wave  > bh) | (wave  < bl))
imin = np.argmin(np.abs(spi.wavelengths - wmin))
imax = np.argmin(np.abs(spi.wavelengths - wmax))

var_spectrum = np.nanvar(delta, axis=0)
var_total = np.nanvar(delta[:, varinds], axis=1)

# Determine fraction of pixels contributing half the RMS
sv = np.sort(delta[:, varinds]**2, axis=1)
svc = np.cumsum(sv, axis=1)
svcn = svc/ np.nanmax(svc, axis=-1)[:,None]
half = np.nanargmin(np.abs(svcn - 0.5), axis=1)
npix = np.isfinite(svcn).sum(axis=1)

lines, indlines = {'Ha':6563., 'NaD': 5897.0, 'CaK': 3933.0, 'CaH': 3968, 'Mg5163':5163.1, 'CaT':8544.0}, {}
for l, w in lines.items():
    indlines[l] = np.argmin(np.abs(spi.wavelengths - w/1e4))

# Plot the variance spectrum
sfig, sax = pl.subplots()
sax.plot(spi.wavelengths[imin:imax], np.sqrt(var_spectrum[imin:imax])*100, label='$\sigma(m/o-1)$')
sax.set_xlabel('$\lambda (\mu m)$')
sax.set_ylabel('Fractional RMS (%)')
sax.set_ylim(0, 80)
sfig.show()
sfig.savefig('figures/irtf_residual_spectrum.pdf')

# Plot a map of total variance as a function of label
l1, l2, l3 = 'logt', 'feh', 'logg'
lab = spi.training_labels 
mapfig, mapaxes = pl.subplots(1, 2, figsize=(12.5,7))
sc = mapaxes[0].scatter(lab[l1], lab[l2], marker='o', c=np.sqrt(var_total)*100)
mapaxes[0].set_xlabel(l1)
mapaxes[0].set_ylabel(l2)
sc = mapaxes[1].scatter(lab[l1], lab[l3], marker='o', c=np.sqrt(var_total)*100)
mapaxes[1].set_xlabel(l1)
mapaxes[1].set_ylabel(l3)
mapaxes[1].invert_yaxis()
cbar = pl.colorbar(sc)
cbar.ax.set_ylabel('Fractional RMS (%)')
mapfig.show()                   
mapfig.savefig('figures/irtf_residual_map.pdf')

# Plot a map of line residual as a function of label
showlines = ['CaT']#lines.keys()
for line in showlines:
    vlim = -100, 100
#    if lines[line] < 0.4:
    vlim = -100, 100
    mapfig, mapaxes = pl.subplots(1, 2, figsize=(12.5,7))
    sc = mapaxes[0].scatter(lab[l1], lab[l2], marker='o', c=delta[:, indlines[line]]*100,
                            cmap=pl.cm.coolwarm, vmin=vlim[0], vmax=vlim[1])
    mapaxes[0].set_xlabel(l1)
    mapaxes[0].set_ylabel(l2)
    sc = mapaxes[1].scatter(lab[l1], lab[l3], marker='o', c=delta[:,indlines[line]]*100,
                            cmap=pl.cm.coolwarm, vmin=vlim[0], vmax=vlim[1])
    mapaxes[1].set_xlabel(l1)
    mapaxes[1].set_ylabel(l3)
    mapaxes[1].invert_yaxis()
    cbar = pl.colorbar(sc)
    cbar.ax.set_ylabel('Residual @ {}'.format(line))
    mapfig.show()
    mapfig.savefig('figures/irtf_residual_{}_map.pdf'.format(line))

# Plot cumulative number as a function of RMS
rms = np.sqrt(var_total)*100
rms[~np.isfinite(rms)]=1000
oo = np.argsort(rms)
cfig, cax = pl.subplots()
cax.plot(rms[oo], np.arange(len(oo)))
cax.set_ylabel('N(<RMS)')
cax.set_xlabel('Fractional RMS (%)')
cax.set_xlim(0,100)
cfig.show()
cfig.savefig('figures/irtf_cumlative_rms.pdf')


badfig, badaxes = pl.subplots(10, 1, sharex=True, figsize=(6, 12))
for i, bad in enumerate(oo[-10:][::-1]):
    ax = badaxes[i]
    labels = dict([(n, spi.training_labels[bad][n]) for n in spi.training_labels.dtype.names])
    title = "T={teff:4.0f}, logg={logg:3.2f}, feh={feh:3.1f}".format(**labels)
    ax.plot(spi.wavelengths[imin:imax], predicted[bad, imin:imax], label='predicted')
    ax.plot(spi.wavelengths[imin:imax], spi.training_spectra[bad, imin:imax], label='actual')
    ax.text(0.05, 0.9, "#{}, RMS={:4.1f}%".format(spi.training_labels[bad]['miles_id'], rms[bad]),
            transform=ax.transAxes, fontsize=10)
    ax.text(0.7, 0.05, title, transform=ax.transAxes, fontsize=10)
    print(i)
    
    if i == 0:
        ax.legend(loc=0, prop={'size':8})
    if i < 9:
        ax.set_xticklabels([])
badfig.savefig('figures/irtf_worst10.pdf')
sys.exit()
# compute covariance matrix
dd = delta[:, imin:imax]
dd[~np.isfinite(dd)] = 0.0
cvmat = np.cov(dd.T)

l = 'Ha'
plot(spi.wavelengths[imin:imax], cvmat[lineinds[l]-imin,:], label=lines.keys()[i])
     