#  Copyright (c) 2021 zfit

from typing import Callable, Iterable, Optional

import numdifftools
import tensorflow as tf

from ..util.container import convert_to_container
from ..util.deprecation import deprecated
from . import function
from .tools import _auto_upcast
from .zextension import convert_to_tensor


def poly_complex(*args, real_x=False):
    """Complex polynomial with the last arg being x.

    Args:
        *args: Coefficients of the polynomial
        real_x: If True, x is assumed to be real.

    Returns:
    """
    from .. import z

    args = list(args)
    x = args.pop()
    if real_x is not None:
        pow_func = tf.pow
    else:
        pow_func = z.nth_pow
    return tf.add_n([coef * z.to_complex(pow_func(x, p)) for p, coef in enumerate(args)])


def numerical_gradient(func: Callable, params: Iterable["zfit.Parameter"]) -> tf.Tensor:
    """Calculate numerically the gradient of func() with respect to `params`.

    Args:
        func: Function without arguments that depends on `params`
        params: Parameters that `func` implicitly depends on and with respect to which the
            derivatives will be taken.

    Returns:
        Gradients
    """
    params = convert_to_container(params)

    def wrapped_func(param_values):
        for param, value in zip(params, param_values):
            param.assign(value)
        value = func()
        if hasattr(value, 'numpy'):
            value = value.numpy()
        return value

    param_vals = tf.stack(params)
    original_vals = [param.read_value() for param in params]
    grad_func = numdifftools.Gradient(wrapped_func, order=2, base_step=1e-4)
    if tf.executing_eagerly():
        gradient = convert_to_tensor(grad_func(param_vals))
    else:
        gradient = tf.numpy_function(grad_func, inp=[param_vals],
                                     Tout=tf.float64)
    if gradient.shape == ():
        gradient = tf.reshape(gradient, shape=(1,))
    gradient.set_shape(param_vals.shape)
    for param, val in zip(params, original_vals):
        param.set_value(val)
    return gradient


def numerical_value_gradient(func: Callable, params: Iterable["zfit.Parameter"]) -> [tf.Tensor, tf.Tensor]:
    """Calculate numerically the gradients of `func()` with respect to `params`, also returns the value of `func()`.

    Args:
        func: Function without arguments that depends on `params`
        params: Parameters that `func` implicitly depends on and with respect to which the
            derivatives will be taken.

    Returns:
        Value, gradient
    """
    return func(), numerical_gradient(func, params)


numerical_value_gradients = deprecated(None, "Use `numerical_value_gradient` instead.")(numerical_value_gradient)


def numerical_hessian(func: Optional[Callable],
                      params: Iterable["zfit.Parameter"],
                      hessian=None) -> tf.Tensor:
    """Calculate numerically the hessian matrix of func with respect to `params`.

    Args:
        func: Function without arguments that depends on `params`
        params: Parameters that `func` implicitly depends on and with respect to which the
            derivatives will be taken.

    Returns:
        Hessian matrix
    """

    params = convert_to_container(params)

    def wrapped_func(param_values):
        for param, value in zip(params, param_values):
            param.assign(value)
        value = func()
        if hasattr(value, 'numpy'):
            value = value.numpy()
        return value

    param_vals = tf.stack(params)
    original_vals = [param.value() for param in params]

    if hessian == 'diag':
        hesse_func = numdifftools.Hessdiag(wrapped_func,
                                           order=4,
                                           # TODO: maybe add step to remove numerical problems?
                                           base_step=1e-4
                                           )
    else:
        hesse_func = numdifftools.Hessian(wrapped_func,
                                          order=4,
                                          base_step=1e-4,
                                          )
    if tf.executing_eagerly():
        computed_hessian = convert_to_tensor(hesse_func(param_vals))
    else:
        computed_hessian = tf.numpy_function(hesse_func, inp=[param_vals],
                                             Tout=tf.float64)
    n_params = param_vals.shape[0]
    if hessian == 'diag':
        computed_hessian.set_shape((n_params,))
    else:
        computed_hessian.set_shape((n_params, n_params))

    for param, val in zip(params, original_vals):
        param.set_value(val)
    return computed_hessian


def numerical_value_gradient_hessian(func: Optional[Callable],
                                     params: Iterable["zfit.Parameter"],
                                     gradient: Optional[Callable] = None,
                                     hessian: Optional[str] = None) -> [tf.Tensor, tf.Tensor, tf.Tensor]:
    """Calculate numerically the gradients and hessian matrix of `func()` wrt `params`; also return `func()`.

    Args:
        func: Function without arguments that depends on `params`
        params: Parameters that `func` implicitly depends on and with respect to which the
            derivatives will be taken.

    Returns:
        Value, gradient and hessian matrix
    """
    if params is None:
        raise ValueError("params cannot be None")
    if func is None and gradient is None:
        raise ValueError("Either func or grad has to be given")
    value, gradients = numerical_value_gradient(func, params)
    hessian = numerical_hessian(func, params, hessian=hessian)

    return value, gradients, hessian


numerical_value_gradients_hessian = deprecated(None,
                                               "Use `numerical_value_gradient_hessian` instead.")(
    numerical_value_gradient_hessian)


def autodiff_gradient(func: Callable, params: Iterable["zfit.Parameter"]) -> tf.Tensor:
    """Calculate using autodiff the gradients of `func()` wrt `params`.

    Automatic differentiation (autodiff) is a way of retreiving the derivative of x wrt y. It works by consecutively
    applying the chain rule. All that is needed is that every operation knows its own derivative.
    TensorFlow implements this and anything using `tf.*` operations only can use this technique.

        Args:
            func: Function without arguments that depends on `params`
            params: Parameters that `func` implicitly depends on and with respect to which the
                derivatives will be taken.

        Returns:
            Gradient
    """
    return autodiff_value_gradients(func, params)[1]


def autodiff_value_gradient(func: Callable, params: Iterable["zfit.Parameter"]) -> [tf.Tensor, tf.Tensor]:
    """Calculate using autodiff the gradients of `func()` wrt `params`; also return `func()`.

    Automatic differentiation (autodiff) is a way of retreiving the derivative of x wrt y. It works by consecutively
    applying the chain rule. All that is needed is that every operation knows its own derivative.
    TensorFlow implements this and anything using `tf.*` operations only can use this technique.

        Args:
            func: Function without arguments that depends on `params`
            params: Parameters that `func` implicitly depends on and with respect to which the
                derivatives will be taken.

        Returns:
            Value and gradient
    """
    with tf.GradientTape(persistent=False,  # needs to be persistent for a call from hessian.
                         watch_accessed_variables=False) as tape:
        tape.watch(params)
        value = func()
    gradients = tape.gradient(value, sources=params)
    return value, gradients


autodiff_value_gradients = deprecated(None, "Use `autodiff_value_gradient` instead.")(autodiff_value_gradient)


def autodiff_hessian(func: Callable, params: Iterable["zfit.Parameter"], hessian=None) -> tf.Tensor:
    """Calculate using autodiff the hessian matrix of `func()` wrt `params`.

    Automatic differentiation (autodiff) is a way of retrieving the derivative of x wrt y. It works by consecutively
    applying the chain rule. All that is needed is that every operation knows its own derivative.
    TensorFlow implements this and anything using `tf.*` operations only can use this technique.

        Args:
            func: Function without arguments that depends on `params`
            params: Parameters that `func` implicitly depends on and with respect to which the
                derivatives will be taken.

        Returns:
            Hessian matrix
    """

    return automatic_value_gradients_hessian(func, params, hessian=hessian)[2]


def automatic_value_gradient_hessian(func: Callable = None, params: Iterable["zfit.Parameter"] = None,
                                     value_grad_func=None,
                                     hessian=None) -> [tf.Tensor, tf.Tensor, tf.Tensor]:
    """Calculate using autodiff the gradients and hessian matrix of `func()` wrt `params`; also return `func()`.

    Automatic differentiation (autodiff) is a way of retreiving the derivative of x wrt y. It works by consecutively
    applying the chain rule. All that is needed is that every operation knows its own derivative.
    TensorFlow implements this and anything using `tf.*` operations only can use this technique.

        Args:
            func: Function without arguments that depends on `params`
            params: Parameters that `func` implicitly depends on and with respect to which the
                derivatives will be taken.

        Returns:
            Value, gradient and hessian matrix
    """
    if params is None:
        raise ValueError("Parameters have to be specified, are currently None.")
    if func is None and value_grad_func is None:
        ValueError("Either `func` or `value_grad_func` has to be specified.")

    from .. import z
    persistant = hessian == 'diag' or tf.executing_eagerly()  # currently needed, TODO: can we better parallelize that?
    with tf.GradientTape(persistent=persistant, watch_accessed_variables=False) as tape:
        tape.watch(params)
        if callable(value_grad_func):
            loss, gradients = value_grad_func(params)
        else:
            loss, gradients = autodiff_value_gradients(func=func, params=params)
        if hessian != 'diag':
            gradients_tf = tf.stack(gradients)
    if hessian == 'diag':
        computed_hessian = tf.stack(
            # tape.gradient(gradients_tf, sources=params)
            # computed_hessian = tf.stack(tf.vectorized_map(lambda grad: tape.gradient(grad, sources=params), gradients))
            [tape.gradient(grad, sources=param) for param, grad in zip(params, gradients)]
        )
    else:
        computed_hessian = z.convert_to_tensor(tape.jacobian(gradients_tf, sources=params,
                                                             experimental_use_pfor=False  # causes TF bug? Slow..
                                                             ))
    del tape
    return loss, gradients, computed_hessian


automatic_value_gradients_hessian = deprecated(None,
                                               "Use `automatic_value_gradient_hessian` instead.")(
    automatic_value_gradient_hessian)


@function(wraps="tensor")
def reduce_geometric_mean(input_tensor, axis=None, keepdims=False):
    log_mean = tf.reduce_mean(tf.math.log(input_tensor), axis=axis, keepdims=keepdims)
    return tf.math.exp(log_mean)


def log(x, name=None):
    x = _auto_upcast(x)
    return _auto_upcast(tf.math.log(x=x, name=name))
