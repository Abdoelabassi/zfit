import tensorflow as tf

from ..core.minimizer import MinimizerInterface
from .base_tf import WrapOptimizer


# class AdadeltaMinimizer(AdapterTFOptimizer, tf.train.AdadeltaOptimizer, MinimizerInterface):
#     def __init__(self):
#         raise NotImplementedError("Currently a placeholder, has to be implemented (with WrapOptimizer")
#
#
# class AdagradMinimizer(AdapterTFOptimizer, tf.train.AdagradOptimizer, MinimizerInterface):
#     def __init__(self):
#         raise NotImplementedError("Currently a placeholder, has to be implemented (with WrapOptimizer")
#
#
# class GradientDescentMinimizer(AdapterTFOptimizer, tf.train.GradientDescentOptimizer, MinimizerInterface):
#     def __init__(self):
#         raise NotImplementedError("Currently a placeholder, has to be implemented (with WrapOptimizer")
#
#
# class RMSPropMinimizer(AdapterTFOptimizer, tf.train.RMSPropOptimizer, MinimizerInterface):
#     def __init__(self):
#         raise NotImplementedError("Currently a placeholder, has to be implemented (with WrapOptimizer")


class AdamMinimizer(WrapOptimizer):
    _DEFAULT_name = 'Adam'

    def __init__(self, loss, params=None, tolerance=None,
                 learning_rate=0.2,
                 beta1=0.9,
                 beta2=0.999,
                 epsilon=1e-08,
                 use_locking=False,
                 name='Adam', **kwargs):
        optimizer = tf.train.AdamOptimizer(learning_rate=learning_rate,
                                           beta1=beta1, beta2=beta2,
                                           epsilon=epsilon, use_locking=use_locking,
                                           name=name)
        super().__init__(optimizer=optimizer, loss=loss, params=params,
                         tolerance=tolerance, **kwargs)
