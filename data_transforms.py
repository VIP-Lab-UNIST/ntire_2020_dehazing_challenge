import numbers
import random

import numpy as np
from PIL import Image, ImageOps
import torch

"""
Modified data transforms for [image, gt] triplet
"""

class Resize(object):
        def __init__(self, size):
            self.size = size
        def __call__(self, image, label):
            return image.resize((self.size, self.size), Image.BILINEAR), \
                    label.resize((self.size, self.size), Image.BILINEAR)


class RandomIdentityMapping(object):
        def __init__(self, p=0.1):
            self.p = p
        def __call__(self, image, label):
            if random.random() < self.p:
                return label, label
            else:
                return image, label


class RandomCrop(object):
    def __init__(self, size):
        if isinstance(size, numbers.Number):
            self.size = (int(size), int(size))
        else:
            self.size = size

    def __call__(self, image, label, *args):
        assert label is None or (image.size == label.size), \
            "image and label doesn't have the same size {} / {}".format(
                image.size, label.size)

        w, h = image.size
        tw, th = self.size
        top = bottom = left = right = 0
        if w < tw:
            left = (tw - w) // 2
            right = tw - w - left
        if h < th:
            top = (th - h) // 2
            bottom = th - h - top
        if left > 0 or right > 0 or top > 0 or bottom > 0:
            label = pad_image(
                'reflection', label, top, bottom, left, right)
            image = pad_image(
                'reflection', image, top, bottom, left, right)
        w, h = image.size
        if w == tw and h == th:
            return (image, label, *args)

        x1 = random.randint(0, w - tw)
        y1 = random.randint(0, h - th)
        results = [image.crop((x1, y1, x1 + tw, y1 + th))]
        if label is not None:
            results.append(label.crop((x1, y1, x1 + tw, y1 + th)))
        results.extend(args)
        return results


class RandomScale(object):
    def __init__(self, scale):
        if isinstance(scale, numbers.Number):
            scale = [1, scale]
        self.scale = scale

    def __call__(self, image, label):
        ratio = random.uniform(self.scale[0], self.scale[1])
        w, h = image.size
        tw = int(ratio * w)
        th = int(ratio * h)
        if ratio == 1:
            return image, label
        elif ratio < 1:
            interpolation = Image.ANTIALIAS
        else:
            interpolation = Image.CUBIC
        return image.resize((tw, th), interpolation), \
            label.resize((tw, th), interpolation)


class RandomRotate(object):
    """Crops the given PIL.Image at a random location to have a region of
    the given size. size can be a tuple (target_height, target_width)
    or an integer, in which case the target will be of a square shape (size, size)
    """

    def __init__(self, angle):
        self.angle = angle

    def __call__(self, image, label=None, *args):
        assert label is None or (image.size == label.size)

        w, h = image.size
        p = max((h, w))
        angle = random.randint(0, self.angle * 2) - self.angle

        if label is not None:
            label = pad_image('reflection', label, h, h, w, w)
            label = label.rotate(angle, resample=Image.BILINEAR)
            label = label.crop((w, h, w + w, h + h))

        image = pad_image('reflection', image, h, h, w, w)
        image = image.rotate(angle, resample=Image.BILINEAR)
        image = image.crop((w, h, w + w, h + h))
        return image, label


class RandomHorizontalFlip(object):
    """Randomly horizontally flips the given PIL.Image with a probability of 0.5
    """

    def __call__(self, image, label):
        if random.random() < 0.5:
            results = [image.transpose(Image.FLIP_LEFT_RIGHT),
                       label.transpose(Image.FLIP_LEFT_RIGHT)]
        else:
            results = [image, label]
        return results

class RandomVerticalFlip(object):
    """Randomly horizontally flips the given PIL.Image with a probability of 0.5
    """

    def __call__(self, image, label):
        if random.random() < 0.5:
            results = [image.transpose(Image.FLIP_TOP_BOTTOM),
                       label.transpose(Image.FLIP_TOP_BOTTOM)]
        else:
            results = [image, label]
        return results

class AddNoise(object):
    def __init__(self, mean=0, sigma=0.01):
        self.mean = mean
        self.sigma = sigma

    def __call__(self, image, label):     
        image = np.asarray(image)/255.0
        new_shape = list(image.shape)
        new_image = np.empty(new_shape, dtype=image.dtype)

        row,col,ch= image.shape
        mean = self.mean
        sigma = self.sigma
        gauss = np.random.normal(mean,sigma,(row,col,ch))
        # gauss = gauss.reshape(row,col,ch)
        new_image = (image + gauss) * 255.0
        return Image.fromarray(np.asarray(new_image.astype(np.uint8))), label#Image.fromarray(np.asarray(new_gt))


def pad_reflection(image, top, bottom, left, right):
    if top == 0 and bottom == 0 and left == 0 and right == 0:
        return image
    h, w = image.shape[:2]
    next_top = next_bottom = next_left = next_right = 0
    if top > h - 1:
        next_top = top - h + 1
        top = h - 1
    if bottom > h - 1:
        next_bottom = bottom - h + 1
        bottom = h - 1
    if left > w - 1:
        next_left = left - w + 1
        left = w - 1
    if right > w - 1:
        next_right = right - w + 1
        right = w - 1
    new_shape = list(image.shape)
    new_shape[0] += top + bottom
    new_shape[1] += left + right
    new_image = np.empty(new_shape, dtype=image.dtype)
    new_image[top:top+h, left:left+w] = image
    new_image[:top, left:left+w] = image[top:0:-1, :]
    new_image[top+h:, left:left+w] = image[-1:-bottom-1:-1, :]
    new_image[:, :left] = new_image[:, left*2:left:-1]
    new_image[:, left+w:] = new_image[:, -right-1:-right*2-1:-1]
    return pad_reflection(new_image, next_top, next_bottom,
                          next_left, next_right)


def pad_constant(image, top, bottom, left, right, value):
    if top == 0 and bottom == 0 and left == 0 and right == 0:
        return image
    h, w = image.shape[:2]
    new_shape = list(image.shape)
    new_shape[0] += top + bottom
    new_shape[1] += left + right
    new_image = np.empty(new_shape, dtype=image.dtype)
    new_image.fill(value)
    new_image[top:top+h, left:left+w] = image
    return new_image


def pad_image(mode, image, top, bottom, left, right, value=0):
    if mode == 'reflection':
        return Image.fromarray(
            pad_reflection(np.asarray(image), top, bottom, left, right))
    elif mode == 'constant':
        return Image.fromarray(
            pad_constant(np.asarray(image), top, bottom, left, right, value))
    else:
        raise ValueError('Unknown mode {}'.format(mode))


class ToTensor(object):
    """
    Converts a PIL.Image or numpy.ndarray (H x W x C) in the range
    [0, 255] to a torch.FloatTensor of shape (C x H x W) in the range [0.0, 1.0].
    """

    def __call__(self, pic, label=None):
        if isinstance(pic, np.ndarray):
            # handle numpy array
            img = torch.from_numpy(pic)
        else:
            # handle PIL Image
            img = torch.ByteTensor(torch.ByteStorage.from_buffer(pic.tobytes()))
            # PIL image mode: 1, L, P, I, F, RGB, YCbCr, RGBA, CMYK
            if pic.mode == 'YCbCr':
                nchannel = 3
            else:
                nchannel = len(pic.mode)
            img = img.view(pic.size[1], pic.size[0], nchannel)
            # put it from HWC to CHW format
            # yikes, this transpose takes 80% of the loading time/CPU
            img = img.transpose(0, 1).transpose(0, 2).contiguous()
        img = img.float().div(255)
        
        if label is None:
            return img,
        
        else:
            gt = torch.ByteTensor(torch.ByteStorage.from_buffer(label.tobytes()))
            if label.mode == 'YCbCr':
                nchannel=3
            else:
                nchannel = len(label.mode)

            gt = gt.view(label.size[1], label.size[0], nchannel)
            gt = gt.transpose(0, 1).transpose(0, 2).contiguous()
            gt = gt.float().div(255)
            #return img, torch.LongTensor(np.array(label, dtype=np.int))
            return img, gt

class Compose(object):
    """
    Composes several transforms together.
    """

    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, *args):
        for t in self.transforms:
            args = t(*args)
        return args
