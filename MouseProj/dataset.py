import torch
import numpy as np
from torch.utils.data import Dataset
from scipy.ndimage import affine_transform
from niiutility import *
from numba import jit
import time

def loadbvcenter(img):
	'''
	get the bv center
	'''
	bvmask = loadbvmask(img)
	
	bvcenter = np.zeros(3)
	
	bvcenter[0] = np.mean(bvmask[0:2])
	bvcenter[1] = np.mean(bvmask[2:4])
	bvcenter[2] = np.mean(bvmask[4:6])

	return bvcenter

def loadbvmask(img):
	'''
	Truely stupid and brutal force way to Find mask of BV
	'''
	img = (img > 0.66).astype(np.float32)
	# BVmask.shape = 1, X, Y, Z

	_, X, Y, Z = img.shape
	x1, y1, z1 = 0, 0, 0
	x2, y2, z2 = X-1, Y-1, Z-1

	while x1 < X:
		if (np.sum(img[:,x1,:,:]) > 0): # ~take a slice and check!
			break
		else:
			x1 += 1

	while y1 < Y:
		if (np.sum(img[:,:,y1,:]) > 0):
			break
		else:
			y1 += 1

	while z1 < Z:
		if (np.sum(img[:,:,:,z1]) > 0):
			break
		else:
			z1 += 1

	while x2 > 0:
		if (np.sum(img[:,x2,:,:]) > 0): 
			break
		else:
			x2 -= 1

	while y2 > 0:
		if (np.sum(img[:,:,y2,:]) > 0): 
			break
		else:
			y2 -= 1

	while z2 > 0:
		if (np.sum(img[:,:,:,z2]) > 0): 
			break
		else:
			z2 -= 1

	return np.array([x1, x2, y1, y2, z1, z2])

def toTensorBV (sample):

	# use if you use 370 BV image
	
	image, label = sample['image'], sample['label']
	imageTensor = torch.from_numpy(((image-0.25)*256).copy()) # normalize the image by mean reduction, the mean=0.25 here 
	labelTensor = torch.from_numpy(label.copy()) # no need to conduct anything special to it, I think
	labelTensor = torch.round(labelTensor)

	return {'image': imageTensor, 'label': labelTensor}

def toTensor (sample):
	'''
	Notes:
		Mean Reduction on image, OneHot on label, Convert one sample to single tensor
	Args:
		sample: dict of ndarray, image in [0, 255], (C=1, X, Y, Z), 
			label in {0, 0.5, 1}, (C=1, X, Y, Z)
		device: torch.device('cuda')/torch.device('cpu')
	Ret:
		Dict of:
			imageTensor range [0, 255] with mean 0, (C=1, X, Y, X)
			labelTensor in [0, 1], (C=3, X, Y, X)
	'''
	image, label = sample['image'], sample['label']
	imageTensor = torch.from_numpy(image-90)

	labelOH = np.zeros((3, image.shape[1], image.shape[2], image.shape[3]) \
		, dtype=np.float32)

	labelOH[0:1] = (label < 0.33).astype(np.float32)
	labelOH[1:2] = (label > 0.33).astype(np.float32)
	labelOH[2:3] = (label > 0.66).astype(np.float32)

	labelOH[1:2] -= labelOH[2:3]

	labelTensor = torch.from_numpy(labelOH)

	labelTensor = torch.round(labelTensor)

	return {'image': imageTensor, 'label': labelTensor}

def AffineFunOld(img, xr, yr, zr, xm, ym, zm, order):
	'''
	Notes:
		Rotate and move
		MoveToCenter->RotateX->RotateY->RotateZ->MoveBack->MoveRandom
	Args:
		img: image of shape (C=1, X, Y, Z)
		xr, yr, zr: Rotate in degree
		xm, ym, zm: move as int
		order: 3 for image, 0 for label
	Ret:
		img: Transformed image of shape (C=1, X, Y, Z)
	'''
	sinx = np.sin(np.deg2rad(xr))
	cosx = np.cos(np.deg2rad(xr))

	siny = np.sin(np.deg2rad(yr))
	cosy = np.cos(np.deg2rad(yr))

	sinz = np.sin(np.deg2rad(zr))
	cosz = np.cos(np.deg2rad(zr))

	xc = img[0].shape[0]//2
	yc = img[0].shape[1]//2
	zc = img[0].shape[2]//2

	Mc = np.array([[1, 0, 0, xc],[0, 1, 0, yc],[0, 0, 1, zc],[0, 0, 0, 1]])
	Rx = np.array([[cosx, sinx, 0, 1],[-sinx, cosx, 0, 1],[0, 0, 1, 1], [0, 0, 0, 1]])
	Ry = np.array([[cosy, 0, siny, 1],[0, 1, 0, 1],[-siny, 0, cosy, 1], [0, 0, 0, 1]])
	Rz = np.array([[1, 0, 0, 1],[0, cosz, sinz, 1],[0, -sinz, cosz, 1], [0, 0, 0, 1]])
	Mb = np.array([[1, 0, 0, -xc],[0, 1, 0, -yc],[0, 0, 1, -zc],[0, 0, 0, 1]])
	MM = np.array([[1, 0, 0, xm],[0, 1, 0, ym],[0, 0, 1, zm],[0 ,0, 0, 1]])

	Matrix = np.linalg.multi_dot([Mc, Rx, Ry, Rz, Mb, MM])
	img[0] = affine_transform(img[0], Matrix, output_shape=img[0].shape, order=order)

	return img

class RandomAffineOld(object):
	'''
	Random rotation and move
	'''
	def __init__(self, fluR, fluM):

		self.fluR = fluR
		self.fluM = fluM

	def __call__(self, sample):

		xr, yr, zr = np.random.uniform(-self.fluR, self.fluR, size=3)
		xm, ym, zm = np.random.uniform(-self.fluM, self.fluM, size=3)

		image, label = sample['image'], sample['label']
		return {'image': AffineFunOld(image, xr, yr, zr, xm, ym, zm, 1), \
				'label': AffineFunOld(label, xr, yr, zr, xm, ym, zm, 0)}

def AffineFun(img, xr, yr, zr, xm, ym, zm, s, DS, order):
	'''
	Notes:
		Rotate and move
		MoveToCenter->RotateX->RotateY->RotateZ->MoveBack->MoveRandom
	Args:
		img: image of shape (C=1, X, Y, Z)
		xr, yr, zr: Rotate in degree
		xm, ym, zm: move as int
		order: 3 for image, 0 for label
	Ret:
		img: Transformed image of shape (C=1, X, Y, Z)
	'''
	sinx = np.sin(np.deg2rad(xr))
	cosx = np.cos(np.deg2rad(xr))

	siny = np.sin(np.deg2rad(yr))
	cosy = np.cos(np.deg2rad(yr))

	sinz = np.sin(np.deg2rad(zr))
	cosz = np.cos(np.deg2rad(zr))

	xc = img[0].shape[0]//2
	yc = img[0].shape[1]//2
	zc = img[0].shape[2]//2
    
	xout = np.round(img[0].shape[0]/DS).astype(np.int16)
	yout = np.round(img[0].shape[1]/DS).astype(np.int16)
	zout = np.round(img[0].shape[2]/DS).astype(np.int16)
    
	imgout = np.zeros((xout, yout, zout))

	Mc = np.array([ [1, 0, 0, xc],
					[0, 1, 0, yc],
					[0, 0, 1, zc],
					[0, 0, 0, 1]])
	
	Ms = np.array([ [1/s, 0, 0, 0],
					[0, 1/s, 0, 0],
					[0, 0, 1/s, 0], 
					[0, 0, 0, 1]])
    
	MD = np.array([ [DS, 0, 0, 0],
					[0, DS, 0, 0],
					[0, 0, DS, 0], 
					[0, 0, 0, 1]])
    
	Rx = np.array([ [cosx, sinx, 0, 0],
					[-sinx, cosx, 0, 0],
					[0, 0, 1, 0], 
					[0, 0, 0, 1]])

	Ry = np.array([ [cosy, 0, siny, 0],
					[0, 1, 0, 0],
					[-siny, 0, cosy, 0], 
					[0, 0, 0, 1]])
	
	Rz = np.array([ [1, 0, 0, 0],
					[0, cosz, sinz, 0],
					[0, -sinz, cosz, 0], 
					[0, 0, 0, 1]])
	
	Mb = np.array([ [1, 0, 0, -xc],
					[0, 1, 0, -yc],
					[0, 0, 1, -zc],
					[0, 0, 0, 1]])

	MM = np.array([ [1, 0, 0, xm],
					[0, 1, 0, ym],
					[0, 0, 1, zm],
					[0 ,0, 0, 1]])
#	Matrix = np.linalg.multi_dot([Mc, Rx, Ry, Rz, Mb, MM])
	Matrix = np.linalg.multi_dot([Mc, Ms, Rx, Ry, Rz, Mb, MM, MD])
	imgout = affine_transform(img[0], Matrix, output_shape=(xout, yout, zout), order=order)
	return imgout[None,:,:,:]

def filpFun(img, x, y, z):
	'''
	Notes:
		filp image
	Args:
		img: image of shape (C=1, X, Y, Z)
		x, y, z: filp x ? filp y ? flip z ?
	Ret:
		img: Transformed image of shape (C=1, X, Y, Z)
	'''
	if x==True:
		img = np.flip(img, axis=1)

	if y==True:
		img = np.flip(img, axis=2)

	if z==True:
		img = np.flip(img, axis=3)

	return img

def upSampleFun(img, level, order):
	'''
	Args:
		img: shape [1, X, Y, Z]
		level: scaling factor of downsampling
		order: 3 for image, 0 for label
	Ret:
		imgout: down sampled image of shape [1, X//level, Y//level, Z//level]
	'''
	if level == 1:
		return img
	else:
		_, x, y, z = img.shape

		imgout = np.zeros([1, x*level, y*level, z*level], dtype=np.float32)
		Matrix = np.array([[1/level, 0, 0, 0],[0, 1/level, 0, 0],[0, 0, 1/level, 0],[0, 0, 0, 1]])
		imgout[0] = affine_transform(img[0], Matrix, output_shape=imgout[0].shape, order=order)
		return imgout

def downSampleFun(img, level, order):
	'''
	Args:
		img: shape [1, X, Y, Z]
		level: scaling factor of downsampling
		order: 3 for image, 0 for label
	Ret:
		imgout: down sampled image of shape [1, X//level, Y//level, Z//level]
	'''
	if level == 1:
		return img
	else:

		imgout = zoom(img[0], 1/level, order=order)
		return imgout[None,:,:,:]

class downSample(object):
	'''
	Down sample happens before affine
	'''
	def __init__(self, level):

		self.level = level
		pass

	def __call__(self, sample):

		image, label = sample['image'], sample['label']
		return {'image': downSampleFun(image, self.level, 1), \
				'label': downSampleFun(label, self.level, 0)}

class RandomFilp(object):
	def __init__(self, p):
		self.p = p

	def __call__(self, sample):
		x, y, z = np.random.uniform(0, 1, size=3)
		p = self.p
		image, label = sample['image'], sample['label']
		return {'image': filpFun(image, (x<p), (y<p), (z<p)), \
			'label': filpFun(label, (x<p), (y<p), (z<p))}

class RandomAffine(object):
	'''
	Random rotation and move
	'''
	def __init__(self, fluR=0, fluM=0, fluS=1, DS=1):

		self.fluR = fluR
		self.fluM = fluM
		self.fluS = fluS
		self.DS = DS

	def __call__(self, sample):

		xr, yr, zr = np.random.uniform(-self.fluR, self.fluR, size=3)		
		xm, ym, zm = np.random.uniform(-self.fluM, self.fluM, size=3)
		s = np.random.uniform(1/self.fluS, self.fluS, size=1)

		image, label = sample['image'], sample['label']
		return {'image': AffineFun(image, xr, yr, zr, xm, ym, zm, s, self.DS, 1), \
				'label': AffineFun(label, xr, yr, zr, xm, ym, zm, s, self.DS, 0)}

class niiDataset(Dataset):
	'''
	pytorch dataset for bv segmentation
	'''
	def __init__(self, index, transform=None):
		'''
		Args:
			index of int
			No Conversion of anykind in a dataset class!
			transform(callable, default=none): transfrom on a sample
		'''

		self.index=index
		self.transform=transform

	def __len__(self):
		'''
		Override: return size of dataset
		'''
		return (self.index).shape[0]

	def __getitem__(self, indice):
		'''
		Override: integer indexing in range from 0 to len(self) exclusive.
		type: keep as np array
		'''
		image, label = loadnii(self.index[indice], 192, 256, 256)
		sample = {'image':image, 'label':label}

		if self.transform:
			sample = self.transform(sample)

		sample = toTensor(sample)

		return sample

class niiMaskDataset(Dataset):

	def __init__(self, index, transform=None):
		self.index=index
		self.transform=transform
		
	def __len__(self):
		'''
		Override: return size of dataset
		'''
		return (self.index).shape[0]

	def __getitem__(self, indice):
		image, label = loadnii(self.index[indice], 128, 192, 192, mode='pad')
		sample = {'image':image, 'label':label}

		# data are numpy array at this point

		if self.transform:
			sample = self.transform(sample)

		sample = toTensor(sample)
		
		imageTensor = sample['image']
		bodyMask = sample['label'].narrow(0, 1, 1)
		bvMask = sample['label'].narrow(0, 2, 1)
		bodyMask = torch.round(bodyMask)
		imageTensor = imageTensor - torch.mean(imageTensor)
		imageTensor = imageTensor*bodyMask
		
		sample = {'image':imageTensor, 'label':bvMask}

		return sample

class BvMaskDataset(Dataset):
	'''
	image: transformed image
	bbox: box cooderinate based on transformed label
	'''
	def __init__(self, index, transform=None):
		self.index=index
		self.transform=transform
		
	def __len__(self):
		'''
		Override: return size of dataset
		'''
		return (self.index).shape[0]

	def __getitem__(self, indice):
		image, label = loadnii(self.index[indice], 192, 256, 256, mode='pad')
		sample = {'image':image, 'label':label}

		# data are numpy array at this point

		if self.transform:
			sample = self.transform(sample)

		BBox = loadbvmask(sample['label'])
		BBox = torch.from_numpy(BBox)
		# Get the BBox ground truth

		sample = toTensor(sample)
		imageTensor = sample['image']
		# bvMask = sample['label'].narrow(0, 2, 1)
		# Get the image tensor
		
		# bodyMask = sample['label'].narrow(0, 1, 1)
		# bodyMask = torch.round(bodyMask)
		# imageTensor = imageTensor - torch.mean(imageTensor)
		# imageTensor = imageTensor*bodyMask
		
		sample = {'image':imageTensor, 'label':BBox}

		return sample

class DatasetBVSeg(Dataset):
	'''
	Dataset obj to use when using 370 BV
	'''
	def __init__(self, index, transform=None):
		self.index=index
		self.transform=transform
        
	def __len__(self):
		'''
		Override: return size of dataset
		'''
		return (self.index).shape[0]

	def __getitem__(self, indice):

		image, label = load_img(indice, mode='bv', shape=(256, 256, 256), verbose=False)
		sample = {'image':image, 'label':label}

		if self.transform:
			sample = self.transform(sample)

		# have to perform transform with data

		BBox = loadbvmask(sample['label'])
		BBox = torch.from_numpy(BBox)
		# Get the BBox ground truth

		sample = toTensorBV(sample)
		imageTensor = sample['image']

		sample = {'image':imageTensor, 'label':BBox}

		return sample

class DatasetBV(Dataset):
	'''
	Dataset obj to use when using 370 BV
	'''
	def __init__(self, index, transform=None):
		self.index=index
		self.transform=transform
        
	def __len__(self):
		'''
		Override: return size of dataset
		'''
		return (self.index).shape[0]

	def __getitem__(self, indice):
		# load_img(idx, mode, shape, verbose=False):
#		image = self.datamem[self.index[indice]]
#		label = self.labelmem[self.index[indice]]

		image, label = load_img(indice, mode='bv', shape=(256, 256, 256), verbose=False)
		sample = {'image':image, 'label':label}

		if self.transform:
			sample = self.transform(sample)

		# have to perform transform with data
		BBox = loadbvcenter(sample['label'])
		BBox = torch.from_numpy(BBox)
		# Get the BBox ground truth

		sample = toTensorBV(sample)
		imageTensor = sample['image']

		sample = {'image':imageTensor, 'label':BBox}

		return sample

class DatasetBVSegmentation(Dataset):
	'''
	Dataset obj to use when using 370 BV, with original image returned
	'''
	def __init__(self, index, transform=None):
		self.index=index
		self.transform=transform
        
	def __len__(self):
		'''
		Override: return size of dataset
		'''
		return (self.index).shape[0]

	def __getitem__(self, indice):

		image, label = load_img(self.index[indice], mode='bv', shape=(256, 256, 256), verbose=False)
		sample = {'image':image, 'label':label}

		if self.transform:
			sample = self.transform(sample)
		# Down Sample by hand
		# have to perform transform with data
		imageTrans = sample['image']
		labelTrans = sample['label']
		imageHalf = downSampleFun(imageTrans, 2, 3)
        
		imageTensor = torch.from_numpy(((imageTrans-0.25)*256).copy())
		imageHalfTensor = torch.from_numpy(((imageHalf-0.25)*256).copy())
        
		labelTensor = torch.from_numpy(labelTrans.copy()) # no need to conduct anything special to it, I think
		labelTensor = torch.round(labelTensor)
        
		sample = {'image':imageTensor, 'label':labelTensor, 'half':imageHalfTensor}

		return sample


class niiPatchDataset(Dataset):
	'''
	patched dataset for bv segmentation
	'''
	def __init__(self, index, transform=None):
		self.index = index
		self.transform=transform

	def __len__(self):
		return (self.index).shape[0]*2*3*3

	def __getitem__(self, indice):
		
		image_indice = indice//(2*3*3)
		indice = indice%(2*3*3)

		h_index = indice//(3*3)
		indice = indice%(3*3)

		w_index = indice//3
		d_index = indice%3

		image, label = loadnii(self.index[indice], 192, 256, 256)

		image_sample = image[:, 64*h_index:64*(h_index+1), 64*w_index:64*(w_index+1) \
			, 64*d_index:64*(d_index+1)]

		label_sample = label[:, 64*h_index:64*(h_index+1), 64*w_index:64*(w_index+1) \
			, 64*d_index:64*(d_index+1)]

		label_sample = label_sample - torch.mean(label_sample)

		sample = {'image':image_sample, 'label':label_sample}
		sample = toTensor(sample)
		return sample