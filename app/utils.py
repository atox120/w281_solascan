import copy
import math
import threading
import numpy as np
from collections.abc import Iterable
from multiprocessing import Process, Pipe


class ImageWrapper:

    """
    Class for piping the images and their information through the various transforms. 
    Has attributes:
    .images: the images themselves, stored as numpy arrays.
    .category: the defect class associated with the image, as string. 
    .image_labels: the labels associated with the each image, stored as a list. 
    """
    
    def __init__(self, images, image_labels=None, category=None):

        self.images = images
        self.category = category
        self.image_labels = image_labels

    def __invert__(self):
        return self.images

    def __len__(self):
        return self.images.shape[0]

    def __sub__(self, other):
        """

        :param other: Remove the labels from this Wrapper if it exists in the other
        :return:
        """
        if not isinstance(other, ImageWrapper):
            raise TypeError('Other must be and ImageWrapper object')

        keep = []
        for cnt, x in enumerate(self.image_labels):
            # If this image is not in other then keep it
            if x not in other.image_labels:
                keep.append(cnt)

        # These are the images to keep
        images = self.images[keep]
        image_labels = [self.image_labels[x] for x in keep]

        return ImageWrapper(images.copy(), image_labels=image_labels, category=copy.deepcopy(self.category))

    def __add__(self, other):
        """

        :param other: Combine this and other across axis=0
        :return:
        """
        if not isinstance(other, ImageWrapper):
            raise TypeError('Other must be and ImageWrapper object')

        image_labels = self.image_labels + other.image_labels
        images = np.concatenate((self.images, other.images), axis=0)

        return ImageWrapper(images, image_labels=image_labels, category=self.category)

    def __and__(self, other):
        """

        :param other: Combine this and other across axis=-1
        :return:
        """
        if not isinstance(other, ImageWrapper):
            raise TypeError(f'Other must be an ImageWrapper object but is of {type(other)}')

        if np.any([x != y for x, y in zip(self.image_labels, other.image_labels)]):
            raise KeyError(' Cannot perform operation as image labels are nto matched')

        image_labels = self.image_labels
        images = np.concatenate((self.images, other.images), axis=-1)

        return ImageWrapper(images, image_labels=image_labels, category=self.category)

    def copy(self):

        return ImageWrapper(self.images.copy(), image_labels=copy.deepcopy(self.image_labels),
                            category=copy.deepcopy(self.category))


def input_check(indict, key, default, out_dict, exception=False):
    """
    Checks that the required inputs are parsed to the output dictionary.
    If exception = True, then this is a required input and an error is raised. 
    Else default parameter is assigned to that parameter.
    """

    try:
        out_dict[key] = indict[key]
        del indict[key]
    except KeyError:
        if exception:
            raise KeyError(f'{key} is a required input and was not provided')
        else:
            if default is not None:
                out_dict[key] = default


def line_split_string(instr, delimiter=' '):
    instr = str(instr)
    # instr = instr.replace('/n', ' ')

    split_strng = instr.split(delimiter)
    out_strng = ' '

    new_length = 0
    for strng in split_strng:
        if new_length > 40:
            out_strng += '\n'
            new_length = 0
        new_length += len(strng)

        out_strng += f' {strng}'
    return out_strng


def chunk(instr):

    instr = str(instr)
    num_chunks = math.ceil(len(instr)/40)
    split_strng = [instr[i:i+40] for i in range(num_chunks)]

    out_strng = ''
    for strng in split_strng:
        out_strng += strng + '\n'

    return out_strng[:-2]


def make_iter(var):
    if isinstance(var, Iterable) and not isinstance(var, np.ndarray) and not isinstance(var, str):
        return var
    else:
        return (var, )


class MyThread(threading.Thread):
    def __init__(self, func, args, threadid, name, counter):
        threading.Thread.__init__(self)
        self.threadID = threadid
        self.name = name
        self.counter = counter
        self.func = func
        self.args = args
        self.results = []

    def run(self):
        self.results = self.func(*self.args)


def parallel_wrapper(func, args, sender):
    """

    :param func:
    :param args:
    :param sender:
    :return:
    """

    # noinspection PyBroadException
    try:
        if isinstance(args, dict):
            retval = func(**args)
        else:
            args = make_iter(args)
            retval = func(*args)
        # print(retval)
        sender.send(retval)
    except Exception:
        # exc_info = sys.exc_info()
        # print(traceback)
        sender.send([])
    finally:
        # This is always
        sender.close()


def parallelize(funcs, args):
    """

    :param funcs:
    :param args:
    :return:
    """

    # Start the function
    processes = []
    pipe_list = []
    threads = []
    for cnt, (func, arg) in enumerate(zip(funcs, args)):
        # This pipe moves data from the process back to main function
        recv_end, send_end = Pipe(False)

        # Make the argument into a tuple for the parallel wrapper
        tuplearg = (func, arg, send_end)
        p = Process(target=parallel_wrapper, args=tuplearg)

        # Add the process and the pipe to a list
        processes.append(p)
        pipe_list.append(recv_end)
        p.start()

        # Start the thread for collecting the data
        thread = MyThread(recv_end.recv, (), cnt, "Thread-" + str(cnt), cnt)
        thread.start()
        threads.append(thread)

    # Join the threads
    for t in threads:
        t.join()

    # Collect all the results
    results = [t.results for t in threads]

    # Join and start the processes
    for p in processes:
        p.join()

    return results
