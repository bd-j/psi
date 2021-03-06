import sys
import numpy as np
import matplotlib.pyplot as pl
from spi.library_models import MILESInterpolator
from badstar import allbadstars

import time
ts = time.time()

# The PSI Model
mlib = '/Users/bjohnson/Projects/spi/data/miles/miles_prugniel.h5'
fgk_bounds = {'teff': (4200.0, 9000.0)}
badstar_ids = np.array(allbadstars.tolist())

psi = MILESInterpolator(training_data=mlib)
psi.features = (['logt'], ['feh'], ['logg'],
                ['logt', 'logt'], ['feh', 'feh'], ['logg', 'logg'],
                ['logt', 'feh'], ['logg', 'logt'], ['logg', 'feh'],
                ['logt', 'logt', 'logt'], ['logt', 'logt', 'logt', 'logt'], #logt high order
                ['logt', 'logt', 'logg'], ['logt', 'logg', 'logg'], # logg logt high order cross terms
                ['logt', 'logt', 'feh'], ['logt', 'feh', 'feh']  # feh logt high order cross terms
                )

psi.select(training_data=mlib, bounds=fgk_bounds, badvalues={'miles_id':badstar_ids})
ntrain = psi.n_train
predicted = np.zeros([ntrain, psi.n_wave])

# Retrain and predict after leaving one out
for i, j in enumerate(psi.training_indices.copy()):
    if (i % 10) == 0: print(i)
    # get full sample and the parameters of the star to leave out
    spec = psi.library_spectra[j,:]
    tlabels = psi.library_labels[j]
    labels = dict([(n, tlabels[n]) for n in psi.label_names])
    # leave one out and train
    psi.library_mask[j] = False
    psi.train()
    predicted[i, :] = psi.get_star_spectrum(**labels)
    psi.library_mask[j] = True
    
# reload the full training set
# psi.select(training_data=mlib, bounds=fgk_bounds, badvalues={'miles_id':badstar_ids})

# get fractional residuals
wmin, wmax = 3800, 7200
imin = np.argmin(np.abs(psi.wavelengths - wmin))
imax = np.argmin(np.abs(psi.wavelengths - wmax))
delta = predicted / psi.training_spectra - 1.0
var_spectrum = delta.var(axis=0)
var_total = delta[:, imin:imax].var(axis=1)
lines, indlines = {'Ha':6563., 'NaD': 5897.0, 'CaK': 3933.0, 'CaH': 3968, 'Mg5163':5163.1}, {}
for l, w in lines.items():
    indlines[l] = np.argmin(np.abs(psi.wavelengths - w))


# Plot the variance spectrum
sfig, sax = pl.subplots()
sax.plot(psi.wavelengths, np.sqrt(var_spectrum)*100, label='$\sigma(m/o-1)$')
sax.set_xlabel('$\lambda (\AA)$')
sax.set_ylabel('Fractional RMS (%)')
sax.set_ylim(0, 100)
sfig.show()
sfig.savefig('figures/residual_spectrum_{}.pdf'.format(ts))

# Plot a map of total variance as a function of label
l1, l2, l3 = 'logt', 'feh', 'logg'
lab = psi.training_labels 
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
[ax.invert_xaxis() for ax in mapaxes]
mapfig.show()                   
mapfig.savefig('figures/residual_map_{}.pdf'.format(ts))

# Plot a map of line residual as a function of label
showlines = lines.keys()
showlines = ['CaK', 'NaD']
for line in showlines:
    vlim = -50, 50
    if lines[line] < 4000:
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
    [ax.invert_xaxis() for ax in mapaxes]
    mapfig.show()
    mapfig.savefig('figures/residual_{}_map_{}.pdf'.format(line, ts))

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
cfig.savefig('figures/cumlative_rms_{}.pdf'.format(ts))

badfig, badaxes = pl.subplots(10, 1, sharex=True, figsize=(6, 12))
for i, bad in enumerate(oo[-10:][::-1]):
    ax = badaxes[i]
    labels = dict([(n, psi.training_labels[bad][n]) for n in psi.training_labels.dtype.names])
    title = "T={teff:4.0f}, logg={logg:3.2f}, feh={feh:3.1f}".format(**labels)
    ax.plot(psi.wavelengths, predicted[bad,:], label='predicted')
    ax.plot(psi.wavelengths, psi.training_spectra[bad,:], label='actual')
    ax.text(0.05, 0.9, "#{}, RMS={:4.1f}%".format(psi.training_labels[bad]['miles_id'], rms[bad]),
            transform=ax.transAxes, fontsize=10)
    ax.text(0.7, 0.05, title, transform=ax.transAxes, fontsize=10)
    if i == 0:
        ax.legend(loc=0, prop={'size':8})
    if i < 9:
        ax.set_xticklabels([])
badfig.savefig('figures/worst10_{}.pdf'.format(ts))

# B-V colors
from sedpy import observate
filt = observate.load_filters(['hipparcos_V', 'hipparcos_B'])
#filt = observate.load_filters(['bessell_V', 'bessell_B'])
pmags_actual = observate.getSED(psi.wavelengths, psi.training_spectra, filterlist=filt)
pmags_predicted = observate.getSED(psi.wavelengths, predicted, filterlist=filt)
# Compare colors to observations
mid, b, v = np.genfromtxt('../../data/tycho2_b_v.dat', unpack=True)
bv = b - v
mid = mid.astype(int)
inds = np.zeros(len(mid)) - 1
mlist = psi.training_labels['miles_id'].tolist()
for i, m in enumerate(mid):
    if m in mlist:
        inds[i] = mlist.index(m)
inds = inds.astype(int)
good = inds >= 0

fig, axes = pl.subplots(2, 1)
ax= axes[0]
ax.plot(psi.training_labels['logt'][inds[good]], np.diff(pmags_actual, axis=1)[inds[good], 0], 'o', label='Miles spectra')
ax.plot(psi.training_labels['logt'][inds[good]], np.diff(pmags_predicted, axis=1)[inds[good], 0], 'o', label='Predicted spectra')
ax.plot(psi.training_labels['logt'][inds[good]], bv[good], 'o', label='observed color')
ax.set_xlabel('logt')
ax.set_ylabel('Hipparcos B-V')
ax.legend(loc=0)
ax = axes[1]
ax.plot(psi.training_labels['logt'], np.diff(pmags_actual, axis=1) - np.diff(pmags_predicted, axis=1),
        'o', label='(miles-predicted)')
ax.set_xlabel('logt')
ax.set_ylabel('$\Delta(B-V)$')
ax.legend(loc=0)
fig.savefig('figures/B-V_{}.pdf'.format(ts))

pfig, pax = pl.subplots(2, 1)
pax[0].plot(psi.training_labels['logt'][inds[good]], np.diff(pmags_actual, axis=1)[inds[good], 0] - bv[good],
         'o', label='(miles-obs)')
pax[0].plot(psi.training_labels['logt'][inds[good]], np.diff(pmags_predicted, axis=1)[inds[good], 0] - bv[good],
         'o', label='(predicted-obs)')
pax[0].legend(loc=0)
pax[0].set_xlabel('logt')
pax[0].set_ylabel('$\Delta (B-V)$')
a = np.diff(pmags_actual, axis=1)[inds[good], 0] - bv[good]
b = np.diff(pmags_predicted, axis=1)[inds[good], 0] - bv[good]
pax[1].scatter(a, b, c=(np.sqrt(var_total)*100)[inds[good]], marker='o')
pax[1].set_xlabel('miles-obs')
pax[1].set_ylabel('predicted-obs')
pax[1].plot([-1,1], [-1,1], linestyle=':', color='k')
pax[1].set_xlim(-0.4, 0.4)
pax[1].set_ylim(-0.4, 0.4)

out = open('bv.dat', "w")
fmt = '{}  {:5.3f} {:5.3f} {:5.3f}\n'
out.write('{} {}\n'.format(*[f.name for f in filt]))
out.write('MID  bv_obs  bv_miles  bv_pred\n')
for i in range(len(good)):
    bv_pred = np.diff(pmags_predicted, axis=1)[inds[i], 0]
    bv_miles = np.diff(pmags_actual, axis=1)[inds[i], 0]
    bv_obs = bv[i]
    if good[i]:
        out.write(fmt.format(mid[i], bv_obs, bv_miles, bv_pred))
out.close()


sys.exit()
# compute covariance matrix
dd = delta[:, imin:imax]
dd[~np.isfinite(dd)] = 0.0
cvmat = np.cov(dd.T)

l = 'Ha'
plot(psi.wavelengths[imin:imax], cvmat[lineinds[l]-imin,:], label=lines.keys()[i])
     
