import sys
import numpy as np
import matplotlib.pyplot as pl
from model import MILESInterpolator

#def loo(i)

# The PSI Model
mlib = '/Users/bjohnson/Projects/psi/data/miles/miles_prugniel.h5'
fgk_bounds = {'teff': (4000.0, 6000.0)}
psi = MILESInterpolator(training_data=mlib, normalize_labels=False)
psi.restrict_sample(bounds=fgk_bounds)

ntrain = psi.n_train
predicted = np.zeros([ntrain, psi.n_wave])

# Retrain and predict after leaving one out
for i in range(ntrain):
    psi.load_training_data(training_data=mlib)
    psi.restrict_sample(bounds=fgk_bounds)
    psi.features = (['logt'], ['feh'], ['logg'],
                    ['logt', 'logt'], ['feh', 'feh'], ['logg', 'logg'],
                    ['logt', 'feh'], ['logt', 'logt', 'logt'])
                    #['logt', 'logt', 'logt'], ['logt', 'logt', 'logt', 'logt'],
                    #['logt', 'feh'], ['logt', 'logg'],
                    #['logt', 'logt', 'logg'],

    spec= psi.training_spectra[i,:]
    tlabels = psi.training_labels[i]
    labels = dict([(n, tlabels[n]) for n in psi.label_names])
    psi.leave_out(i)
    psi.train()
    print(psi.coeffs)
    predicted[i, :] = psi.get_star_spectrum(**labels)

# reload the full training set
psi.load_training_data(training_data=mlib)
psi.restrict_sample(bounds=fgk_bounds)

# get fractional residuals
delta = predicted/psi.training_spectra - 1.0
var_spectrum = delta.var(axis=0)
var_total = delta[:, 10:-10].var(axis=1)

# Plot the variance spectrum
sfig, sax = pl.subplots()
sax.plot(psi.wavelengths, np.sqrt(var_spectrum)*100, label='$\sigma(m/o-1)$')
sax.set_xlabel('$\lambda (\AA)$')
sax.set_ylabel('Fractional RMS (%)')
sax.set_ylim(0, 100)
sfig.show()

# Plot a map of total variance as a function of label

l1name, l2name = 'logt', 'feh'
l1 = psi.training_labels[l1name]
l2 = psi.training_labels[l2name]
mapfig, mapax = pl.subplots()
cm = pl.cm.get_cmap('gnuplot2_r')
sc = mapax.scatter(l1, l2, marker='o', c=np.sqrt(var_total)*100)
mapax.set_xlabel(l1name)
mapax.set_ylabel(l2name)
pl.colorbar(sc)
mapfig.show()                   