import numpy as np


__all__ = ["flatten_struct", "dict_struct", "make_struct", "within"]


def flatten_struct(struct, use_labels=None):
    """This is slow, should be replaced with a view-based method.
    """
    if use_labels is None:
        return np.array(struct.tolist())
    else:
        return np.array([struct[n] for n in use_labels])


def dict_struct(struct):
    """Convert from a structured array to a dictionary.  This shouldn't really
    be necessary.
    """
    return dict([(n, struct[n]) for n in struct.dtype.names])

    
def make_struct(**label_dict):
        """Convert from a dictionary of labels to a numpy structured array
        """
        dtype = np.dtype([(n, np.float) for n in label_dict.keys()])
        try:
            nl = len(label_dict[label_dict.keys()[0]])
        except:
            nl = 1
        labels = np.zeros(nl, dtype=dtype)
        for n in label_dict.keys():
            labels[n] = label_dict[n]
        return labels
 

def within(bound, value):
    return (value < bound[1]) & (value > bound[0])