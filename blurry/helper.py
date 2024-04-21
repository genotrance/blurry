"Common helper functions"

# Standard imports
import concurrent.futures
import logging
import os
import sys
import threading
import time

MAXWORKERS = os.cpu_count()

#logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger("blurry")

# Remove default console handler
for handler in logger.handlers:
    if isinstance(handler, logging.StreamHandler):
        logger.removeHandler(handler)

# Log timing separately if requested
is_timeit = "--timeit" in sys.argv
if is_timeit:
    # Critical level is for timing
    class TimeitFilter(logging.Filter):
        "Custom filter that only allows critical messages"
        def filter(self, record):
            return record.levelno == logging.CRITICAL

    logger.setLevel(logging.CRITICAL)
    timeit_handler = logging.FileHandler("time.csv", "w")
    timeit_handler.setLevel(logging.CRITICAL)
    timeit_handler.setFormatter(logging.Formatter("%(message)s"))
    timeit_handler.addFilter(TimeitFilter())
    logger.addHandler(timeit_handler)

# Function call trace logging
is_debug = "--debug" in sys.argv
if is_debug:
    # Debug level is for tracing
    logger.setLevel(logging.DEBUG)
    debug_handler = logging.FileHandler("debug.log", "w")
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(logging.Formatter("%(asctime)s: %(message)s"))
    logger.addHandler(debug_handler)

def timeit(func):
    "Decorator to measure the time taken by a function"
    if is_timeit:
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            logger.critical("%s,%0.6f", func.__name__, end - start)
            return result
        return wrapper
    return func

def log(message, func="debug"):
    "Log a debug message"
    if is_debug:
        tname = threading.current_thread().name
        logger.debug("%s:%s%s(%s)", tname, debug.depth[tname] * "  ", func, message)

def debug(func):
    "Decorator to log the function call tree"
    if is_debug:
        def wrapper(*args, **kwargs):
            tname = threading.current_thread().name
            if debug.depth.get(tname, None) is None:
                debug.depth[tname] = 1
            params = ""
            for arg in args:
                params += str(arg) + ", "
            for key, val in kwargs.items():
                params += str(key) + "=" + str(val) + ", "
            log(params[:-2], func=func.__name__)
            debug.depth[tname] += 1
            ret = func(*args, **kwargs)
            debug.depth[tname] -= 1
            log("DONE", func=func.__name__)
            return ret
        return wrapper
    return func
# Function depth
debug.depth = {}

def debugclass(cls):
    "Decorator to decorate every class method with debug"
    if is_debug:
        for name, method in vars(cls).items():
            if name[0] != "_" and callable(method):
                setattr(cls, name, debug(method))
        cls.__str__ = lambda x: cls.__name__
    return cls

@debug
def parallelize(funcparam, post = None, results = None, final = None, executor = None):
    """
    Parallel execution in threads - two cases
    - Run function on multiple params in parallel
        for param in params:
            results[param] = post(func(param))
    - Run multiple functions on one param in parallel
        for func in funcs:
            results[func] = post(func(param))
    Conclude by running final(var)

    funcparam = (func, params[]) | (funcs[], param)
    """
    func = funcs = param = params = None
    if len(funcparam) != 2:
        raise ValueError("funcparam must be length 2")
    if isinstance(funcparam[0], list):
        funcs = funcparam[0]
    else:
        func = funcparam[0]
    if isinstance(funcparam[1], list):
        params = funcparam[1]
    else:
        param = funcparam[1]

    if executor is None:
        numworkers = len(funcs) if funcs is not None else min(len(params), MAXWORKERS)
        local_executor = concurrent.futures.ThreadPoolExecutor(max_workers = numworkers)
    else:
        local_executor = executor

    if func is not None and params:
        future_to_var = {local_executor.submit(func, param): param for param in params}
    elif param is not None and funcs:
        future_to_var = {local_executor.submit(func, param): func for func in funcs}

    for future in concurrent.futures.as_completed(future_to_var):
        # Get var for this future
        var = future_to_var[future]

        # Get result for this var
        val = post(future.result()) if post is not None else future.result()

        # Save results if specified
        if results is not None:
            results[var] = val

        # Call final if specified
        if final is not None:
            final(var)

    if executor is None:
        # Clean up the executor
        local_executor.shutdown()